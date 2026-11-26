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
import datetime
import json
import math
import os
import tempfile

# state@2 (v0.3.0) adds budget.money/deadline, heartbeat and stop. A v0.2.0 engine's load()
# refuses it; load()/load_checked() here migrate a state@1 (v0.2.0) file.
SCHEMA = "on-call-shift/state@2"
LEGACY_SCHEMAS = ("on-call-shift/state@1",)
# A deadline at or above this is a millisecond epoch, not seconds (year 5138 in seconds).
DEADLINE_MAX_EPOCH_SECS = 1e11

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

def _check_scope(scope):
    if isinstance(scope, str) and scope.strip():
        return scope
    if (isinstance(scope, (list, tuple)) and scope
            and all(isinstance(part, str) and part.strip() for part in scope)):
        return list(scope)
    raise ShiftError("MISSING_FIELD", "scope")


def _number(value, field, *, count=False):
    """A finite number from the intake, or a contract error naming the field (never a raw
    ValueError, TypeError, OverflowError or NaN)."""
    try:
        number = int(value) if count else float(value)
        finite = math.isfinite(number)  # an int too large for a float overflows here
    except (TypeError, ValueError, OverflowError):
        raise ShiftError("BAD_BUDGET", field) from None
    if not finite or number < 0:
        raise ShiftError("BAD_BUDGET", field)
    return number


def _utc(epoch_secs):
    return datetime.datetime.fromtimestamp(epoch_secs, tz=datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def _new_budget(budget, now):
    """An int is a count of adoptions (the v0.2 shape). A dict carries the principal's own
    terms, any of: "adoptions"; a money cap ("currency", "amount", optional "freeze_at" below
    it, optional "baseline" measured at open, optional "source"); a "deadline" in epoch
    seconds, UTC (a millisecond epoch is refused).
    Money is measured as a delta from the baseline, never assumed. Nothing is guessed."""
    if not isinstance(budget, dict):
        if budget is None:
            raise ShiftError("MISSING_FIELD", "budget")
        try:
            limit = int(budget)
        except (TypeError, ValueError, OverflowError):
            raise ShiftError("MISSING_FIELD", "budget") from None
        if limit < 0:
            raise ShiftError("MISSING_FIELD", "budget")
        return {"limit": limit, "spent": 0, "money": None, "deadline": None}
    adoptions, deadline, money = budget.get("adoptions"), budget.get("deadline"), None
    if adoptions is not None:
        adoptions = _number(adoptions, "adoptions", count=True)
    if deadline is not None:
        deadline = _number(deadline, "deadline")
        if deadline >= DEADLINE_MAX_EPOCH_SECS:
            raise ShiftError("BAD_BUDGET", "deadline: epoch seconds (UTC), not milliseconds")
    currency = budget.get("currency")
    if currency is not None or budget.get("amount") is not None:
        if currency is None or currency == "":
            raise ShiftError("MISSING_FIELD", "budget.currency")
        if not isinstance(currency, str) or not currency.strip():
            raise ShiftError("BAD_BUDGET", "budget.currency")
        if budget.get("amount") is None:
            raise ShiftError("MISSING_FIELD", "budget.amount")
        amount = _number(budget["amount"], "amount")
        freeze_at = amount if budget.get("freeze_at") is None else _number(budget["freeze_at"],
                                                                            "freeze_at")
        if not 0 < freeze_at <= amount:
            raise ShiftError("BAD_BUDGET", "0 < freeze_at <= amount")
        baseline = budget.get("baseline")
        money = {"currency": currency, "limit": amount, "freeze_at": freeze_at,
                 "baseline": None if baseline is None else _number(baseline, "baseline"),
                 "spent": 0.0,
                 "measured_at": None if baseline is None else now,
                 "source": budget.get("source"),
                 # set by the first reading the meter cannot explain; only the principal's
                 # rebaseline_spend clears it
                 "inconsistent_at": None}
    if adoptions is None and money is None and deadline is None:
        raise ShiftError("MISSING_FIELD", "budget")
    return {"limit": adoptions, "spent": 0,
            "money": money, "deadline": deadline}


def _heartbeat(capabilities):
    """The holder's own scheduled wakeup. `transport` is what the host adapter declares
    (OMP: a background job whose completion starts a follow-up turn); the rest is set by
    arm_heartbeat and cleared by the tick that consumes it."""
    return {"transport": (capabilities or {}).get("heartbeat_transport"), "job_ref": None,
            "armed_at": None, "fires_at": None, "bound_target": None}


def open_shift(*, shift_id, principal, scope, backlog, capacity, budget, holder,
               supervisor_target, now, lease_secs, mantras=None, capabilities=None,
               successor_policy=None, team_seats=None):
    """Assume a shift in ONE call from the principal's intake. Every field the contract needs
    is required; none is guessed.

    scope: a string or a non-empty list of strings. backlog: a reference to the principal's
    explicit list (path#section, URL, tracker query), or None ONLY when no list was given
    (then adoption rules apply). budget: see _new_budget."""
    for name, value in (("shift_id", shift_id), ("principal", principal),
                        ("holder", holder), ("supervisor_target", supervisor_target)):
        if not value:
            raise ShiftError("MISSING_FIELD", name)
    scope = _check_scope(scope)
    if backlog is not None and not (isinstance(backlog, str) and backlog.strip()):
        raise ShiftError("BAD_BACKLOG", "a reference string, or None only when no list was given")
    if capacity is None or int(capacity) < 1:
        raise ShiftError("MISSING_FIELD", "capacity")
    budget = _new_budget(budget, now)
    explicit = [m for m in (mantras or []) if isinstance(m, str) and m.strip()]
    state = {
        "schema": SCHEMA,
        "shift_id": shift_id,
        "principal": principal,
        "scope": scope,
        "backlog": backlog,  # None = not given: adopt; a reference = given: start_item
        "capacity": int(capacity),
        "budget": budget,
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
        # Admission closes when persistence fails or preflight freezes new work.
        "admission": {"open": True, "reason": None},
        "save_seq": 0,  # bumped by every autosave attempt (continuity.autosave)
        # Child checkpoints: id -> {"ref", "sha256", "received"}; the child keeps its own file.
        "children": {},
        "conflict_log": {},
        # The holder's OWN team. Roster states: admitted -> active -> draining -> retired.
        "team": {"seats": int(team_seats) if team_seats else int(capacity), "members": {}},
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
        "heartbeat": _heartbeat(capabilities),
        "stop": None,  # how the shift ended: cutoff (holder) or principal stop / revoke
        "log": [_opened_entry(now, holder, budget)],
    }
    return state


def _opened_entry(now, holder, budget):
    entry = {"at": now, "event": "shift_opened", "holder": holder}
    if budget["deadline"] is not None:
        entry["deadline_utc"] = _utc(budget["deadline"])  # echo: the unit and zone are visible
    return entry


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


def migrate(state):
    """Bring a state@1 (v0.2.0) file to state@2: additive and idempotent. Anything that is
    not an on-call-shift state of a known schema is refused, never migrated."""
    if (not isinstance(state, dict)
            or state.get("schema") not in (SCHEMA,) + LEGACY_SCHEMAS
            or not isinstance(state.get("budget"), dict)):
        raise ShiftError("SCHEMA_MISMATCH", str(state.get("schema") if isinstance(state, dict)
                                                else type(state).__name__))
    state["schema"] = SCHEMA
    state["budget"].setdefault("money", None)
    state["budget"].setdefault("deadline", None)
    if isinstance(state["budget"]["money"], dict):
        state["budget"]["money"].setdefault("inconsistent_at", None)
    state.setdefault("heartbeat", _heartbeat(None))
    state.setdefault("stop", None)
    return state


def load(path):
    with open(path, encoding="utf-8") as handle:
        state = json.load(handle)
    return migrate(state)


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
            "recovery": "arm the host's self-wakeup for the holder (arm_heartbeat, at most half "
                        "a lease ahead) and bind it to the exact supervisor; with no host "
                        "wakeup, report what is in flight and that the shift is unobserved "
                        "until the next turn; never claim coverage",
            "always_on_claim": False}


def apply_tick(state, actor, event_id, now, *, generation, spend_total=None):
    """A tick is evidence the clock ran and the holder is alive. It notifies nobody. A new tick
    renews the lease, consumes the heartbeat it came from, records the spend the host measured
    (`spend_total`, a running total) and freezes admission at the cutoff. A replayed id has no
    effect. Everything is validated before the first change, so a tick is never half applied:
    a reading that is not a number freezes admission like any inconsistent reading."""
    _require_holder(state, actor, now, generation)
    if spend_total is not None and not state["budget"]["money"]:
        raise ShiftError("NO_MONEY_BUDGET", "the principal gave no money cap")
    reading = None if spend_total is None else _reading(spend_total)
    if event_id in state["processed_events"]:
        return state, None
    state["processed_events"].append(event_id)
    state["cursor"] = {"seq": state["cursor"]["seq"] + 1, "last_event_id": event_id}
    state["lease"]["expires_at"] = now + state["lease"]["lease_secs"]
    if state["heartbeat"]["job_ref"] is not None and state["heartbeat"]["job_ref"] == event_id:
        state["heartbeat"].update(job_ref=None, armed_at=None, fires_at=None)
    if reading is not None:
        _record_spend(state, reading, now)
    _freeze_at_cutoff(state, now)
    effect = {"signal": "tick", "event_id": event_id, "at": now,
              "notification": "NOT_SENT_BY_TIMER", "execution": "NOT_REQUESTED"}
    state["effects"].append(effect)
    return state, effect


# --------------------------------------------------------------------------- budget, cutoff

def cutoff_reason(state, now):
    """The principal's own end of the shift: its deadline, or measured spend at the freeze
    threshold. None while neither is reached."""
    budget = state["budget"]
    if budget.get("deadline") is not None and now >= budget["deadline"]:
        return "DEADLINE_REACHED"
    money = budget.get("money")
    if money and money["spent"] >= money["freeze_at"]:
        return "SPEND_CAP_REACHED"
    return None


def _spend_block(state, now):
    """A money cap counts only on a fresh, trusted measurement. An inconsistent or unreadable
    meter (sticky until the principal's rebaseline_spend), none yet, or one older than a
    lease blocks new work (fail closed)."""
    money = state["budget"].get("money")
    if not money:
        return None
    if money["inconsistent_at"] is not None:
        return "SPEND_UNMEASURABLE"
    if money["measured_at"] is None:
        return "SPEND_NOT_MEASURED"
    if now - money["measured_at"] > state["lease"]["lease_secs"]:
        return "SPEND_MEASUREMENT_STALE"
    return None


def _admission_block(state, now):
    """Why no new item may start now, or None. Shared by select_next, adopt and start_item."""
    if not state["admission"]["open"]:
        return "ADMISSION_FROZEN"
    blocked = cutoff_reason(state, now) or _spend_block(state, now)
    if blocked:
        return blocked
    limit = state["budget"]["limit"]
    if limit is not None and state["budget"]["spent"] >= limit:
        return "BUDGET_EXHAUSTED"
    if len(state["in_flight"]) >= state["capacity"]:
        return "CAPACITY_FULL"
    return None


def _freeze(state, reason):
    """Close admission, never overwriting an earlier freeze reason, except POSTFLIGHT: that is
    the holder's own end-of-turn bookkeeping, which the next turn lifts, so a later safety
    freeze (spend, cutoff) replaces it and the lift can no longer reopen admission."""
    if state["admission"]["open"] or state["admission"]["reason"] == "POSTFLIGHT":
        state["admission"] = {"open": False, "reason": reason}


def _freeze_at_cutoff(state, now):
    reason = cutoff_reason(state, now)
    if reason:
        _freeze(state, reason)
    return reason


def _reading(value):
    """A meter reading as a float, or NaN for anything that is not one (None, text,
    overflow). Never raises, so a caller can validate before it changes anything."""
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return math.nan


def _unmeasurable(state, now):
    money = state["budget"]["money"]
    if money["inconsistent_at"] is None:
        money["inconsistent_at"] = now
    _freeze(state, "SPEND_MEASUREMENT_INCONSISTENT")
    return {"recorded": False, "reason": "SPEND_MEASUREMENT_INCONSISTENT",
            "spent": money["spent"]}


def _record_spend(state, measured_total, now, source=None):
    money = state["budget"]["money"]
    total = _reading(measured_total)
    if money["inconsistent_at"] is not None:
        # sticky: only the principal's rebaseline_spend trusts this meter again
        return {"recorded": False, "reason": "SPEND_UNMEASURABLE", "spent": money["spent"]}
    if not math.isfinite(total) or total < 0:
        # NaN, infinity, a negative or an unreadable total is not a measurement. Fail closed.
        return _unmeasurable(state, now)
    if money["baseline"] is None:
        # first reading of this meter (at open, or the new holder's after relief/takeover):
        # spend so far is kept and the delta continues from it
        money.update(baseline=round(total - money["spent"], 6), measured_at=now)
    else:
        spent = round(total - money["baseline"], 6)
        if spent < money["spent"]:
            # a running total never goes down: another source or a reset. Fail closed.
            return _unmeasurable(state, now)
        money.update(spent=spent, measured_at=now)
    if source:
        money["source"] = source
    return {"recorded": True, "reason": None, "spent": money["spent"],
            "left": round(money["freeze_at"] - money["spent"], 6),
            "cutoff": _freeze_at_cutoff(state, now)}


def record_spend(state, actor, measured_total, now, *, generation, source=None):
    """Record the host's measured running total of spend (for example the session cost
    ledger). The first reading is the baseline; spend is the delta from it. At the freeze
    threshold admission closes by itself. A reading that goes down, or one that is not a
    number (pass None when the meter cannot be read), makes the meter SPEND_UNMEASURABLE
    until the principal's rebaseline_spend."""
    _require_holder(state, actor, now, generation)
    if not state["budget"]["money"]:
        raise ShiftError("NO_MONEY_BUDGET", "the principal gave no money cap")
    return _record_spend(state, measured_total, now, source)


def rebaseline_spend(state, by, measured_total, now, *, generation):
    """The principal trusts the meter again: this reading becomes the new baseline and the
    spend already counted is KEPT (baseline = reading - spent), so a reset or a new ledger
    never refunds the cap. Clears SPEND_UNMEASURABLE and lifts only the freeze it caused."""
    if by != state["principal"]:
        return {"rebaselined": False, "reason": "NOT_AUTHORIZED_TO_REBASELINE"}
    if generation != state["generation"]:
        return {"rebaselined": False, "reason": "STALE_GENERATION"}
    if state["status"] not in (ACTIVE, HANDOFF_PENDING):
        return {"rebaselined": False, "reason": "SHIFT_NOT_ACTIVE"}
    money = state["budget"]["money"]
    if not money:
        return {"rebaselined": False, "reason": "NO_MONEY_BUDGET"}
    total = _reading(measured_total)
    if not math.isfinite(total) or total < 0:
        return {"rebaselined": False, "reason": "SPEND_MEASUREMENT_INCONSISTENT"}
    money.update(baseline=round(total - money["spent"], 6), measured_at=now,
                 inconsistent_at=None)
    state["log"].append({"at": now, "event": "spend_rebaselined", "by": by,
                         "spent": money["spent"]})
    if state["admission"]["reason"] == "SPEND_MEASUREMENT_INCONSISTENT":
        cutoff = cutoff_reason(state, now)
        if cutoff:
            state["admission"] = {"open": False, "reason": cutoff}
        elif any(child.get("pending") for child in state["children"].values()):
            # a child failure hid behind this freeze: it is now the cause (recover_child)
            state["admission"] = {"open": False, "reason": "CHILD_PERSISTENCE_FAILED"}
        else:
            state["admission"] = {"open": True, "reason": None}
    else:
        _freeze_at_cutoff(state, now)
    return {"rebaselined": True, "reason": None, "spent": money["spent"]}


def _new_holder_meter(state):
    """Relief or takeover: the new holder reads its own ledger (on OMP each session has one),
    so its first reading re-baselines and keeps the spend already counted. An unmeasurable
    meter stays unmeasurable: only the principal's rebaseline_spend clears it."""
    money = state["budget"]["money"]
    if money:
        money.update(baseline=None, measured_at=None)


# --------------------------------------------------------------------------- work loop

def heartbeat_armed(state, now):
    """An armed heartbeat that will wake the holder before its lease lapses and no later than
    the deadline. Anything else counts as not armed."""
    heartbeat, deadline = state["heartbeat"], state["budget"]["deadline"]
    return (heartbeat["job_ref"] is not None
            and now < heartbeat["fires_at"] < state["lease"]["expires_at"]
            and (deadline is None or heartbeat["fires_at"] <= deadline))


def arm_heartbeat(state, actor, now, *, generation, transport, job_ref, fires_at,
                  bound_target=None):
    """Record the self-wakeup the holder armed before idling (OMP: an async background job
    whose completion starts a follow-up turn in the holder's session). It must fire within
    half a lease; arming renews the lease (the holder is acting), so the holder always wakes,
    ticks and renews before the lease can lapse. Bound to the exact supervisor it is also a
    SUPPORTED wakeup; it never downgrades a wakeup the host already bound to the supervisor.
    It launches nothing by itself."""
    _require_holder(state, actor, now, generation)
    if not transport or not job_ref:
        raise ShiftError("MISSING_FIELD", "job_ref" if transport else "transport")
    if fires_at is None or fires_at <= now:
        raise ShiftError("HEARTBEAT_NOT_IN_FUTURE", str(fires_at))
    if fires_at - now > state["lease"]["lease_secs"] / 2:
        raise ShiftError("HEARTBEAT_AFTER_HALF_LEASE", str(fires_at))
    deadline = state["budget"]["deadline"]
    if deadline is not None and fires_at > deadline:
        raise ShiftError("HEARTBEAT_AFTER_DEADLINE", "the deadline is the last wake: close then")
    state["lease"]["expires_at"] = now + state["lease"]["lease_secs"]
    state["heartbeat"] = {"transport": transport, "job_ref": job_ref, "armed_at": now,
                          "fires_at": fires_at, "bound_target": bound_target}
    if state["wakeup"]["mode"] != "SUPPORTED":
        state["wakeup"] = classify_wakeup({"wakeup_transport": transport,
                                           "bound_target": bound_target},
                                          state["supervisor_target"])
    state["log"].append({"at": now, "event": "heartbeat_armed", "job_ref": job_ref,
                         "fires_at": fires_at})
    return state


def may_yield(state, actor, now, *, generation, eligible):
    """The work loop's exit gate (read-only). `eligible`: select_next just offered an item to
    start or adopt. The holder ends its turn only on {"yield": True}; otherwise it does `next`
    (dispatch, record_spend, arm_heartbeat, close_at_cutoff) and asks again. A meter that is
    only stale never blocks a yield while a heartbeat is armed: the wake re-measures. An
    unmeasurable meter is a degraded exit, never a loop."""
    if generation is None:
        raise ShiftError("GENERATION_REQUIRED", actor)
    if state["status"] not in (ACTIVE, HANDOFF_PENDING):
        return {"yield": True, "reason": "SHIFT_ENDED", "next": None}
    if generation != state["generation"] or actor != state["holder"]:
        return {"yield": True, "reason": "FENCED", "next": None}
    cutoff = cutoff_reason(state, now)
    if cutoff:
        return {"yield": False, "reason": cutoff, "next": "close_at_cutoff"}
    if not lease_valid(state, actor, now):
        return {"yield": True, "reason": "LEASE_EXPIRED", "next": "report_degraded"}
    unmeasured = _spend_block(state, now)
    if unmeasured == "SPEND_UNMEASURABLE":
        # degraded exit: no new item and no new wake (each would be unmeasured spend) until
        # the principal's rebaseline_spend; in-flight work and the deadline stand
        return {"yield": True, "reason": "SPEND_UNMEASURABLE", "next": "report_degraded"}
    if eligible:
        if unmeasured:
            return {"yield": False, "reason": unmeasured, "next": "record_spend"}
        return {"yield": False, "reason": "ELIGIBLE_WORK", "next": "dispatch"}
    if heartbeat_armed(state, now):
        return {"yield": True, "reason": "HEARTBEAT_ARMED", "next": None,
                "until": state["heartbeat"]["fires_at"]}
    if unmeasured:
        return {"yield": False, "reason": unmeasured, "next": "record_spend"}
    fire_by = now + state["lease"]["lease_secs"] / 2
    if state["budget"]["deadline"] is not None:
        fire_by = min(fire_by, state["budget"]["deadline"])
    if not state["heartbeat"]["transport"]:
        # no host wakeup declared. On OMP that means `capabilities` was omitted at open: the
        # holder arms anyway (arm_heartbeat with its transport, by fire_by), never postflight
        return {"yield": True, "reason": "NO_HOST_WAKEUP", "next": "postflight",
                "fire_by": fire_by}
    return {"yield": False, "reason": "NO_WAKEUP_ARMED", "next": "arm_heartbeat",
            "fire_by": fire_by}


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
    # A4: union keys whose items link each other's refs (issue <-> PR with different keys).
    parent = {}

    def root(key):
        while parent.setdefault(key, key) != key:
            key = parent[key]
        return key

    ref_key = {}
    for result in connector_results:
        for item in result.get("items") or []:
            if item.get("ref") and item.get("intent_key"):
                ref_key[item["ref"]] = item["intent_key"]
                root(item["intent_key"])
    for result in connector_results:
        for item in result.get("items") or []:
            for link in item.get("links") or []:
                if link in ref_key and item.get("intent_key"):
                    a, b = sorted((root(item["intent_key"]), root(ref_key[link])))
                    parent[b] = a
    aliases = {k: root(k) for k in list(parent) if root(k) != k}
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
            key = aliases.get(key, key)
            target = merged.setdefault(key, {
                "intent_key": key, "refs": [], "assignee": None, "in_flight_by": None,
                "gate": None, "gates": [], "gut": 0, "raci": {}})
            if item.get("gate") and item["gate"] not in target["gates"]:
                target["gates"].append(dict(item["gate"]))  # every source's gate is kept
            for ref in [item.get("ref")] + list(item.get("links") or []):
                if ref and ref not in target["refs"]:
                    target["refs"].append(ref)
            for field in ("assignee", "in_flight_by", "gate"):
                if item.get(field) and not target[field]:
                    target[field] = item[field]
                elif (field != "gate" and item.get(field) and target[field]
                      and item[field] != target[field]):
                    # Two sources disagree on who owns it: keep both, adopt nothing.
                    target.setdefault("conflicts", []).append(
                        {"field": field, "values": sorted({target[field], item[field]})})
            target["gut"] = max(target["gut"], int(item.get("gut") or 0))
            for role in ("driver", "responsible", "approver", "consulted", "informed"):
                value = (item.get("raci") or {}).get(role)
                if value and role not in target["raci"]:
                    target["raci"][role] = value
    for item in merged.values():
        for role in ("driver", "responsible", "approver", "consulted", "informed"):
            item["raci"].setdefault(role, "unknown")  # never invented
    every_connector_empty = bool(connectors) and all(c["status"] == "empty" for c in connectors)
    for alias, canonical in aliases.items():
        merged[canonical].setdefault("aliases", []).append(alias)
    return {"items": merged, "connectors": connectors, "aliases": aliases,
            "queue_empty": every_connector_empty and not merged}


def _ineligible(state, item, actor):
    """Why an item may not be adopted by `actor` now, or None. Shared by select and adopt."""
    if item["in_flight_by"] and item["in_flight_by"] != actor:
        return "IN_FLIGHT_BY_OTHER"
    if item["assignee"] and item["assignee"] != actor:
        return "OWNED_BY_OTHER"
    if item.get("conflicts"):
        return "OWNERSHIP_CONFLICT"
    recorded = state["gates"].get(item["intent_key"])
    if recorded and recorded.get("state") != "granted":
        return "HUMAN_GATE"
    sources = item.get("gates") or ([item["gate"]] if item["gate"] else [])
    for gate in sources:
        # Only the same decider's own recorded grant supersedes its connector copy
        # (set_gate guarantees a recorded grant was decided by its `by`).
        if recorded and gate.get("by") and recorded.get("by") == gate.get("by"):
            continue
        if gate.get("state") != "granted":
            return "HUMAN_GATE"  # fail closed: any open gate from any source blocks
    return None


def select_next(state, backlog, actor, now, *, generation):
    """Pick ONE eligible item, or return a reasoned wait. Never invents work. The action is
    `start` (start_item) for the principal's given list, `adopt` otherwise, or
    `reopen_admission` when only the holder's own end-of-turn POSTFLIGHT freeze from its last
    turn stands in the way (continuity.reopen_admission, then select again)."""
    _require_holder(state, actor, now, generation)
    if state.get("incident"):
        return {"action": "handle_incident", "incident": state["incident"]["id"]}
    blocked = _admission_block(state, now)
    if (blocked == "ADMISSION_FROZEN" and state["status"] == ACTIVE
            and state["admission"]["reason"] == "POSTFLIGHT" and not cutoff_reason(state, now)
            and not any(child.get("pending") for child in state["children"].values())):
        return {"action": "reopen_admission", "reason": "POSTFLIGHT"}
    if blocked:
        return {"action": "wait", "reason": blocked}
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
        action = "start" if _given_list(state) else "adopt"
        return {"action": action, "intent_key": chosen["intent_key"], "skipped": skipped}
    blind = [c["connector"] for c in backlog["connectors"]
             if c["status"] in ("denied", "unavailable", "partial")]
    if blind:
        return {"action": "wait", "reason": "CONNECTORS_NOT_READABLE", "connectors": blind,
                "skipped": skipped}
    return {"action": "wait", "reason": "NO_ELIGIBLE_ITEM", "skipped": skipped}


def _given_list(state):
    return bool(state["backlog"]) and not state.get("backlog_exhausted")


def _take(state, actor, intent_key, backlog, now, via):
    """Take one item into the shift once; a replay adds nothing. Every limit is checked here,
    before any mutation: select_next is advice only."""
    intent_key = (backlog.get("aliases") or {}).get(intent_key, intent_key)
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
    blocked = _admission_block(state, now)
    if blocked == "ADMISSION_FROZEN":
        raise ShiftError(blocked, str(state["admission"]["reason"]))
    if blocked:
        raise ShiftError(blocked, intent_key)
    state["adopted"][intent_key] = {"refs": list(item["refs"]), "at": now, "via": via}
    state["in_flight"].append(intent_key)
    state["budget"]["spent"] += 1
    return state, True


def adopt(state, actor, intent_key, backlog, now, *, generation):
    """Adopt one item found in the trackers, only when no list was given or it is done."""
    _require_holder(state, actor, now, generation)
    if _given_list(state):
        raise ShiftError("BACKLOG_GIVEN", "the principal gave a list: use start_item")
    return _take(state, actor, intent_key, backlog, now, "adoption")


def start_item(state, actor, intent_key, backlog, now, *, generation):
    """Start one item of the principal's GIVEN list (normalized with normalize_backlog) and
    put it in flight, with the same gate, owner, in-flight, admission, cutoff, budget and
    capacity checks as adopt. Without a given list, items come from adopt instead."""
    _require_holder(state, actor, now, generation)
    if not _given_list(state):
        raise ShiftError("NO_BACKLOG_GIVEN", "no list given (or it is done): use adopt")
    return _take(state, actor, intent_key, backlog, now, "backlog")


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
    decider = current.get("by") if current else gate.get("by")
    if current and gate.get("decided_by") != decider:
        raise ShiftError("GATE_DECIDER_MISMATCH", intent_key)
    if gate.get("state") == "granted":
        # A grant must name its decider, and the holder is never that decider.
        if not decider or gate.get("decided_by") != decider:
            raise ShiftError("GATE_DECIDER_MISMATCH", intent_key)
        if decider in (actor, state["holder"]):
            raise ShiftError("SELF_GRANT_REFUSED", intent_key)
    state["gates"][intent_key] = dict(gate, by=decider)
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
    # The outgoing holder's heartbeat wakes the outgoing session, not the successor's.
    state["heartbeat"] = _heartbeat({"heartbeat_transport": state["heartbeat"]["transport"]})
    _new_holder_meter(state)
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


def _end(state, kind, by, reason, now):
    """Terminal transition shared by a principal stop/revoke and a holder cutoff close."""
    left = sorted(state["in_flight"])
    state["status"] = REVOKED if kind == "principal_revoke" else STOPPED
    state["lease"]["expires_at"] = min(state["lease"]["expires_at"], now)
    state["stop"] = {"kind": kind, "by": by, "reason": reason, "at": now, "in_flight_left": left}
    event = {"cutoff": "closed_at_cutoff", "principal_stop": "stopped",
             "principal_revoke": "revoked"}[kind]
    entry = {"at": now, "event": event, "by": by, "in_flight_left": left}
    if reason:
        entry["reason"] = reason
    state["log"].append(entry)


def stop_shift(state, by, now, *, revoke=False):
    """Legitimate stop or revocation: only the principal may end the shift without relief."""
    if by != state["principal"]:
        raise ShiftError("NOT_AUTHORIZED_TO_STOP", by)
    _end(state, "principal_revoke" if revoke else "principal_stop", by, None, now)
    return state


def close_at_cutoff(state, actor, now, *, generation):
    """The holder ends the shift at the principal's OWN cutoff (deadline or spend threshold
    given at intake): STOPPED with that reason and the in-flight work left, distinct from a
    principal stop or revocation. Allowed after the lease lapsed (the holder may have been
    suspended), never before the cutoff, and never to a stale or another holder."""
    if state["status"] not in (ACTIVE, HANDOFF_PENDING):
        raise ShiftError("SHIFT_NOT_ACTIVE", state["status"])
    if generation is None:
        raise ShiftError("GENERATION_REQUIRED", actor)
    if generation != state["generation"]:
        raise ShiftError("STALE_GENERATION", f"{generation} != {state['generation']}")
    if actor != state["holder"] or actor != state["lease"]["holder"]:
        raise ShiftError("NOT_THE_HOLDER", str(actor))
    reason = cutoff_reason(state, now)
    if not reason:
        raise ShiftError("NOT_AT_CUTOFF", "only the principal ends a shift early")
    _freeze(state, reason)
    state["handoff"] = None
    _end(state, "cutoff", actor, reason, now)
    return {"closed": True, "reason": reason, "in_flight_left": state["stop"]["in_flight_left"]}


# --------------------------------------------------------------------------- UDV

SATISFACTION = ("confirmed", "refused", "unknown")


def _delivery(state, intent_key):
    return state["deliveries"].setdefault(intent_key, {
        "technical_verified": False, "delivered_to_recipient": False,
        "satisfaction": "unknown", "recipient": None, "recipient_kind": None,
        "attempts": 0, "result_ref": None, "reservations": None, "reopened_as": None,
        "sent": []})


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
    if [result_ref, recipient] in record["sent"]:
        # Sent before (current or historical, e.g. r1 -> r2 -> r1): never again, and the
        # current delivery and its evidence stay untouched.
        return {"sent": False, "reason": "NO_RESEND_SAME_RESULT"}
    if record["attempts"] and (record["result_ref"], record["recipient"]) != (result_ref, recipient):
        # The accepted evidence was for another result or another person: it no longer applies.
        record.update(technical_verified=False, delivered_to_recipient=False,
                      satisfaction="unknown", reservations=None)
    record.update(recipient=recipient, recipient_kind=recipient_kind, result_ref=result_ref)
    record["sent"].append([result_ref, recipient])
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
        if record["satisfaction"] == "refused" and record["reopened_as"]:
            # Same rejection of the same delivered result, replayed: no second reopening.
            return {"recorded": False, "reason": "DUPLICATE_REJECTION",
                    "reopened_as": record["reopened_as"]}
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
    if not evidence.get("source") or not evidence.get("digest"):
        return {"changed": False, "reason": "EVIDENCE_WITHOUT_SOURCE", "choice": record["choice"]}
    fingerprint = f"{evidence.get('source')}#{evidence.get('digest')}"
    seen_digests = {f.rsplit("#", 1)[-1] for f in record["seen"]}
    if evidence["digest"] in seen_digests:  # same content under any source name = echo
        return {"changed": False, "reason": "REPEATED_EVIDENCE", "choice": record["choice"]}
    record["seen"].append(fingerprint)
    if evidence.get("supports") == record["choice"]:
        return {"changed": False, "reason": "SAME_CONCLUSION", "choice": record["choice"]}
    record["changes"].append({"from": record["choice"], "to": evidence.get("supports"),
                              "evidence": fingerprint, "lens": evidence.get("lens"), "at": now})
    record["choice"] = evidence.get("supports")
    return {"changed": True, "reason": None, "choice": record["choice"]}


# --------------------------------------------------------------------------- conflicts

def resolve_conflict(state, actor, conflict_id, *, facts, authorities, alternatives,
                     evidence, reversible, review_criterion, now, generation):
    """Record and settle a disagreement between sources or owners.

    authorities: {world: owner} (who may decide in each world, e.g. tracker, repo, org).
    alternatives: [{"id", "needs_human_authorization": bool}].
    evidence: [{"supports": alt id, "source", "digest", "verified": bool}].
    Never decided by majority or by the latest message: only VERIFIED evidence counts, and
    duplicates of one digest count once. A human authorization is never arbitrated, and
    owners who disagree across worlds are an authority conflict: only that effect is parked,
    the rest of the shift continues.
    """
    _require_holder(state, actor, now, generation)
    record = {"facts": list(facts), "authorities": dict(authorities),
              "alternatives": [dict(a) for a in alternatives], "reversible": bool(reversible),
              "review_criterion": review_criterion, "at": now}
    owners = {v for v in authorities.values() if v}
    human = [a["id"] for a in alternatives if a.get("needs_human_authorization")]
    if len(owners) > 1 or human:
        reason = "HUMAN_AUTHORIZATION_NOT_ARBITRATED" if human else "AUTHORITY_CONFLICT"
        record.update(decision=None, status="PARKED", reason=reason)
        state["parked"].append({"operation": conflict_id, "reason": reason,
                                "recovery_owner": sorted(owners) or None, "at": now})
    else:
        support = {}
        for item in evidence:
            if item.get("verified") and item.get("digest"):
                support.setdefault(item["supports"], set()).add(item["digest"])
        winners = [alt for alt, digests in support.items() if digests]
        if len(winners) == 1:
            record.update(decision=winners[0], status="RESOLVED", reason="VERIFIED_EVIDENCE",
                          evidence=sorted(support[winners[0]]))
        else:
            record.update(decision=None, status="OPEN",
                          reason="NO_VERIFIED_EVIDENCE" if not winners else "EVIDENCE_SPLIT")
    state["conflict_log"][conflict_id] = record
    return {"status": record["status"], "decision": record["decision"],
            "reason": record["reason"]}


# --------------------------------------------------------------------------- own team

RISK_ADMITTED = ("low", "medium")
CAPABILITY_DECISIONS = ("reuse", "configure", "extend", "create", "none")


def admit_member(state, actor, member_id, *, role, scope, risk, cost, now, generation,
                 persistent=False, review_at=None, disarm=None, kind="member",
                 decision="create", dependents=None, verification=None, expires_at=None):
    """Admit one capability to the holder's OWN roster: a team member or an own tool (skill,
    CLI, MCP, app, technique). By scope, risk and budget; ephemeral by default; persistent
    needs a review date and a disarm path. Every admission records its decision (reuse,
    configure, extend, create or none). Re-admitting is a no-op (no duplicate)."""
    _require_holder(state, actor, now, generation)
    if decision not in CAPABILITY_DECISIONS:
        raise ShiftError("BAD_DECISION", str(decision))
    if decision == "none":
        return {"admitted": False, "reason": "DECIDED_NOT_TO"}
    team = state["team"]
    if member_id in team["members"]:
        return {"admitted": False, "reason": "ALREADY_ADMITTED"}
    if scope != state["scope"]:
        return {"admitted": False, "reason": "OUT_OF_SCOPE"}
    if risk not in RISK_ADMITTED:
        return {"admitted": False, "reason": "RISK_TOO_HIGH"}
    limit = state["budget"]["limit"]
    if limit is not None and state["budget"]["spent"] + int(cost) > limit:
        return {"admitted": False, "reason": "BUDGET_EXCEEDED"}
    blocked = ("ADMISSION_FROZEN" if not state["admission"]["open"]
               else cutoff_reason(state, now) or _spend_block(state, now))
    if blocked:
        return {"admitted": False, "reason": blocked}
    active = [m for m in team["members"].values() if m["status"] != "retired"]
    if len(active) >= team["seats"]:
        return {"admitted": False, "reason": "SEATS_FULL"}
    if persistent and not (review_at and disarm):
        return {"admitted": False, "reason": "PERSISTENT_NEEDS_REVIEW_AND_DISARM"}
    state["budget"]["spent"] += int(cost)
    team["members"][member_id] = {
        "owner": state["shift_id"], "role": role, "scope": scope, "risk": risk,
        "cost": int(cost), "mode": "persistent" if persistent else "ephemeral",
        "review_at": review_at, "disarm": disarm, "status": "admitted", "in_flight": [],
        "admitted_at": now, "exit_receipt": None, "kind": kind, "decision": decision,
        "dependents": [dict(d) for d in (dependents or [])], "verification": verification,
        "expires_at": expires_at}
    return {"admitted": True, "reason": None}


def request_shared_change(state, actor, resource, action, now, *, generation, owner=None):
    """Owning tools or a team grants no power over SHARED resources. Any request to create or
    delete a resource this shift does not own is parked for its owner, never performed."""
    _require_holder(state, actor, now, generation)
    if action not in ("create", "delete"):
        raise ShiftError("BAD_ACTION", str(action))
    state["parked"].append({"operation": f"{action}:{resource}",
                            "reason": "SHARED_RESOURCE_NOT_OWNED",
                            "recovery_owner": owner, "at": now})
    return {"done": False, "decision": "park", "reason": "SHARED_RESOURCE_NOT_OWNED"}


def _own_member(state, member_id):
    member = state["team"]["members"].get(member_id)
    if member is None:
        raise ShiftError("UNKNOWN_MEMBER", member_id)
    if member["owner"] != state["shift_id"]:
        raise ShiftError("NOT_YOUR_MEMBER", member_id)  # other owners are never touched
    return member


def assign_member(state, actor, member_id, intent_key, now, *, generation):
    _require_holder(state, actor, now, generation)
    member = _own_member(state, member_id)
    if member["status"] in ("draining", "retired"):
        return {"assigned": False, "reason": "MEMBER_" + member["status"].upper()}
    if intent_key not in member["in_flight"]:
        member["in_flight"].append(intent_key)
    member["status"] = "active"
    return {"assigned": True, "reason": None}


def member_done(state, actor, member_id, intent_key, now, *, generation):
    _require_holder(state, actor, now, generation)
    member = _own_member(state, member_id)
    if intent_key in member["in_flight"]:
        member["in_flight"].remove(intent_key)
    return {"done": True, "left": list(member["in_flight"])}


def retire_member(state, actor, member_id, now, *, generation):
    """Normal retirement: stop new work, drain what is in flight, then retire with an exit
    receipt. Idempotent: retiring a retired member changes nothing. History is kept."""
    _require_holder(state, actor, now, generation)
    member = _own_member(state, member_id)
    if member["status"] == "retired":
        return {"retired": True, "reason": "ALREADY_RETIRED", "receipt": member["exit_receipt"]}
    active_dependents = [d for d in member.get("dependents", []) if d.get("active")]
    if active_dependents:
        # Retiring would break someone relying on it: refuse; dependents are not touched.
        return {"retired": False, "reason": "DEPENDENTS_ACTIVE",
                "dependents": [d.get("id") for d in active_dependents]}
    if member["in_flight"]:
        member["status"] = "draining"
        return {"retired": False, "reason": "DRAINING", "in_flight": list(member["in_flight"])}
    member["status"] = "retired"
    member["exit_receipt"] = {"member": member_id, "cursor_seq": state["cursor"]["seq"],
                              "generation": state["generation"], "at": now}
    return {"retired": True, "reason": None, "receipt": member["exit_receipt"]}


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
    # A heartbeat armed by the lost holder would wake the lost session: never the claimant's.
    state["heartbeat"] = _heartbeat({"heartbeat_transport": state["heartbeat"]["transport"]})
    _new_holder_meter(state)
    state["log"].append({"at": now, "event": "taken_over", "from": previous, "to": claimant,
                         "generation": state["generation"], "nonce": policy["nonce"]})
    return {"taken_over": True, "reason": None, "generation": state["generation"],
            "nonce": policy["nonce"]}


def snapshot(state):
    return copy.deepcopy(state)
