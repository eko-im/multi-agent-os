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
expect 5 "A6 close gate blocks while HOTL is open"            "$PY" "$SB" "$FX/progress.json" --gate close
expect 5 "A7 close gate blocks an open HITL not in digest"    "$PY" "$SB" "$FX/undigested.json" --gate close
expect 0 "A8 close gate passes: HOTL 100%, HITL in digest"    "$PY" "$SB" "$FX/closable.json" --gate close
expect 2 "A9 unreadable input is a usage error"               "$PY" "$SB" "$FX/does-not-exist.json"
expect 3 "A10 delegated done without delegator re-measure"    "$PY" "$SB" "$FX/delegated-unmeasured.json"
expect 3 "A12 remeasured must be boolean true, not a string" "$PY" "$SB" "$FX/delegated-string-false.json"
expect 0 "A11 delegated done, delegator re-measured: closes"  "$PY" "$SB" "$FX/delegated-remeasured.json" --gate close

echo "== mutation check: each guard removed must flip its scenario =="
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

# mutate <label> <python-substring-to-neutralize> <replacement> <fixture> [extra args...]
mutate() {
  local label="$1" needle="$2" repl="$3" fx="$4"; shift 4
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
  if [ "$got" = "0" ]; then ok "M $label: guard removed -> scenario flips to exit 0"
  else bad "M $label: guard removed but scenario still exits $got (test does not discriminate)"; fi
}

mutate "evidence guard"    'state == "done" and not str(it.get("evidence", "")).strip()' 'False' "$FX/no-evidence.json"
mutate "HITL floor guard"  'it.get("floor") not in HITL_FLOOR' 'False' "$FX/tactical-hitl.json"
mutate "re-measure guard"  'it.get("delegated") and it.get("remeasured") is not True' 'False' "$FX/delegated-unmeasured.json"
mutate "shrink guard"      'if gone:' 'if False:' "$FX/shrunk.json" --baseline "$FX/baseline.json"
mutate "close gate"        'if s["hotl"]["num"] != s["hotl"]["den"] or undigested:' 'if False:' "$FX/progress.json" --gate close

echo "== $pass passed, $fail failed =="
[ "$fail" -eq 0 ]
