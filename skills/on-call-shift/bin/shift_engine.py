#!/usr/bin/env python3
"""on-call-shift reference engine: the shift contract as pure, testable state transitions.

Stdlib only. No network, no model, no subprocess, no clock of its own: every function takes
`now` (epoch seconds) from the caller, so a host timer, a test or a replay all drive it the
same way. The engine never sends anything and never launches anything. A host adapter does
the I/O; the engine decides whether that I/O is allowed and records what really happened.

Contract: skills/on-call-shift/references/shift-contract.md (state, lease, cursor, signals,
handoff) and references/backlog-adoption.md (connectors, normalization, RACI/DARCI).
"""
from __future__ import annotations

import copy
import json
import os
import tempfile

SCHEMA = "on-call-shift/state@1"

# Operator mantras used only when the operator gave none. An explicit list is kept verbatim.
DEFAULT_MANTRAS = (
    "change the decision when the evidence changes",
    "a verifiable increment beats an announced plan",
)

# Four distinct signals. Only the last one is "the shift did its job".
SIGNALS = ("tick", "notification", "wakeup", "resume")

# Connector outcomes. Only "empty" means the queue is empty.
CONNECTOR_STATES = ("ok", "empty", "denied", "unavailable", "partial")

ACTIVE, HANDOFF_PENDING, STOPPED, REVOKED = "ACTIVE", "HANDOFF_PENDING", "STOPPED", "REVOKED"


class ShiftError(Exception):
    """A transition the contract forbids. `code` is stable for callers and tests."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


# --------------------------------------------------------------------------- open / persist

def open_shift(*, shift_id, principal, scope, backlog, capacity, budget, holder,
               supervisor_target, now, lease_secs, mantras=None, capabilities=None,
               successor_policy=None):
    """Assume a shift. Every field the contract needs is required; none is guessed."""
    for name, value in (("shift_id", shift_id), ("principal", principal), ("scope", scope),
                        ("holder", holder), ("supervisor_target", supervisor_target)):
        if not value:
            raise ShiftError("MISSING_FIELD", name)
    if capacity is None or int(capacity) < 1:
        raise ShiftError("MISSING_FIELD", "capacity")
    if budget is None or int(budget) < 0:
        raise ShiftError("MISSING_FIELD", "budget")
    explicit = [m for m in (mantras or []) if isinstance(m, str) and m.strip()]
    state = {
        "schema": SCHEMA,
        "shift_id": shift_id,
        "principal": principal,
        "scope": scope,
        "backlog": backlog,  # None = not given; adoption runs only then (see adopt rules)
        "capacity": int(capacity),
        "budget": {"limit": int(budget), "spent": 0},
        "mantras": explicit if explicit else list(DEFAULT_MANTRAS),
        "mantras_source": "explicit" if explicit else "default",
        "holder": holder,
        "supervisor_target": supervisor_target,
        "lease": {"holder": holder, "expires_at": now + int(lease_secs),
                  "lease_secs": int(lease_secs)},
        "generation": 1,
        # Successor the PRINCIPAL pre-authorized to take over if the holder dies. The
        # outgoing holder cannot set this for itself mid-shift; it comes in at intake.
        # One authorization, one succession: the policy is bound to the generation it was
        # armed in and consumed by the takeover it allows.
        "successor_policy": _bind_policy(successor_policy, holder, principal, 1),
        "continuity": _continuity(successor_policy),
        "consumed_takeovers": [],
        "incident": None,
        "decisions": {},
        "deliveries": {},
        "reopened": {},
        "parked": [],
        "cursor": {"seq": 0, "last_event_id": None},
        "processed_events": [],
        "effects": [],
        "adopted": {},
        "in_flight": [],
        "gates": {},
        "pending_events": {},
        "handoff": None,
        "status": ACTIVE,
        "wakeup": classify_wakeup(capabilities or {}, supervisor_target),
        "log": [{"at": now, "event": "shift_opened", "holder": holder}],
    }
    return state


def save(state, path):
    """Atomic write: a crash mid-save leaves the previous state, never a torn file."""
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".shift-", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def load(path):
    with open(path, encoding="utf-8") as handle:
        state = json.load(handle)
    if state.get("schema") != SCHEMA:
        raise ShiftError("SCHEMA_MISMATCH", str(state.get("schema")))
    return state


# --------------------------------------------------------------------------- lease

def lease_valid(state, actor, now, generation=None):
    """`generation` is the fencing token the caller last saw; a stale one is never valid."""
    lease = state["lease"]
    if generation is not None and generation != state["generation"]:
        return False
    return (state["status"] in (ACTIVE, HANDOFF_PENDING)
            and lease["holder"] == actor == state["holder"]
            and now < lease["expires_at"])


def _require_holder(state, actor, now, generation):
    """Every mutator calls this: the caller must hold the lease AND show the current
    generation (fencing token). A missing token is refused, never assumed current."""
    if generation is None:
        raise ShiftError("GENERATION_REQUIRED", actor)
    if generation != state["generation"]:
        raise ShiftError("STALE_GENERATION", f"{generation} != {state['generation']}")
    if not lease_valid(state, actor, now):
        raise ShiftError("LEASE_INVALID", f"{actor} does not hold a valid lease")


def renew_lease(state, actor, now, *, generation):
    _require_holder(state, actor, now, generation)
    state["lease"]["expires_at"] = now + state["lease"]["lease_secs"]
    return state


# --------------------------------------------------------------------------- signals

def classify_wakeup(capabilities, supervisor_target=None):
    """Declare what the runtime really offers. Absent capability = DEGRADED, never 'always on'.

    `capabilities` comes from the host adapter (see ooda-loop references/runtime-adapters.md):
    {"wakeup_transport": "<name>" | None, "bound_target": "<exact supervisor>" | None}.
    """
    transport = capabilities.get("wakeup_transport")
    target = capabilities.get("bound_target")
    if transport and target and target == supervisor_target:
        return {"mode": "SUPPORTED", "transport": transport, "bound_target": target,
                "reason": None, "recovery": None, "always_on_claim": False}
    reason = ("NO_BOUND_WAKEUP_TRANSPORT" if not transport else
              "NO_BOUND_TARGET" if not target else "BOUND_TARGET_MISMATCH")
    return {"mode": "DEGRADED", "transport": transport, "bound_target": target,
            "reason": reason,
            "recovery": "bind a host wakeup transport to the exact supervisor, or poll on the "
                        "next human or scheduled turn; report the gap, do not claim coverage",
            "always_on_claim": False}


def apply_tick(state, actor, event_id, now, *, generation):
    """A tick is evidence the clock ran. It notifies nobody. A replayed id has no effect."""
    _require_holder(state, actor, now, generation)
    if event_id in state["processed_events"]:
        return state, None
    state["processed_events"].append(event_id)
    state["cursor"] = {"seq": state["cursor"]["seq"] + 1, "last_event_id": event_id}
    effect = {"signal": "tick", "event_id": event_id, "at": now,
              "notification": "NOT_SENT_BY_TIMER", "execution": "NOT_REQUESTED"}
    state["effects"].append(effect)
    return state, effect


def authorize_send(state, actor, target, now, generation=None):
    """Gate for any outbound notification or wakeup. Returns the decision; sends nothing."""
    if generation is not None and generation != state["generation"]:
        return {"allowed": False, "reason": "STALE_GENERATION"}
    if not lease_valid(state, actor, now):
        return {"allowed": False, "reason": "LEASE_INVALID"}
    if target != state["supervisor_target"]:
        return {"allowed": False, "reason": "WRONG_TARGET"}
    return {"allowed": True, "reason": None}


def record_signal(state, actor, kind, event_id, receipt, now, *, generation):
    """Record a signal the HOST reports it exercised. The kind must be proven by the receipt.

    - notification: receipt.delivered_to == supervisor_target
    - wakeup: SUPPORTED mode AND receipt.woken == supervisor_target
    - resume: receipt.consumed_by == holder AND receipt.effects == 1
    Anything weaker is recorded as the weaker kind that the receipt does prove.
    """
    _require_holder(state, actor, now, generation)
    if kind not in SIGNALS:
        raise ShiftError("UNKNOWN_SIGNAL", kind)
    proven = "tick"
    target = state["supervisor_target"]
    if receipt.get("delivered_to") == target:
        proven = "notification"
    if state["wakeup"]["mode"] == "SUPPORTED" and receipt.get("woken") == target:
        proven = "wakeup"
    if (proven == "wakeup" and receipt.get("consumed_by") == state["holder"]
            and receipt.get("effects") == 1):
        proven = "resume"
    entry = {"signal": proven, "claimed": kind, "event_id": event_id, "at": now,
             "downgraded": SIGNALS.index(proven) < SIGNALS.index(kind)}
    state["effects"].append(entry)
    return entry


# --------------------------------------------------------------------------- events and ACK

def open_event(state, actor, event_id, now, *, recipient, generation):
    _require_holder(state, actor, now, generation)
    if not recipient or recipient == actor:
        raise ShiftError("BAD_EVENT_RECIPIENT", str(recipient))
    if event_id in state["pending_events"]:
        return state
    state["pending_events"][event_id] = {"opened_at": now, "acked": False,
                                         "recipient": recipient}
    return state


def conclude_event(state, actor, event_id, ack, now, *, generation):
    """An event is concluded only with an ACK from its recipient. No ACK = still pending."""
    _require_holder(state, actor, now, generation)
    event = state["pending_events"].get(event_id)
    if event is None:
        raise ShiftError("UNKNOWN_EVENT", event_id)
    if not ack or ack.get("event_id") != event_id or not ack.get("from"):
        return {"concluded": False, "reason": "NO_ACK"}
    if ack.get("kind") == "heartbeat":
        return {"concluded": False, "reason": "HEARTBEAT_IS_NOT_ACK"}
    if ack.get("from") != event.get("recipient"):
        return {"concluded": False, "reason": "ACK_NOT_FROM_RECIPIENT"}
    event["acked"] = True
    del state["pending_events"][event_id]
    state["log"].append({"at": now, "event": "event_concluded", "id": event_id})
    return {"concluded": True, "reason": None}


# --------------------------------------------------------------------------- backlog

def normalize_backlog(connector_results):
    """Merge items from N connectors into one work-item per intent key.

    connector_results: [{"connector", "kind", "identity", "scope", "status", "observed_at",
                         "items": [{"ref", "intent_key", "links", "assignee", "state",
                                    "in_flight_by", "gate", "gut", "raci"}]}]
    Returns {"items": {intent_key: merged}, "connectors": [...], "queue_empty": bool}.
    """
    merged = {}
    connectors = []
    for result in connector_results:
        status = result.get("status")
        if status not in CONNECTOR_STATES:
            raise ShiftError("BAD_CONNECTOR_STATUS", str(status))
        connectors.append({k: result.get(k) for k in
                           ("connector", "kind", "identity", "scope", "status",
                            "observed_at", "error")})
        for item in result.get("items") or []:
            key = item.get("intent_key")
            if not key:
                raise ShiftError("MISSING_INTENT_KEY", str(item.get("ref")))
            target = merged.setdefault(key, {
                "intent_key": key, "refs": [], "assignee": None, "in_flight_by": None,
                "gate": None, "gut": 0, "raci": {}})
            for ref in [item.get("ref")] + list(item.get("links") or []):
                if ref and ref not in target["refs"]:
                    target["refs"].append(ref)
            for field in ("assignee", "in_flight_by", "gate"):
                if item.get(field) and not target[field]:
                    target[field] = item[field]
            target["gut"] = max(target["gut"], int(item.get("gut") or 0))
            for role in ("driver", "responsible", "approver", "consulted", "informed"):
                value = (item.get("raci") or {}).get(role)
                if value and role not in target["raci"]:
                    target["raci"][role] = value
    for item in merged.values():
        for role in ("driver", "responsible", "approver", "consulted", "informed"):
            item["raci"].setdefault(role, "unknown")  # never invented
    every_connector_empty = bool(connectors) and all(c["status"] == "empty" for c in connectors)
    return {"items": merged, "connectors": connectors,
            "queue_empty": every_connector_empty and not merged}


def _ineligible(state, item, actor):
    """Why an item may not be adopted by `actor` now, or None. Shared by select and adopt."""
    if item["in_flight_by"] and item["in_flight_by"] != actor:
        return "IN_FLIGHT_BY_OTHER"
    if item["assignee"] and item["assignee"] != actor:
        return "OWNED_BY_OTHER"
    gate = state["gates"].get(item["intent_key"])
    if item["gate"] or (gate and gate.get("state") != "granted"):
        return "HUMAN_GATE"
    return None


def select_next(state, backlog, actor, now, *, generation):
    """Pick ONE eligible item, or return a reasoned wait. Never invents work."""
    _require_holder(state, actor, now, generation)
    if state.get("incident"):
        return {"action": "handle_incident", "incident": state["incident"]["id"]}
    if state["budget"]["spent"] >= state["budget"]["limit"]:
        return {"action": "wait", "reason": "BUDGET_EXHAUSTED"}
    if len(state["in_flight"]) >= state["capacity"]:
        return {"action": "wait", "reason": "CAPACITY_FULL"}
    skipped = []
    candidates = []
    for key, item in backlog["items"].items():
        if key in state["adopted"]:
            continue
        why = _ineligible(state, item, actor)
        if why == "HUMAN_GATE":
            skipped.append({"intent_key": key, "why": why,
                            "gate": item["gate"] or state["gates"].get(key)})
            continue
        if why:
            skipped.append({"intent_key": key, "why": why,
                            "offer": "remove impediment; do not take authorship"})
            continue
        candidates.append(item)
    if candidates:
        chosen = sorted(candidates, key=lambda i: (-i["gut"], i["intent_key"]))[0]
        return {"action": "adopt", "intent_key": chosen["intent_key"], "skipped": skipped}
    blind = [c["connector"] for c in backlog["connectors"]
             if c["status"] in ("denied", "unavailable", "partial")]
    if blind:
        return {"action": "wait", "reason": "CONNECTORS_NOT_READABLE", "connectors": blind,
                "skipped": skipped}
    return {"action": "wait", "reason": "NO_ELIGIBLE_ITEM", "skipped": skipped}


def adopt(state, actor, intent_key, backlog, now, *, generation):
    """Adopt once. Re-adopting the same intent key is a no-op, so a replay adds nothing.
    Every limit is checked again here, before any mutation: select_next is advice only."""
    _require_holder(state, actor, now, generation)
    if state["backlog"] and not state.get("backlog_exhausted"):
        raise ShiftError("BACKLOG_GIVEN", "adopt only when no backlog was given or it is done")
    if intent_key in state["adopted"]:
        return state, False
    item = backlog["items"].get(intent_key)
    if item is None:
        raise ShiftError("UNKNOWN_ITEM", intent_key)
    why = _ineligible(state, item, actor)
    if why:
        raise ShiftError(why, intent_key)
    if state.get("incident"):
        raise ShiftError("INCIDENT_ACTIVE", intent_key)
    if state["budget"]["spent"] >= state["budget"]["limit"]:
        raise ShiftError("BUDGET_EXHAUSTED", intent_key)
    if len(state["in_flight"]) >= state["capacity"]:
        raise ShiftError("CAPACITY_FULL", intent_key)
    state["adopted"][intent_key] = {"refs": list(item["refs"]), "at": now}
    state["in_flight"].append(intent_key)
    state["budget"]["spent"] += 1
    return state, True


def mark_backlog_exhausted(state, actor, now, *, generation):
    _require_holder(state, actor, now, generation)
    state["backlog_exhausted"] = True
    return state


# --------------------------------------------------------------------------- gates, review

def set_gate(state, actor, intent_key, gate, now, *, generation):
    """gate: {"kind": "approval"|"veto", "by": "<decider>", "deadline": epoch, "state": ...}.

    The holder records gates. Once a gate exists, changing it needs `decided_by` equal to the
    gate's own decider, so a veto is never flipped by anyone else."""
    _require_holder(state, actor, now, generation)
    current = state["gates"].get(intent_key)
    if current and gate.get("decided_by") != current.get("by"):
        raise ShiftError("GATE_DECIDER_MISMATCH", intent_key)
    state["gates"][intent_key] = dict(gate, by=current.get("by") if current else gate.get("by"))
    return state


def complete_item(state, actor, intent_key, *, author, reviewer, now, generation):
    _require_holder(state, actor, now, generation)
    gate = state["gates"].get(intent_key)
    if gate and gate.get("state") != "granted":
        return {"completed": False,
                "reason": "VETOED" if gate.get("kind") == "veto" else "AWAITING_HUMAN_GATE",
                "deadline": gate.get("deadline")}
    if not reviewer or reviewer == author:
        return {"completed": False, "reason": "REVIEWER_IS_AUTHOR"}
    if intent_key in state["in_flight"]:
        state["in_flight"].remove(intent_key)
    _delivery(state, intent_key)["technical_verified"] = True
    state["log"].append({"at": now, "event": "item_completed", "id": intent_key,
                         "author": author, "reviewer": reviewer})
    return {"completed": True, "reason": None}


# --------------------------------------------------------------------------- handoff, stop

def _handoff_view(state):
    return {"cursor_seq": state["cursor"]["seq"], "in_flight": sorted(state["in_flight"]),
            "gates": sorted(state["gates"]), "generation": state["generation"]}


def propose_handoff(state, actor, successor, now, *, generation):
    _require_holder(state, actor, now, generation)
    if not successor or successor == actor:
        raise ShiftError("NO_SUCCESSOR", str(successor))
    state["handoff"] = dict(_handoff_view(state), **{"from": actor, "to": successor,
                                                     "proposed_at": now})
    state["status"] = HANDOFF_PENDING
    return state


def accept_handoff(state, ack, now):
    """Relief happens only on an explicit ACK that echoes cursor, in-flight work and gates."""
    handoff = state.get("handoff")
    if state["status"] != HANDOFF_PENDING or not handoff:
        raise ShiftError("NO_PENDING_HANDOFF")
    if not ack or ack.get("kind") != "handoff_ack":
        return {"relieved": False, "reason": "NOT_A_HANDOFF_ACK"}
    if ack.get("from") != handoff["to"]:
        return {"relieved": False, "reason": "ACK_FROM_WRONG_PARTY"}
    live = _handoff_view(state)
    if any(live[k] != handoff[k] for k in live):
        # Work moved after the proposal: the old ACK no longer covers it. Refresh the
        # proposal to the live state; the successor must ACK again. Nothing is dropped.
        handoff.update(live)
        return {"relieved": False, "reason": "PROPOSAL_STALE_REACK", "expect": live}
    if ack.get("generation") != handoff["generation"]:
        return {"relieved": False, "reason": "ACK_MISMATCH_GENERATION"}
    for field in ("cursor_seq", "in_flight", "gates"):
        echoed = ack.get(field)
        if field != "cursor_seq":
            echoed = sorted(echoed or [])
        if echoed != handoff[field]:
            return {"relieved": False, "reason": f"ACK_MISMATCH_{field.upper()}"}
    state["holder"] = handoff["to"]
    state["generation"] += 1
    state["lease"] = {"holder": handoff["to"], "expires_at": now + state["lease"]["lease_secs"],
                      "lease_secs": state["lease"]["lease_secs"]}
    state["status"] = ACTIVE
    state["log"].append({"at": now, "event": "relieved", "from": handoff["from"],
                         "to": handoff["to"]})
    state["handoff"] = None
    # A policy armed in the previous generation no longer applies to the new holder.
    state["continuity"] = _continuity(_live_policy(state))
    return {"relieved": True, "reason": None}


def handoff_timed_out(state, now, deadline_secs):
    """Silence is not relief: past the deadline the outgoing holder keeps the shift."""
    handoff = state.get("handoff")
    if state["status"] == HANDOFF_PENDING and handoff and now >= handoff["proposed_at"] + deadline_secs:
        state["status"] = ACTIVE
        state["handoff"] = None
        state["log"].append({"at": now, "event": "handoff_timeout_kept_by",
                             "holder": state["holder"]})
        return True
    return False


def stop_shift(state, by, now, *, revoke=False):
    """Legitimate stop or revocation: only the principal may end the shift without relief."""
    if by != state["principal"]:
        raise ShiftError("NOT_AUTHORIZED_TO_STOP", by)
    state["status"] = REVOKED if revoke else STOPPED
    state["lease"]["expires_at"] = now
    state["log"].append({"at": now, "event": "revoked" if revoke else "stopped", "by": by,
                         "in_flight_left": sorted(state["in_flight"])})
    return state


# --------------------------------------------------------------------------- UDV

SATISFACTION = ("confirmed", "refused", "unknown")


def _delivery(state, intent_key):
    return state["deliveries"].setdefault(intent_key, {
        "technical_verified": False, "delivered_to_recipient": False,
        "satisfaction": "unknown", "recipient": None, "recipient_kind": None,
        "attempts": 0, "result_ref": None, "reservations": None, "reopened_as": None})


def deliver(state, actor, intent_key, *, recipient, recipient_kind, result_ref, receipt, now,
            generation):
    """Hand the result to its recipient once. Receipt proves receipt, not satisfaction.

    receipt: {"received_by": <recipient> | None}. An absent recipient leaves the delivery
    pending; the same result is never sent again (no resend loop). Evidence is bound to the
    (result, recipient) pair: a different result or recipient resets it.
    """
    _require_holder(state, actor, now, generation)
    if recipient_kind not in ("human", "agent"):
        raise ShiftError("BAD_RECIPIENT_KIND", str(recipient_kind))
    record = _delivery(state, intent_key)
    if record["attempts"] and record["result_ref"] == result_ref:
        if record["recipient"] == recipient:
            return {"sent": False, "reason": "NO_RESEND_SAME_RESULT"}
    if record["attempts"] and (record["result_ref"], record["recipient"]) != (result_ref, recipient):
        # The accepted evidence was for another result or another person: it no longer applies.
        record.update(technical_verified=False, delivered_to_recipient=False,
                      satisfaction="unknown", reservations=None)
    record.update(recipient=recipient, recipient_kind=recipient_kind, result_ref=result_ref)
    record["attempts"] += 1
    record["delivered_to_recipient"] = (receipt or {}).get("received_by") == recipient
    return {"sent": True,
            "reason": None if record["delivered_to_recipient"] else "RECIPIENT_ABSENT_PENDING"}


def record_receipt(state, actor, intent_key, receipt, now, *, generation):
    """A late receipt for the result already sent. Records it; sends nothing again."""
    _require_holder(state, actor, now, generation)
    record = state["deliveries"].get(intent_key)
    if not record or not record["attempts"]:
        return {"recorded": False, "reason": "NOTHING_SENT"}
    if (receipt or {}).get("result_ref") not in (None, record["result_ref"]):
        return {"recorded": False, "reason": "RECEIPT_FOR_OTHER_RESULT"}
    if (receipt or {}).get("received_by") != record["recipient"]:
        return {"recorded": False, "reason": "NOT_THE_RECIPIENT"}
    record["delivered_to_recipient"] = True
    return {"recorded": True, "reason": None, "attempts": record["attempts"]}


def record_feedback(state, actor, intent_key, feedback, now, *, generation):
    """feedback: {"from", "kind": accept|accept_with_reservation|reject, "on_behalf_of"?, "note"?}.

    Only the recipient answers, and an agent recipient answers only for its own role, never for
    a person. A qualified acceptance is not unequivocal satisfaction. A rejection reopens the
    intent, linked to the original result. Feedback naming another result is refused.
    """
    _require_holder(state, actor, now, generation)
    record = state["deliveries"].get(intent_key)
    if not record or not record["delivered_to_recipient"]:
        return {"recorded": False, "reason": "NOT_DELIVERED"}
    if feedback.get("from") != record["recipient"]:
        return {"recorded": False, "reason": "NOT_THE_RECIPIENT"}
    if feedback.get("result_ref") not in (None, record["result_ref"]):
        return {"recorded": False, "reason": "FEEDBACK_FOR_OTHER_RESULT"}
    on_behalf = feedback.get("on_behalf_of")
    if record["recipient_kind"] == "agent" and on_behalf and on_behalf != feedback["from"]:
        return {"recorded": False, "reason": "AGENT_CANNOT_ACCEPT_FOR_A_PERSON"}
    kind = feedback.get("kind")
    if kind == "accept":
        record["satisfaction"] = "confirmed"
    elif kind == "accept_with_reservation":
        record["satisfaction"] = "unknown"
        record["reservations"] = feedback.get("note") or "unspecified"
    elif kind == "reject":
        record["satisfaction"] = "refused"
        reopened = f"{intent_key}#reopen-{len(state['reopened']) + 1}"
        state["reopened"][reopened] = {"reopens": intent_key,
                                       "result_ref": record["result_ref"],
                                       "note": feedback.get("note"), "at": now}
        record["reopened_as"] = reopened
        state["in_flight"].append(reopened)
    else:
        raise ShiftError("BAD_FEEDBACK_KIND", str(kind))
    return {"recorded": True, "reason": None}


def udv_status(state, intent_key):
    """Three independent states. 100% only when delivered AND satisfaction is confirmed."""
    record = state["deliveries"].get(intent_key) or _delivery(copy.deepcopy(state), intent_key)
    done = (record["technical_verified"] and record["delivered_to_recipient"]
            and record["satisfaction"] == "confirmed")
    if done:
        pending = None
    elif not record["delivered_to_recipient"]:
        pending = "AWAITING_RECIPIENT"
    elif record["satisfaction"] == "refused":
        pending = "REJECTED_REOPENED"
    elif record["reservations"]:
        pending = "QUALIFIED_ACCEPTANCE"
    elif not record["technical_verified"]:
        pending = "TECHNICAL_NOT_VERIFIED"
    else:
        pending = "SATISFACTION_UNKNOWN"
    return {"technical_verified": record["technical_verified"],
            "delivered_to_recipient": record["delivered_to_recipient"],
            "satisfaction": record["satisfaction"],
            "udv_percent": 100 if done else 0, "pending": pending}


# --------------------------------------------------------------------------- blast radius

BLAST_FIELDS = ("data", "people", "projects", "accounts", "dependencies", "reversible",
                "worst_case", "detection", "recovery_owner", "crosses_authority", "in_scope")


def assess_effect(state, actor, operation_id, blast, now, *, generation):
    """Run before every effect. Local, reversible and in scope proceeds; anything that crosses
    an authority limit parks THAT operation only and leaves the rest of the shift running."""
    _require_holder(state, actor, now, generation)
    missing = [f for f in BLAST_FIELDS if f not in blast]
    if missing:
        return {"decision": "refuse", "reason": "INCOMPLETE_BLAST_RADIUS", "missing": missing}
    if blast["in_scope"] and blast["reversible"] and not blast["crosses_authority"]:
        return {"decision": "proceed", "reason": None}
    reason = ("CROSSES_AUTHORITY" if blast["crosses_authority"]
              else "OUT_OF_SCOPE" if not blast["in_scope"] else "IRREVERSIBLE")
    state["parked"].append({"operation": operation_id, "reason": reason,
                            "recovery_owner": blast["recovery_owner"], "at": now})
    return {"decision": "park", "reason": reason}


# --------------------------------------------------------------------------- incident, route

def raise_incident(state, actor, incident_id, now, *, generation):
    """An incident preempts backlog work. It never moves the cursor or drops in-flight work."""
    _require_holder(state, actor, now, generation)
    if state.get("incident"):
        return {"raised": False, "reason": "INCIDENT_ALREADY_OPEN"}
    state["incident"] = {"id": incident_id, "opened_at": now,
                         "cursor_at_open": dict(state["cursor"])}
    return {"raised": True, "reason": None}


def resolve_incident(state, actor, incident_id, now, *, generation):
    _require_holder(state, actor, now, generation)
    incident = state.get("incident")
    if not incident or incident["id"] != incident_id:
        return {"resolved": False, "reason": "UNKNOWN_INCIDENT"}
    state["incident"] = None
    state["log"].append({"at": now, "event": "incident_resolved", "id": incident_id})
    return {"resolved": True, "reason": None}


def decide_route(state, actor, decision_key, evidence, now, *, generation):
    """Change a decision only on NEW evidence. evidence: {"source", "digest", "supports",
    "lens"?}. The same (source, digest) seen again is an echo and changes nothing. The lens is
    recorded only when it changed the route."""
    _require_holder(state, actor, now, generation)
    record = state["decisions"].setdefault(decision_key, {"choice": None, "seen": [],
                                                          "changes": []})
    fingerprint = f"{evidence.get('source')}#{evidence.get('digest')}"
    if not evidence.get("source") or not evidence.get("digest"):
        return {"changed": False, "reason": "EVIDENCE_WITHOUT_SOURCE", "choice": record["choice"]}
    if fingerprint in record["seen"]:
        return {"changed": False, "reason": "REPEATED_EVIDENCE", "choice": record["choice"]}
    record["seen"].append(fingerprint)
    if evidence.get("supports") == record["choice"]:
        return {"changed": False, "reason": "SAME_CONCLUSION", "choice": record["choice"]}
    record["changes"].append({"from": record["choice"], "to": evidence.get("supports"),
                              "evidence": fingerprint, "lens": evidence.get("lens"), "at": now})
    record["choice"] = evidence.get("supports")
    return {"changed": True, "reason": None, "choice": record["choice"]}


# --------------------------------------------------------------------------- holder loss

def _bind_policy(policy, holder, principal, generation):
    """Normalize a successor policy and bind it to one generation. Self-succession is refused."""
    if not policy or not policy.get("pre_authorized"):
        return None
    if policy["pre_authorized"] == holder:
        raise ShiftError("SELF_SUCCESSION", holder)
    return {"pre_authorized": policy["pre_authorized"], "armed_by": principal,
            "armed_generation": generation,
            "nonce": policy.get("nonce") or f"g{generation}:{policy['pre_authorized']}"}


def _live_policy(state):
    """The policy counts only in the generation it was armed in."""
    policy = state.get("successor_policy")
    if policy and policy.get("armed_generation") == state["generation"]:
        return policy
    return None


def _continuity(successor_policy):
    if successor_policy and successor_policy.get("pre_authorized"):
        return {"mode": "SUPPORTED", "reason": None, "uninterrupted_claim": False}
    return {"mode": "DEGRADED", "reason": "NO_PREAUTHORIZED_SUCCESSOR",
            "uninterrupted_claim": False}


def arm_successor(state, by, successor, generation, now, nonce=None):
    """Arm a new successor. Only the principal may do it, only for the current generation,
    and never naming the current holder."""
    if by != state["principal"]:
        return {"armed": False, "reason": "NOT_AUTHORIZED_TO_ARM"}
    if generation != state["generation"]:
        return {"armed": False, "reason": "STALE_GENERATION"}
    if state["status"] not in (ACTIVE, HANDOFF_PENDING):
        return {"armed": False, "reason": "SHIFT_NOT_ACTIVE"}
    if not successor or successor == state["holder"]:
        return {"armed": False, "reason": "SELF_SUCCESSION"}
    policy = _bind_policy({"pre_authorized": successor, "nonce": nonce}, state["holder"],
                          by, state["generation"])
    if policy["nonce"] in state["consumed_takeovers"]:
        return {"armed": False, "reason": "NONCE_ALREADY_USED"}
    state["successor_policy"] = policy
    state["continuity"] = _continuity(policy)
    state["log"].append({"at": now, "event": "successor_armed", "successor": successor,
                         "generation": state["generation"]})
    return {"armed": True, "reason": None}


def take_over(state, claimant, now, nonce=None):
    """The holder's lease lapsed (holder presumed dead, no ACK). Only the successor the
    principal armed for the CURRENT generation may take over, exactly once: the policy is
    consumed, the generation goes up, cursor, events, in-flight work, gates and UDV records stay
    as they were. A second expiry needs a new arming; without one the shift is DEGRADED."""
    if state["status"] not in (ACTIVE, HANDOFF_PENDING):
        return {"taken_over": False, "reason": "SHIFT_NOT_ACTIVE"}
    if now < state["lease"]["expires_at"]:
        return {"taken_over": False, "reason": "HOLDER_LEASE_STILL_VALID"}
    if claimant == state["holder"]:
        return {"taken_over": False, "reason": "SELF_SUCCESSION"}
    policy = _live_policy(state)
    if nonce is not None and nonce in state["consumed_takeovers"]:
        return {"taken_over": False, "reason": "REPLAY"}
    if not policy:
        state["continuity"] = _continuity(None)
        state["log"].append({"at": now, "event": "holder_lost_degraded",
                             "last_holder": state["holder"]})
        return {"taken_over": False, "reason": "NO_PREAUTHORIZED_SUCCESSOR"}
    if claimant != policy["pre_authorized"]:
        return {"taken_over": False, "reason": "NOT_THE_PREAUTHORIZED_SUCCESSOR"}
    if nonce is not None and nonce != policy["nonce"]:
        return {"taken_over": False, "reason": "NONCE_MISMATCH"}
    previous = state["holder"]
    state["consumed_takeovers"].append(policy["nonce"])
    state["successor_policy"] = None  # one authorization, one succession
    state["generation"] += 1
    state["holder"] = claimant
    state["lease"] = {"holder": claimant, "expires_at": now + state["lease"]["lease_secs"],
                      "lease_secs": state["lease"]["lease_secs"]}
    state["status"] = ACTIVE
    state["handoff"] = None
    state["continuity"] = _continuity(None)  # nobody armed for the new generation yet
    state["log"].append({"at": now, "event": "taken_over", "from": previous, "to": claimant,
                         "generation": state["generation"], "nonce": policy["nonce"]})
    return {"taken_over": True, "reason": None, "generation": state["generation"],
            "nonce": policy["nonce"]}


def snapshot(state):
    return copy.deepcopy(state)
