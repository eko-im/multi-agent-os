#!/usr/bin/env python3
"""scoreboard.py — deterministic HOTL/HITL completeness scoreboard for `session-wrapup`.

Reads a JSON item list (decisions, actions, tasks of this session) and prints the three
numbers the skill reports — %HOTL, %HITL, %session — always as numerator/denominator.

It is a GATE, not a calculator: it refuses inputs that would let the agent fake progress.

  exit 0  ok (and, with --gate close, the close-out gate is met)
  exit 2  usage / unreadable input
  exit 2  also: --gate close without --baseline (the gate needs the round-start list)
  exit 3  invalid item (HOTL done without evidence, delegated HOTL done without the delegator's
          re-measurement record, HITL outside the HITL floor, a flag that is not a boolean,
          a done item whose delivered differs from its expected, bad field)
  exit 4  denominator shrank vs --baseline (an item vanished instead of being closed), or an
          item changed kind vs --baseline (HOTL relabelled as HITL, or back)
  exit 5  --gate close requested but not met (HOTL < 100% or an open HITL is not in the digest)

Input schema (stdlib-only validation):
  {"items": [{"id": str, "kind": "HOTL"|"HITL", "state": "open"|"done",
              "evidence": str (required when HOTL done),
              "delegated": bool (required on every HOTL done: true when a worker/subagent
                                 completed it, false when the conductor did it itself),
              "remeasured": bool (required boolean true when delegated and done),
              "remeasure": {"source", "ref", "at", "result"} (required when delegated and done:
                           where the delegator looked, an immutable reference such as a SHA or
                           PR number, an ISO 8601 time, and what it read. The gate checks the
                           record's shape, not its truth: it is a conductor declaration that
                           can be audited later, not a deterministic re-measurement),
              "expected": str, "delivered": str (optional pair; when one is set both are, and
                           a done item must have delivered == expected: a gap is its own item),
              "floor": one of HITL_FLOOR (required when kind=HITL),
              "digest": bool (HITL only: is it in the HITL DIGEST?)}]}
Every flag above must be a JSON boolean when present: "false" (a string) is refused.
For HITL, state "done" means "answered by the operator".
"""
import argparse
import json
import sys
from datetime import datetime

HITL_FLOOR = {
    "credential",          # a new credential / secret the agent does not hold
    "spend",               # money
    "irreversible-prod",   # irreversible action in production
    "external-send",       # message/e-mail/post leaving the trust boundary
    "operator-taste",      # personal preference or business call of the operator
    "third-party-governance",  # a domain whose owner did not delegate to the agent
    "raw-secret",          # print, log or commit a secret value
    "cross-world-credential",  # a credential used outside its owner's domain
    "access-control-self-approval",  # a change that lets the agent's accounts approve itself
}
# Every hard flag of request-carried-authorization (§5) has a floor value, so no hard case can
# turn HOTL just because its name is missing here. tests/run-tests.sh checks this mapping
# against that skill's HARD_FLAGS.
HARD_FLAG_TO_FLOOR = {
    "spend": "spend",
    "raw_secret": "raw-secret",
    "irreversible_in_prod": "irreversible-prod",
    "external_send": "external-send",
    "third_party_domain": "third-party-governance",
    "cross_world_credential": "cross-world-credential",
    "human_domain": "operator-taste",
    "access_control_self_approval": "access-control-self-approval",
}
BOOL_FLAGS = ("delegated", "remeasured", "digest")
REMEASURE_KEYS = ("source", "ref", "at", "result")
KINDS = {"HOTL", "HITL"}
STATES = {"open", "done"}


def load(path):
    try:
        with (sys.stdin if path == "-" else open(path, encoding="utf-8")) as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        print(f"scoreboard: cannot read {path}: {exc}", file=sys.stderr)
        sys.exit(2)
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        print(f"scoreboard: {path}: top-level 'items' list required", file=sys.stderr)
        sys.exit(2)
    return items


def validate(items):
    errors, seen = [], set()
    for i, it in enumerate(items):
        iid = it.get("id") if isinstance(it, dict) else None
        tag = f"item[{i}] {iid!r}"
        if not isinstance(iid, str) or not iid:
            errors.append(f"{tag}: id must be a non-empty string")
            continue
        if iid in seen:
            errors.append(f"{tag}: duplicate id")
        seen.add(iid)
        kind, state = it.get("kind"), it.get("state")
        if kind not in KINDS:
            errors.append(f"{tag}: kind must be HOTL or HITL")
        if state not in STATES:
            errors.append(f"{tag}: state must be open or done")
        for f in BOOL_FLAGS:
            if f in it and not isinstance(it[f], bool):
                errors.append(f"{tag}: {f} must be a JSON boolean, got {it[f]!r}")
        if kind == "HOTL" and state == "done" and not isinstance(it.get("delegated"), bool):
            errors.append(f"{tag}: HOTL done must declare delegated: true (a worker did it) "
                          "or false (the conductor did it)")
        if ("expected" in it) != ("delivered" in it):
            errors.append(f"{tag}: expected and delivered go together")
        elif state == "done" and "expected" in it and it["expected"] != it["delivered"]:
            errors.append(f"{tag}: done but delivered != expected; file the gap as its own item")
        if kind == "HOTL" and state == "done" and not str(it.get("evidence", "")).strip():
            errors.append(f"{tag}: HOTL marked done without evidence (a worker's word is not evidence)")
        if kind == "HOTL" and state == "done" and it.get("delegated") and it.get("remeasured") is not True:
            errors.append(
                f"{tag}: delegated HOTL marked done without the delegator's own re-measurement "
                "(delegating does not waive responsibility: set remeasured=true only after "
                "checking at source)"
            )
        if kind == "HOTL" and state == "done" and it.get("delegated") is True:
            rec = it.get("remeasure")
            if not (isinstance(rec, dict) and all(
                    isinstance(rec.get(k), str) and rec[k].strip() for k in REMEASURE_KEYS)):
                errors.append(f"{tag}: delegated done needs a remeasure record with "
                              f"{list(REMEASURE_KEYS)} (where, immutable ref, when, what was read)")
            else:
                try:
                    datetime.fromisoformat(rec["at"].replace("Z", "+00:00"))
                except ValueError:
                    errors.append(f"{tag}: remeasure.at must be ISO 8601, got {rec['at']!r}")
        if kind == "HITL" and it.get("floor") not in HITL_FLOOR:
            errors.append(
                f"{tag}: HITL outside the floor ({it.get('floor')!r}); "
                f"allowed: {sorted(HITL_FLOOR)} — otherwise it is HOTL, decide it"
            )
    return errors


def pct(num, den):
    return 100.0 if den == 0 else round(100.0 * num / den, 1)


def score(items):
    hotl = [i for i in items if i["kind"] == "HOTL"]
    hitl = [i for i in items if i["kind"] == "HITL"]
    hotl_done = sum(1 for i in hotl if i["state"] == "done")
    hitl_done = sum(1 for i in hitl if i["state"] == "done")
    pending = [
        {"id": i["id"], "kind": i["kind"], "floor": i.get("floor"), "digest": i.get("digest") is True}
        for i in items if i["state"] == "open"
    ]
    return {
        "hotl": {"num": hotl_done, "den": len(hotl), "pct": pct(hotl_done, len(hotl))},
        "hitl": {"num": hitl_done, "den": len(hitl), "pct": pct(hitl_done, len(hitl))},
        "session": {"num": hotl_done + hitl_done, "den": len(items),
                    "pct": pct(hotl_done + hitl_done, len(items))},
        "pending": pending,
        "ids": sorted(i["id"] for i in items),
        "kinds": {i["id"]: i["kind"] for i in items},
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("items", help="items JSON file, or - for stdin")
    ap.add_argument("--baseline", help="items JSON from the start of the round (denominator guard)")
    ap.add_argument("--gate", choices=["close"], help="also enforce the close-out gate")
    ap.add_argument("--json", action="store_true", help="machine output")
    a = ap.parse_args()
    if a.gate == "close" and not a.baseline:
        print("scoreboard: --gate close needs --baseline (the round-start items)", file=sys.stderr)
        return 2

    items = load(a.items)
    errors = validate(items)
    if errors:
        for e in errors:
            print(f"INVALID {e}", file=sys.stderr)
        return 3
    s = score(items)

    if a.baseline:
        base = load(a.baseline)
        gone = sorted({i.get("id") for i in base if isinstance(i, dict)} - set(s["ids"]))
        if gone:
            print(f"SHRINK denominator lost items without closing them: {gone}", file=sys.stderr)
            return 4
        relabel = sorted(i["id"] for i in base if isinstance(i, dict)
                         and i.get("id") in s["kinds"] and i.get("kind") != s["kinds"][i["id"]])
        if relabel:
            print(f"RELABEL items changed kind vs baseline (close or keep them, do not relabel): "
                  f"{relabel}", file=sys.stderr)
            return 4

    s.pop("kinds")
    if a.json:
        print(json.dumps(s, indent=2))
    else:
        for k in ("hotl", "hitl", "session"):
            v = s[k]
            print(f"%{k.upper():8} {v['num']}/{v['den']} = {v['pct']}%")
        for p in s["pending"]:
            extra = f" floor={p['floor']} digest={'yes' if p['digest'] else 'NO'}" if p["kind"] == "HITL" else ""
            print(f"  pending {p['id']} [{p['kind']}]{extra}")

    if a.gate == "close":
        undigested = [p["id"] for p in s["pending"] if p["kind"] == "HITL" and not p["digest"]]
        if s["hotl"]["num"] != s["hotl"]["den"] or undigested:
            print(f"GATE close not met: HOTL {s['hotl']['num']}/{s['hotl']['den']}, "
                  f"HITL not in digest: {undigested}", file=sys.stderr)
            return 5
    return 0


if __name__ == "__main__":
    sys.exit(main())
