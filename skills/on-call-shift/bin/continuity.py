"""on-call-shift continuity: autosave per transition, child checkpoints, a handoff derived
from the snapshot, preflight/postflight per turn, and a readable diagnosis.

Stdlib only. No network, no model, no timer. The caller passes `now`.
Contract: ../references/continuity.md.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os

import shift_engine as se


def _canonical(state):
    return json.dumps(state, indent=2, sort_keys=True).encode("utf-8")


def snapshot_sha(state):
    return hashlib.sha256(_canonical(state)).hexdigest()


def _atomic_write(path, data):
    directory = os.path.dirname(os.path.abspath(path))
    tmp = os.path.join(directory, f".{os.path.basename(path)}.tmp")
    with open(tmp, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


# --------------------------------------------------------------------------- autosave

def autosave(state, path, *, writer=None):
    """Write the state atomically, keep the previous revision as `.prev`, write a `.sha256`
    sidecar, and read it back. Only a read-back hash match counts as saved. A failure closes
    admission and is reported; it is never reported as saved."""
    writer = writer or _atomic_write
    data = _canonical(state)
    digest = hashlib.sha256(data).hexdigest()
    try:
        if os.path.exists(path):
            with open(path, "rb") as old:
                writer(path + ".prev", old.read())
        writer(path, data)
        writer(path + ".sha256", digest.encode())
        with open(path, "rb") as back:
            if hashlib.sha256(back.read()).hexdigest() != digest:
                raise OSError("read-back hash mismatch")
    except OSError as err:
        state["admission"] = {"open": False, "reason": "PERSISTENCE_FAILED"}
        return {"saved": False, "reason": "PERSISTENCE_FAILED", "error": type(err).__name__}
    return {"saved": True, "reason": None, "sha256": digest}


def transition(state, path, fn, *args, writer=None, **kwargs):
    """Run one engine transition, then autosave. If the save fails, the in-memory state is
    rolled back to before the transition (nothing unsaved survives) and admission closes."""
    before = copy.deepcopy(state)
    result = fn(state, *args, **kwargs)
    saved = autosave(state, path, writer=writer)
    if not saved["saved"]:
        state.clear()
        state.update(before)
        state["admission"] = {"open": False, "reason": "PERSISTENCE_FAILED"}
    return result, saved


def reopen_admission(state, path, actor, now, *, generation, writer=None):
    """Recovery: admission reopens only after a save that reads back correctly."""
    se._require_holder(state, actor, now, generation)
    if state["admission"]["reason"] != "PERSISTENCE_FAILED":
        return {"reopened": False, "reason": "NOT_FROZEN_BY_PERSISTENCE"}
    trial = copy.deepcopy(state)
    trial["admission"] = {"open": True, "reason": None}
    saved = autosave(trial, path, writer=writer)
    if not saved["saved"]:
        return {"reopened": False, "reason": "PERSISTENCE_FAILED"}
    state["admission"] = {"open": True, "reason": None}
    return {"reopened": True, "reason": None, "sha256": saved["sha256"]}


def load_checked(path):
    """Load the newest revision whose hash matches; fall back to `.prev`; else fail."""
    try:
        with open(path, "rb") as handle:
            data = handle.read()
        with open(path + ".sha256", "rb") as handle:
            expected = handle.read().decode().strip()
        if hashlib.sha256(data).hexdigest() == expected:
            return json.loads(data), "current"
    except (OSError, ValueError):
        pass
    try:
        with open(path + ".prev", "rb") as handle:
            return json.loads(handle.read()), "previous"
    except (OSError, ValueError):
        raise se.ShiftError("NO_VALID_CHECKPOINT", path)


def checkpoint_child(parent, child_id, child_state, child_path, *, writer=None):
    """A child (leaf) keeps its own checkpoint file. The parent stores only a pointer, the
    hash and whether the save was received. Secrets and child logs never go to the parent."""
    saved = autosave(child_state, child_path, writer=writer)
    parent["children"][child_id] = {"ref": os.path.basename(child_path),
                                    "sha256": saved.get("sha256"),
                                    "received": saved["saved"]}
    if not saved["saved"]:
        parent["admission"] = {"open": False, "reason": "CHILD_PERSISTENCE_FAILED"}
    return saved


# --------------------------------------------------------------------------- handoff

def render_handoff(state, *, now, stale_after_secs):
    """Handoff-as-prompt derived from the snapshot only. Same state -> same text."""
    sha = snapshot_sha(state)
    last = max([e.get("at", 0) for e in state["log"]] or [0])
    stale = now - last > stale_after_secs
    udv = {k: se.udv_status(state, k)["pending"] or "DONE" for k in sorted(state["deliveries"])}
    lines = [
        f"# Handoff · shift {state['shift_id']}",
        "",
        f"- snapshot_sha256: {sha}",
        f"- generation: {state['generation']}",
        f"- status: {state['status']}",
        f"- holder: {state['holder']}",
        f"- cursor_seq: {state['cursor']['seq']}",
        f"- data: {'STALE' if stale else 'fresh'} (last transition at {last})",
        f"- admission: {'open' if state['admission']['open'] else 'frozen ' + str(state['admission']['reason'])}",
        f"- wakeup: {state['wakeup']['mode']} {state['wakeup']['reason'] or ''}".rstrip(),
        f"- continuity: {state['continuity']['mode']} {state['continuity']['reason'] or ''}".rstrip(),
        f"- in_flight: {', '.join(sorted(state['in_flight'])) or 'none'}",
        f"- gates: {', '.join(sorted(state['gates'])) or 'none'}",
        f"- pending_events: {', '.join(sorted(state['pending_events'])) or 'none'}",
        f"- udv: {', '.join(f'{k}={v}' for k, v in udv.items()) or 'none'}",
        f"- children: {', '.join(f'{k}={v['received']}' for k, v in sorted(state['children'].items())) or 'none'}",
        "",
        "To take over: ACK with kind=handoff_ack, generation, cursor_seq, in_flight and gates "
        "exactly as above. Silence is not relief.",
    ]
    return "\n".join(lines) + "\n"


def write_handoff(state, path, *, now, stale_after_secs, writer=None):
    text = render_handoff(state, now=now, stale_after_secs=stale_after_secs).encode("utf-8")
    writer = writer or _atomic_write
    try:
        if os.path.exists(path):
            with open(path, "rb") as old:
                writer(path + ".prev", old.read())
        writer(path, text)
    except OSError:
        state["admission"] = {"open": False, "reason": "PERSISTENCE_FAILED"}
        return {"written": False, "reason": "PERSISTENCE_FAILED"}
    return {"written": True, "sha256": hashlib.sha256(text).hexdigest()}


# --------------------------------------------------------------------------- pre / post

def preflight(state, actor, now, *, generation, saved_sha=None, watchdog=None,
              watchdog_ack=None, host=None, last_preflight=None):
    """Checks at every wake. Returns findings and ONE graded action:
    observe -> reduce -> freeze -> save -> propose_handoff. Missing metrics are 'unknown'.

    watchdog: a watchdog view from watchdog.greet() for this turn (None = no watchdog);
    watchdog_ack: the result of watchdog.ack() for that greeting, or None if none arrived.
    """
    findings = {}
    try:
        se._require_holder(state, actor, now, generation)
        findings["identity"] = "ok"
    except se.ShiftError as err:
        return {"action": "observe_only", "findings": {"identity": err.code}}
    findings["lease_left_secs"] = state["lease"]["expires_at"] - now
    budget = state["budget"]
    findings["budget_left"] = budget["limit"] - budget["spent"]
    findings["in_flight"] = len(state["in_flight"])
    last = max([e.get("at", 0) for e in state["log"]] or [0])
    findings["clock"] = "BACKWARDS" if now < last else "ok"
    current = snapshot_sha(state)
    findings["saved_sha"] = ("unknown" if saved_sha is None
                             else "match" if saved_sha == current else "DIVERGED")
    if last_preflight is not None:
        findings["progress"] = ("NONE" if last_preflight.get("cursor_seq") == state["cursor"]["seq"]
                                and last_preflight.get("in_flight") == findings["in_flight"]
                                else "ok")
    else:
        findings["progress"] = "unknown"
    host = host or {}
    for key in ("memory_pressure", "disk_free_ratio", "queue_depth"):
        findings[key] = host.get(key, "unknown")
    if watchdog is None:
        findings["watchdog"] = "ABSENT"
    elif watchdog_ack is None:
        findings["watchdog"] = "NO_ACK"
    else:
        findings["watchdog"] = watchdog_ack["verdict"]
    findings["cursor_seq"] = state["cursor"]["seq"]
    # graded action, strongest finding wins
    if findings["clock"] == "BACKWARDS" or findings["saved_sha"] == "DIVERGED":
        action = "freeze"
    elif findings["lease_left_secs"] <= 0 or findings["budget_left"] <= 0:
        action = "propose_handoff"
    elif not state["admission"]["open"]:
        action = "save"
    elif findings["progress"] == "NONE":
        action = "reduce"
    else:
        action = "observe"
    if action == "freeze":
        state["admission"] = {"open": False, "reason": "PREFLIGHT_INCONSISTENT"}
    degraded = findings["watchdog"] in ("ABSENT", "NO_ACK", "LATE", "REJECTED")
    return {"action": action, "findings": findings,
            "backup": "DEGRADED" if degraded else "OK"}


def postflight(state, actor, now, *, generation, successor=None, ack=None):
    """End of turn: stop new admissions, report what is open, and hand off only on an ACK.
    Without a valid ACK the turn ends WITHOUT relief, and says so."""
    se._require_holder(state, actor, now, generation)
    state["admission"] = {"open": False, "reason": "POSTFLIGHT"}
    report = {
        "snapshot_sha256": snapshot_sha(state),
        "cursor_seq": state["cursor"]["seq"],
        "in_flight": sorted(state["in_flight"]),
        "gates": sorted(state["gates"]),
        "pending_events": sorted(state["pending_events"]),
        "udv": {k: se.udv_status(state, k) for k in sorted(state["deliveries"])},
    }
    if successor is None:
        return dict(report, relief="NO_SUCCESSOR_TURN_ENDS_WITHOUT_RELIEF")
    if state["status"] != se.HANDOFF_PENDING:
        se.propose_handoff(state, actor, successor, now, generation=generation)
    if ack is None:
        return dict(report, relief="AWAITING_SUCCESSOR_ACK")
    out = se.accept_handoff(state, ack, now)
    if out["relieved"]:
        state["admission"] = {"open": True, "reason": None}  # new holder admits
    return dict(report, relief="RELIEVED" if out["relieved"] else out["reason"])


# --------------------------------------------------------------------------- diagnosis

def diagnose(state, *, now):
    """A readable state with no private data: modes, counts and reasons only."""
    return {
        "shift_id": state["shift_id"],
        "status": state["status"],
        "generation": state["generation"],
        "lease_left_secs": state["lease"]["expires_at"] - now,
        "cursor_seq": state["cursor"]["seq"],
        "admission": dict(state["admission"]),
        "wakeup": {"mode": state["wakeup"]["mode"], "reason": state["wakeup"]["reason"]},
        "continuity": dict(state["continuity"]),
        "counts": {"in_flight": len(state["in_flight"]), "gates": len(state["gates"]),
                   "pending_events": len(state["pending_events"]),
                   "deliveries": len(state["deliveries"]), "children": len(state["children"]),
                   "parked": len(state["parked"])},
        "udv_pending_reasons": sorted({se.udv_status(state, k)["pending"] or "DONE"
                                       for k in state["deliveries"]}),
        "incident_open": bool(state.get("incident")),
        "budget": dict(state["budget"]),
    }
