"""on-call-shift watchdog: a separate, low-cost observer of ONE shift holder.

It keeps its own state, never writes the holder's state except through the engine's fencing
call, and never launches a model, a session or a timer. Process termination is limited to a
DISPOSABLE process whose identity is re-verified at the moment of action.

This module is logic plus tests. It is NOT an installed watchdog and NOT a wakeup transport.
Contract: ../references/continuity.md.
"""
from __future__ import annotations

import os
import signal
import subprocess

import shift_engine as se

SUSPECT, CONFIRMED, OK = "SUSPECT", "CONFIRMED", "OK"


def register(registry, scope, watchdog_id):
    """One watchdog per scope. A second one is refused (no recursive or double watchers)."""
    if scope in registry and registry[scope] != watchdog_id:
        return {"registered": False, "reason": "WATCHDOG_ALREADY_REGISTERED",
                "existing": registry[scope]}
    registry[scope] = watchdog_id
    return {"registered": True, "reason": None}


def new_watchdog(*, watchdog_id, scope, target_holder, generation, ack_timeout_secs,
                 misses_to_confirm, now):
    return {"watchdog_id": watchdog_id, "scope": scope, "target_holder": target_holder,
            "generation": generation, "ack_timeout_secs": int(ack_timeout_secs),
            "misses_to_confirm": int(misses_to_confirm), "pending": None,
            "last_ack_at": now, "misses": 0, "verdict": OK, "used_nonces": []}


def greet(wd, *, holder, generation, nonce, now):
    """Challenge sent at the holder's preflight. Bound to the exact holder and generation."""
    if nonce in wd["used_nonces"]:
        return {"greeted": False, "reason": "NONCE_REUSED"}
    if holder != wd["target_holder"] or generation != wd["generation"]:
        return {"greeted": False, "reason": "WRONG_TARGET_OR_GENERATION"}
    wd["used_nonces"].append(nonce)
    wd["pending"] = {"nonce": nonce, "sent_at": now}
    return {"greeted": True, "reason": None}


def ack(wd, *, nonce, holder, generation, now):
    """The holder's receipt. Correct, wrong or late are distinct verdicts."""
    pending = wd["pending"]
    if not pending or nonce != pending["nonce"]:
        return {"verdict": "REJECTED", "reason": "UNKNOWN_NONCE"}
    if holder != wd["target_holder"] or generation != wd["generation"]:
        return {"verdict": "REJECTED", "reason": "WRONG_TARGET_OR_GENERATION"}
    wd["pending"] = None
    if now - pending["sent_at"] > wd["ack_timeout_secs"]:
        return {"verdict": "LATE", "reason": "ACK_AFTER_TIMEOUT"}
    wd["last_ack_at"] = now
    wd["misses"] = 0
    wd["verdict"] = OK
    return {"verdict": OK, "reason": None}


def observe(wd, *, now, independent_evidence=False):
    """Silence alone is SUSPECT, never a failure. CONFIRMED needs repeated misses AND
    independent evidence (e.g. the host reports the process gone)."""
    pending = wd["pending"]
    if pending and now - pending["sent_at"] > wd["ack_timeout_secs"]:
        wd["misses"] += 1
        wd["pending"] = None
    if wd["misses"] == 0:
        wd["verdict"] = OK
    elif wd["misses"] >= wd["misses_to_confirm"] and independent_evidence:
        wd["verdict"] = CONFIRMED
    else:
        wd["verdict"] = SUSPECT
    return {"verdict": wd["verdict"], "misses": wd["misses"]}


def fence(wd, state, *, now):
    """Logical quarantine: on a CONFIRMED failure, expire the holder's lease and freeze
    admission. It sends no signal to any process. Succession then goes through the engine's
    single, consumable takeover."""
    if wd["verdict"] != CONFIRMED:
        return {"fenced": False, "reason": "NOT_CONFIRMED"}
    if state["holder"] != wd["target_holder"] or state["generation"] != wd["generation"]:
        return {"fenced": False, "reason": "TARGET_CHANGED"}
    state["lease"]["expires_at"] = min(state["lease"]["expires_at"], now)
    state["admission"] = {"open": False, "reason": "FENCED_BY_WATCHDOG"}
    state["log"].append({"at": now, "event": "fenced", "by": wd["watchdog_id"],
                         "holder": state["holder"], "generation": state["generation"]})
    return {"fenced": True, "reason": None}


# --------------------------------------------------------------------------- disposable process

def _ps(pid, field):
    try:
        out = subprocess.run(["ps", "-o", f"{field}=", "-p", str(pid)], capture_output=True,
                             text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None  # the host does not let us read the process table: identity unknown
    return out.stdout.strip() if out.returncode == 0 else None


def identify(pid):
    """Process identity now (start time and command line), or None when unknown."""
    start, command = _ps(pid, "lstart"), _ps(pid, "command")
    if not start or not command:
        return None
    return {"pid": pid, "start": start, "command": command}


def terminate_disposable(record, *, timeout=5):
    """Stop a process ONLY if it is the disposable child described by `record`, re-verified
    now. Required: marked disposable; our own unreaped child handle with the same pid (the
    kernel cannot reuse an unreaped child's pid); and, when the host exposes the process
    table, the same start time and our token in the command line. Anything else is refused
    and left alone. Graceful SIGTERM to that child only; never a group or global signal."""
    if not record.get("disposable"):
        return {"terminated": False, "reason": "NOT_DISPOSABLE"}
    proc = record.get("_popen")
    if proc is None:
        return {"terminated": False, "reason": "NOT_OWN_CHILD"}
    if proc.pid != record.get("pid"):
        return {"terminated": False, "reason": "PID_REUSED_OR_CHANGED"}
    if proc.poll() is not None:
        return {"terminated": False, "reason": "ALREADY_GONE"}
    now_id = identify(record["pid"])
    if now_id is not None and (now_id["start"] != record.get("start")
                               or record["token"] not in now_id["command"]):
        return {"terminated": False, "reason": "PID_REUSED_OR_CHANGED"}
    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"terminated": False, "reason": "DID_NOT_EXIT"}
    return {"terminated": True, "reason": None,
            "identity_check": "process-table" if now_id else "own-child-handle-only",
            "receipt": {"pid": record["pid"]}}


se.guard_now(globals())
