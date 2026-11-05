#!/usr/bin/env python3
"""scoreboard.py — deterministic HOTL/HITL completeness scoreboard for `session-wrapup`.

Reads a JSON item list (decisions, actions, tasks of this session) and prints the three
numbers the skill reports — %HOTL, %HITL, %session — always as numerator/denominator.

It is a GATE, not a calculator: it refuses inputs that would let the agent fake progress.

  exit 0  ok (and, with --gate close, the close-out gate is met)
  exit 2  usage / unreadable input
  exit 3  invalid item (HOTL done without evidence, HITL outside the HITL floor, bad field)
  exit 4  denominator shrank vs --baseline (an item vanished instead of being closed)
  exit 5  --gate close requested but not met (HOTL < 100% or an open HITL is not in the digest)

Input schema (stdlib-only validation):
  {"items": [{"id": str, "kind": "HOTL"|"HITL", "state": "open"|"done",
              "evidence": str (required when HOTL done),
              "floor": one of HITL_FLOOR (required when kind=HITL),
              "digest": bool (HITL only: is it in the HITL DIGEST?)}]}
For HITL, state "done" means "answered by the operator".
"""
import argparse
import json
import sys

HITL_FLOOR = {
    "credential",          # a new credential / secret the agent does not hold
    "spend",               # money
    "irreversible-prod",   # irreversible action in production
    "external-send",       # message/e-mail/post leaving the trust boundary
    "operator-taste",      # personal preference or business call of the operator
    "third-party-governance",  # a domain whose owner did not delegate to the agent
}
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
        if kind == "HOTL" and state == "done" and not str(it.get("evidence", "")).strip():
            errors.append(f"{tag}: HOTL marked done without evidence (a worker's word is not evidence)")
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
        {"id": i["id"], "kind": i["kind"], "floor": i.get("floor"), "digest": bool(i.get("digest"))}
        for i in items if i["state"] == "open"
    ]
    return {
        "hotl": {"num": hotl_done, "den": len(hotl), "pct": pct(hotl_done, len(hotl))},
        "hitl": {"num": hitl_done, "den": len(hitl), "pct": pct(hitl_done, len(hitl))},
        "session": {"num": hotl_done + hitl_done, "den": len(items),
                    "pct": pct(hotl_done + hitl_done, len(items))},
        "pending": pending,
        "ids": sorted(i["id"] for i in items),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("items", help="items JSON file, or - for stdin")
    ap.add_argument("--baseline", help="items JSON from the start of the round (denominator guard)")
    ap.add_argument("--gate", choices=["close"], help="also enforce the close-out gate")
    ap.add_argument("--json", action="store_true", help="machine output")
    a = ap.parse_args()

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
