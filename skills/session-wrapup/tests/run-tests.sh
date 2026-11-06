#!/usr/bin/env bash
# run-tests.sh — acceptance scenarios for skills/session-wrapup/bin/scoreboard.py.
# Each scenario comes from a real failure the skill exists to stop (see SKILL.md §Acceptance).
# Part 2 is a MUTATION CHECK: each guard is removed from a temp copy and the scenario that
# depends on it must flip — a guard whose test passes with and without it proves nothing.
# Stdlib only; exit 0 iff all pass.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SB="$HERE/../bin/scoreboard.py"
FX="$HERE/fixtures"
PY="$(command -v python3 || true)"
[ -n "$PY" ] || { echo "FAIL: python3 not found"; exit 1; }

pass=0 fail=0
ok()  { echo "  ok   — $1"; pass=$((pass+1)); }
bad() { echo "  FAIL — $1"; fail=$((fail+1)); }

# expect <want-exit> <label> <cmd...>
expect() {
  local want="$1" label="$2"; shift 2
  local got=0
  "$@" >/dev/null 2>&1 || got=$?
  if [ "$got" = "$want" ]; then ok "$label (exit $got)"; else bad "$label (want $want, got $got)"; fi
}

echo "== session-wrapup scoreboard: acceptance scenarios =="

# A1 numbers are num/den, exact
out="$("$PY" "$SB" "$FX/progress.json")"
if printf '%s\n' "$out" | grep -q '^%HOTL     2/4 = 50.0%' \
   && printf '%s\n' "$out" | grep -q '^%HITL     0/1 = 0.0%' \
   && printf '%s\n' "$out" | grep -q '^%SESSION  2/5 = 40.0%'; then
  ok "A1 placar shows numerator/denominator (2/4, 0/1, 2/5)"
else
  bad "A1 placar numbers wrong: $out"
fi

expect 3 "A2 HOTL done without evidence is refused"           "$PY" "$SB" "$FX/no-evidence.json"
expect 3 "A3 tactical question filed as HITL is refused"      "$PY" "$SB" "$FX/tactical-hitl.json"
expect 4 "A4 denominator shrink vs baseline is refused"       "$PY" "$SB" "$FX/shrunk.json" --baseline "$FX/baseline.json"
expect 0 "A5 new item grows the denominator (allowed)"        "$PY" "$SB" "$FX/progress.json" --baseline "$FX/baseline.json"
expect 5 "A6 close gate blocks while HOTL is open"            "$PY" "$SB" "$FX/progress.json" --gate close --baseline "$FX/baseline.json"
expect 5 "A7 close gate blocks an open HITL not in digest"    "$PY" "$SB" "$FX/undigested.json" --gate close --baseline "$FX/undigested.json"
expect 0 "A8 close gate passes: HOTL 100%, HITL in digest"    "$PY" "$SB" "$FX/closable.json" --gate close --baseline "$FX/closable.json"
expect 2 "A9 unreadable input is a usage error"               "$PY" "$SB" "$FX/does-not-exist.json"
expect 3 "A10 delegated done without delegator re-measure"    "$PY" "$SB" "$FX/delegated-unmeasured.json"
expect 3 "A12 remeasured must be boolean true, not a string" "$PY" "$SB" "$FX/delegated-string-false.json"
expect 0 "A11 delegated done, delegator re-measured: closes"  "$PY" "$SB" "$FX/delegated-remeasured.json" --gate close --baseline "$FX/delegated-remeasured.json"
expect 4 "A13 HOTL relabelled as HITL vs baseline is refused" "$PY" "$SB" "$FX/relabel.json" --gate close --baseline "$FX/relabel-baseline.json"
expect 2 "A14 close gate without --baseline is refused"       "$PY" "$SB" "$FX/closable.json" --gate close
expect 3 "A15 digest \"false\" (a string) is refused"          "$PY" "$SB" "$FX/digest-string.json" --gate close --baseline "$FX/digest-string.json"
expect 3 "A16 HOTL done must declare delegated true/false"    "$PY" "$SB" "$FX/delegated-missing.json"
expect 3 "A17 delegated done without a remeasure record"      "$PY" "$SB" "$FX/delegated-no-record.json"
expect 3 "A18 remeasure.at must be ISO 8601"                  "$PY" "$SB" "$FX/delegated-bad-time.json"
expect 3 "A19 done with delivered != expected is refused"     "$PY" "$SB" "$FX/gap-done.json"
expect 3 "A22 expected/delivered must be strings (1 == true)" "$PY" "$SB" "$FX/gap-nonstring.json"
expect 3 "A23 remeasure.at must carry a time, not a date"     "$PY" "$SB" "$FX/delegated-date-only.json"
expect 2 "A24 baseline with a non-string id is a usage error" "$PY" "$SB" "$FX/closable.json" --baseline "$FX/baseline-bad-ids.json"
expect 0 "A20 every hard flag has its own HITL floor value"   "$PY" "$SB" "$FX/hard-floor.json"

# Pre-HITL check record (7 minds). Fixtures come from the 5 real cases of 2026-11-04.
expect 0 "A25 real cases: A, B and C records are accepted"     "$PY" "$SB" "$FX/precheck-real-cases.json"
if "$PY" -c 'import json,sys; v={i["precheck"]["verdict"] for i in json.load(open(sys.argv[1]))["items"]}; sys.exit(v!={"A","B","C"})' "$FX/precheck-real-cases.json"
then ok "A26 real-case fixture holds one happy case per verdict A, B, C"
else bad "A26 real-case fixture does not cover A, B and C"; fi
expect 3 "A27 HITL without a precheck record is refused"       "$PY" "$SB" "$FX/precheck-hitl-no-record.json"
expect 3 "A28 precheck missing a mind is refused"              "$PY" "$SB" "$FX/precheck-missing-mind.json"
expect 3 "A29 precheck mind with an empty note is refused"     "$PY" "$SB" "$FX/precheck-empty-mind.json"
expect 3 "A30 precheck mind with a placeholder (TBD) refused"  "$PY" "$SB" "$FX/precheck-placeholder-mind.json"
expect 3 "A31 verdict outside {A,B,C} is refused"              "$PY" "$SB" "$FX/precheck-bad-verdict.json"
expect 3 "A32 verdict B without an undo is refused"            "$PY" "$SB" "$FX/precheck-b-no-undo.json"
expect 3 "A33 verdict C without a lock or type is refused"     "$PY" "$SB" "$FX/precheck-c-no-lock.json"
expect 3 "A34 A/B on a HITL type the request did not name"     "$PY" "$SB" "$FX/precheck-unnamed-type.json"
expect 3 "A35 A/B on a grant that came from data is refused"   "$PY" "$SB" "$FX/precheck-from-data.json"
expect 3 "A36 HITL item with verdict A (should act) refused"   "$PY" "$SB" "$FX/precheck-hitl-verdict-a.json"
expect 3 "A37 non-string enum (hitl_type: []) refused, no crash" "$PY" "$SB" "$FX/precheck-nonstring-enum.json"
expect 3 "A38 verdict: [] is refused with exit 3, no traceback" "$PY" "$SB" "$FX/precheck-list-verdict.json"
expect 3 "A39 precheck must declare hitl_type (null is explicit)" "$PY" "$SB" "$FX/precheck-no-type-declared.json"
expect 3 "A40 HOTL done with a hard C (human residue) refused" "$PY" "$SB" "$FX/precheck-hotl-hard-c.json"
expect 0 "A41 HOTL done with C c_kind=ladder (council path) ok"  "$PY" "$SB" "$FX/precheck-hotl-ladder-c.json"
expect 3 "A42 c_kind=ladder on a data-origin hard lock refused" "$PY" "$SB" "$FX/precheck-hotl-data-ladder.json"
expect 3 "A43 notes of repeated placeholders (TBD TBD, n/a n/a)" "$PY" "$SB" "$FX/precheck-repeated-placeholder.json"
expect 3 "A44 verdict outside {A,B,C} on a HITL item is refused" "$PY" "$SB" "$FX/precheck-hitl-bad-verdict.json"

# A21 the hard-flag map covers exactly request-carried-authorization's HARD_FLAGS
if PYTHONDONTWRITEBYTECODE=1 "$PY" - "$HERE/../bin" "$HERE/../../request-carried-authorization/scripts" <<'PYEOF'
import sys
sys.path[:0] = sys.argv[1:3]
import scoreboard, carried_authorization as ca
m = scoreboard.HARD_FLAG_TO_FLOOR
assert set(m) == set(ca.HARD_FLAGS), set(m) ^ set(ca.HARD_FLAGS)
assert set(m.values()) <= scoreboard.HITL_FLOOR, set(m.values()) - scoreboard.HITL_FLOOR
assert scoreboard.MINDS == ca.MINDS, (scoreboard.MINDS, ca.MINDS)
PYEOF
then ok "A21 hard-flag map and MINDS == request-carried-authorization, all in floor"
else bad "A21 hard-flag map drifted from request-carried-authorization HARD_FLAGS"; fi

echo "== mutation check: each guard removed must flip its scenario =="
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

# mutate <label> <python-substring-to-neutralize> <replacement> <fixture> [extra args...]
# The mutated scenario must flip to exit $WANT (default 0: a refused case becomes accepted).
mutate() {
  local label="$1" needle="$2" repl="$3" fx="$4" want="${WANT:-0}"; shift 4
  local m="$TMP/sb_mut.py"
  "$PY" - "$SB" "$m" "$needle" "$repl" <<'PYEOF'
import sys
src, dst, needle, repl = sys.argv[1:5]
text = open(src, encoding="utf-8").read()
if needle not in text:
    sys.exit("needle not found: " + needle)
open(dst, "w", encoding="utf-8").write(text.replace(needle, repl, 1))
PYEOF
  local got=0
  "$PY" "$m" "$fx" "$@" >/dev/null 2>&1 || got=$?
  if [ "$got" = "$want" ]; then ok "M $label: guard removed -> scenario flips to exit $want"
  else bad "M $label: guard removed but scenario still exits $got (test does not discriminate)"; fi
}

mutate "evidence guard"    'state == "done" and not str(it.get("evidence", "")).strip()' 'False' "$FX/no-evidence.json"
mutate "HITL floor guard"  'it.get("floor") not in HITL_FLOOR' 'False' "$FX/tactical-hitl.json"
mutate "re-measure guard"  'it.get("delegated") and it.get("remeasured") is not True' 'False' "$FX/delegated-unmeasured.json"
mutate "shrink guard"      'if gone:' 'if False:' "$FX/shrunk.json" --baseline "$FX/baseline.json"
mutate "close gate"        'if s["hotl"]["num"] != s["hotl"]["den"] or undigested:' 'if False:' "$FX/progress.json" --gate close --baseline "$FX/baseline.json"
mutate "relabel guard"     'if relabel:' 'if False:' "$FX/relabel.json" --gate close --baseline "$FX/relabel-baseline.json"
mutate "baseline required" 'if a.gate == "close" and not a.baseline:' 'if False:' "$FX/closable.json" --gate close
# Without the type guard the gate still fails closed (digest is read with `is True`), but as a
# silent "not in digest" (5) instead of an explicit invalid flag (3).
WANT=5 mutate "boolean flags"     'if f in it and not isinstance(it[f], bool):' 'if False:' "$FX/digest-string.json" --gate close --baseline "$FX/digest-string.json"
mutate "delegated declared" 'state == "done" and not isinstance(it.get("delegated"), bool):' 'False:' "$FX/delegated-missing.json"
mutate "remeasure record"  'if kind == "HOTL" and state == "done" and it.get("delegated") is True:' 'if False:' "$FX/delegated-no-record.json"
mutate "remeasure time"    'datetime.fromisoformat(rec["at"]' 'str(rec["at"]' "$FX/delegated-bad-time.json"
mutate "expected=delivered" 'elif state == "done" and "expected" in it and' 'elif False and' "$FX/gap-done.json"
mutate "string expected"   'elif "expected" in it and not (isinstance' 'elif False and not (isinstance' "$FX/gap-nonstring.json"
mutate "time in at"        'if "T" not in rec["at"]:' 'if False:' "$FX/delegated-date-only.json"
WANT=1 mutate "baseline ids"  'if bad_ids:' 'if False:' "$FX/closable.json" --baseline "$FX/baseline-bad-ids.json"
WANT=3 mutate "hard-flag floor" '"raw-secret",          # print' '#' "$FX/hard-floor.json"
mutate "precheck required"  'if it.get("kind") == "HITL" else [])' 'if False else [])' "$FX/precheck-hitl-no-record.json"
mutate "all minds present"  'if missing:' 'if False:' "$FX/precheck-missing-mind.json"
mutate "mind notes filled"  'if hollow:' 'if False:' "$FX/precheck-empty-mind.json"
mutate "placeholder notes"  ' and w not in PLACEHOLDERS' '' "$FX/precheck-placeholder-mind.json"
mutate "per-word notes"     'for w in v.lower().split())' 'for w in [v.lower()])' "$FX/precheck-repeated-placeholder.json"
mutate "verdict set"        'if v not in VERDICTS:' 'if False:' "$FX/precheck-bad-verdict.json"
mutate "B needs undo"       'if v == "B" and not _filled(pc.get("undo")):' 'if False:' "$FX/precheck-b-no-undo.json"
mutate "C needs lock"       'if v == "C" and lock not in' 'if False and lock not in' "$FX/precheck-c-no-lock.json"
mutate "unnamed HITL type"  'and pc.get("named_in_request") is not True:' 'and False:' "$FX/precheck-unnamed-type.json"
mutate "data is not order"  'if v in ("A", "B") and origin == "data":' 'if False:' "$FX/precheck-from-data.json"
mutate "HITL cannot be A/B" 'if it.get("kind") == "HITL" and v in ("A", "B"):' 'if False:' "$FX/precheck-hitl-verdict-a.json"
mutate "string enums"       'if nonstr:' 'if False:' "$FX/precheck-nonstring-enum.json"
mutate "hitl_type declared" 'if "hitl_type" not in pc:' 'if False:' "$FX/precheck-no-type-declared.json"
mutate "hard C stays HITL"  'and v == "C" and not ladder:' 'and False:' "$FX/precheck-hotl-hard-c.json"
mutate "ladder consistent"  'if ladder and (origin == "data" or lock not in LADDER_LOCKS):' 'if False:' "$FX/precheck-hotl-data-ladder.json"

echo "== $pass passed, $fail failed =="
[ "$fail" -eq 0 ]
