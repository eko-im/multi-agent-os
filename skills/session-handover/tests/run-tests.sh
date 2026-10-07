#!/usr/bin/env bash
# run-tests.sh — deterministic tests for session-handover (bin/handover.py).
# Each test exercises one FEAT-N and fails if the feature is absent (TDD: written before the code).
# Fixtures are built at runtime in a temp dir; no secret literal is stored in this file
# (secret-shaped controls are assembled by concatenation inside the script under test).
# Stdlib only. Exit 0 iff every check passes.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$HERE/../bin/handover.py"
PY="$(command -v python3 || true)"
[ -n "$PY" ] || { echo "FAIL: python3 not found"; exit 1; }

T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT
pass=0; fail=0
ok()  { echo "  ok   — $1"; pass=$((pass+1)); }
bad() { echo "  FAIL — $1"; fail=$((fail+1)); }
# expect <exit-code> <label> <cmd...>
expect() { local want="$1" label="$2"; shift 2; "$@" >"$T/out" 2>"$T/err"; local got=$?
  if [ "$got" -eq "$want" ]; then ok "$label (exit $got)"; else bad "$label (want $want, got $got): $(head -c 300 "$T/err")"; fi; }

echo "== session-handover tests =="
[ -f "$BIN" ] || { echo "  FAIL — bin/handover.py missing"; echo "== 0 passed, 1 failed =="; exit 1; }

# ---------- FEAT-1 delegate gate (fail-closed) ----------
mkdir -p "$T/rep"; printf 'report body\n' > "$T/rep/a.md"; : > "$T/rep/empty.md"
cat > "$T/gate_ok.json" <<EOF
{"delegates":[{"id":"A","state":"delivered","report":"$T/rep/a.md"}]}
EOF
cat > "$T/gate_pending.json" <<EOF
{"delegates":[{"id":"A","state":"delivered","report":"$T/rep/a.md"},{"id":"B","state":"running","report":"$T/rep/b.md"}]}
EOF
cat > "$T/gate_empty.json" <<EOF
{"delegates":[{"id":"A","state":"delivered","report":"$T/rep/empty.md"}]}
EOF
expect 0 "FEAT-1 gate passes when every delegate delivered a non-empty report" "$PY" "$BIN" gate --manifest "$T/gate_ok.json"
expect 3 "FEAT-1 gate refuses a running delegate after timeout" "$PY" "$BIN" gate --manifest "$T/gate_pending.json" --timeout 1 --interval 1
expect 3 "FEAT-1 gate refuses 'delivered' with an empty report" "$PY" "$BIN" gate --manifest "$T/gate_empty.json"
expect 3 "FEAT-1 gate fails closed on a missing manifest" "$PY" "$BIN" gate --manifest "$T/nope.json"
echo '{"delegates":[]}' > "$T/gate_none.json"
expect 3 "FEAT-1 gate refuses an empty delegate list (nothing proven)" "$PY" "$BIN" gate --manifest "$T/gate_none.json"

# ---------- ledger fixture ----------
mkdir -p "$T/proj/abc"; : > "$T/proj/abc/S-123.jsonl"
mkdir -p "$T/art"; printf 'x\n' > "$T/art/report1.md"
cat > "$T/ledger.json" <<EOF
{
 "session": {"id":"S-123","link":"https://example.invalid/session/S-123",
             "resume_cmd":"cd ~/work && claude --resume S-123","cwd":"~/work"},
 "title": "demo campaign",
 "declared_empty": ["motivation","target","prompt","failure","error","warning","dor"],
 "nodes": [
  {"id":"I1","kind":"instruction","title":"build the thing","status":"in_progress","parent":null},
  {"id":"G1","kind":"goal","title":"thing works","status":"pending","parent":"I1"},
  {"id":"T1","kind":"task","title":"write code","status":"done","parent":"I1"},
  {"id":"S1","kind":"step","title":"write tests","status":"done","parent":"T1"},
  {"id":"T2","kind":"task","title":"ship it","status":"blocked","parent":"I1"},
  {"id":"D1","kind":"dod","title":"tests green","status":"pending","parent":"T2"},
  {"id":"B1","kind":"bug","title":"flaky check","status":"pending","parent":"T2"},
  {"id":"P1","kind":"gap","title":"no docs","status":"pending","parent":"I1"}
 ],
 "hitl": [
  {"id":"H2","title":"minor naming","quadrant":"Q4","where":"PR comment",
   "options":[{"label":"keep","recommended":true,"tradeoff":"none"},{"label":"rename","tradeoff":"churn"}]},
  {"id":"H1","title":"approve merge","quadrant":"Q1","where":"PR",
   "options":[{"label":"merge after review","recommended":true,"tradeoff":"waits review"},{"label":"merge now","tradeoff":"risk"}]}
 ],
 "roadmap": [{"phase":"F0","item":"re-enter","depends_on":[],"gate":"none","owner":"root","done_when":"state matches graph"}],
 "artifacts": [{"path":"$T/art/report1.md","desc":"report one"}]
}
EOF

# ---------- FEAT-2 ledger validation ----------
expect 0 "FEAT-2 valid ledger validates" "$PY" "$BIN" validate --ledger "$T/ledger.json"
sed 's/"parent":"T1"/"parent":"ZZ"/' "$T/ledger.json" > "$T/bad_parent.json"
expect 3 "FEAT-2 dangling parent refused" "$PY" "$BIN" validate --ledger "$T/bad_parent.json"
sed 's/"status":"blocked"/"status":"maybe"/' "$T/ledger.json" > "$T/bad_status.json"
expect 3 "FEAT-2 unknown status refused" "$PY" "$BIN" validate --ledger "$T/bad_status.json"
sed 's/"parent":null/"parent":"T1"/' "$T/ledger.json" > "$T/cycle.json"
expect 3 "FEAT-2 cycle in the N-tree refused" "$PY" "$BIN" validate --ledger "$T/cycle.json"

# ---------- FEAT-3 harvest coverage (no silent drop) ----------
sed 's/"motivation",//' "$T/ledger.json" > "$T/no_motiv.json"
expect 3 "FEAT-3 a harvest kind neither present nor declared empty is refused" "$PY" "$BIN" validate --ledger "$T/no_motiv.json"

# ---------- FEAT-4 HITL contract ----------
sed 's/{"label":"keep","recommended":true,"tradeoff":"none"},{"label":"rename","tradeoff":"churn"}/{"label":"rename","tradeoff":"churn"},{"label":"keep","recommended":true,"tradeoff":"none"}/' "$T/ledger.json" > "$T/hitl_order.json"
expect 3 "FEAT-4 recommended option must come first" "$PY" "$BIN" validate --ledger "$T/hitl_order.json"
sed 's/"quadrant":"Q4"/"quadrant":"Q9"/' "$T/ledger.json" > "$T/hitl_q.json"
expect 3 "FEAT-4 unknown Eisenhower quadrant refused" "$PY" "$BIN" validate --ledger "$T/hitl_q.json"

# ---------- FEAT-5 recovery triple verification ----------
expect 0 "FEAT-5 recovery verified (transcript found, command carries id)" env HANDOVER_TRANSCRIPT_ROOT="$T/proj" "$PY" "$BIN" recovery --ledger "$T/ledger.json"
sed 's/claude --resume S-123/claude --resume OTHER/' "$T/ledger.json" > "$T/rec_cmd.json"
expect 3 "FEAT-5 command without the session id refused" env HANDOVER_TRANSCRIPT_ROOT="$T/proj" "$PY" "$BIN" recovery --ledger "$T/rec_cmd.json"
expect 3 "FEAT-5 missing transcript refused" env HANDOVER_TRANSCRIPT_ROOT="$T/empty_root" "$PY" "$BIN" recovery --ledger "$T/ledger.json"

# ---------- FEAT-6 render: dry-run default, apply writes, self-location, ordering ----------
OUT="$T/handover"
expect 0 "FEAT-6 render dry-run" env HANDOVER_TRANSCRIPT_ROOT="$T/proj" "$PY" "$BIN" render --ledger "$T/ledger.json" --out "$OUT"
[ ! -e "$OUT/HANDOFF_PROMPT.md" ] && ok "FEAT-6 dry-run wrote nothing" || bad "FEAT-6 dry-run wrote files"
expect 0 "FEAT-6 render --apply" env HANDOVER_TRANSCRIPT_ROOT="$T/proj" "$PY" "$BIN" render --ledger "$T/ledger.json" --out "$OUT" --apply
for f in GRAFO.md HITL_PENDENCIAS.md ROADMAP.md INDEX_ARTEFATOS.md HANDOFF_PROMPT.md; do
  [ -s "$OUT/$f" ] && ok "FEAT-6 wrote $f" || bad "FEAT-6 missing $f"; done
grep -qF "$OUT/HANDOFF_PROMPT.md" "$OUT/HANDOFF_PROMPT.md" && ok "FEAT-7 handoff states its own location" || bad "FEAT-7 handoff lacks self-location"
grep -qF "claude --resume S-123" "$OUT/HANDOFF_PROMPT.md" && grep -qF "claude --resume S-123" "$OUT/ROADMAP.md" \
  && ok "FEAT-5 recovery triple in handoff and roadmap" || bad "FEAT-5 recovery triple missing"
grep -qF "$T/art/report1.md" "$OUT/INDEX_ARTEFATOS.md" && grep -qF "INDEX_ARTEFATOS.md" "$OUT/HANDOFF_PROMPT.md" \
  && ok "FEAT-8 index links artifacts and handoff links index" || bad "FEAT-8 link index incomplete"
h1=$(grep -n 'H1' "$OUT/HITL_PENDENCIAS.md" | head -1 | cut -d: -f1); h2=$(grep -n 'H2' "$OUT/HITL_PENDENCIAS.md" | head -1 | cut -d: -f1)
[ -n "$h1" ] && [ -n "$h2" ] && [ "$h1" -lt "$h2" ] && ok "FEAT-4 HITL sorted by Eisenhower (Q1 before Q4)" || bad "FEAT-4 HITL not sorted"
grep -q 'mermaid' "$OUT/GRAFO.md" && grep -q 'S1' "$OUT/GRAFO.md" && ok "FEAT-9 graph has N-tree + Mermaid" || bad "FEAT-9 graph incomplete"
env HANDOVER_TRANSCRIPT_ROOT="$T/proj" "$PY" "$BIN" render --ledger "$T/ledger.json" --out "$OUT" --apply >/dev/null 2>&1
ls "$OUT"/GRAFO.md.bak-* >/dev/null 2>&1 && bad "FEAT-10 identical re-render created a backup" || ok "FEAT-10 identical re-render is a no-op (idempotent)"
sed 's/"demo campaign"/"demo campaign v2"/' "$T/ledger.json" > "$T/ledger_v2.json"
env HANDOVER_TRANSCRIPT_ROOT="$T/proj" "$PY" "$BIN" render --ledger "$T/ledger_v2.json" --out "$OUT" --apply >/dev/null 2>&1
ls "$OUT"/GRAFO.md.bak-* >/dev/null 2>&1 && grep -q 'v2' "$OUT/GRAFO.md" && ok "FEAT-10 changed re-render keeps a backup (never silent overwrite)" || bad "FEAT-10 no backup on overwrite"
sed 's#report1.md#ghost.md#' "$T/ledger.json" > "$T/dangling_art.json"
expect 3 "FEAT-8 dangling artifact link refused at render" env HANDOVER_TRANSCRIPT_ROOT="$T/proj" "$PY" "$BIN" render --ledger "$T/dangling_art.json" --out "$T/h2" --apply

# ---------- FEAT-11 todo / punch-list sync ----------
cat > "$T/todo.json" <<'EOF'
[{"content":"write code","status":"completed"},{"content":"ship it","status":"in_progress"}]
EOF
expect 0 "FEAT-11 todo in sync" "$PY" "$BIN" sync-todo --ledger "$T/ledger.json" --todo "$T/todo.json"
cat > "$T/todo_drift.json" <<'EOF'
[{"content":"write code","status":"pending"},{"content":"unknown chore","status":"pending"}]
EOF
expect 2 "FEAT-11 todo drift reported" "$PY" "$BIN" sync-todo --ledger "$T/ledger.json" --todo "$T/todo_drift.json"

# ---------- FEAT-12 durable persistence with secret/PII scan ----------
mkdir -p "$T/eph"; printf 'clean report\n' > "$T/eph/clean.md"
"$PY" - "$T/eph/dirty.md" <<'PYEOF'
import sys
tok = "gh" + "p_" + "A1b2C3d4" * 5          # assembled at runtime; never a literal in source
mail = "someone" + "@" + "example" + ".org"
open(sys.argv[1], "w").write("token=%s\ncontact %s\n" % (tok, mail))
PYEOF
expect 0 "FEAT-12 scan self-test (positive control detected)" "$PY" "$BIN" scan --self-test
expect 0 "FEAT-12 persist dry-run of clean file" "$PY" "$BIN" persist --src "$T/eph/clean.md" --dest "$T/durable"
[ ! -e "$T/durable/clean.md" ] && ok "FEAT-12 persist dry-run wrote nothing" || bad "FEAT-12 persist dry-run wrote"
expect 4 "FEAT-12 persist refuses a file with secret/PII" "$PY" "$BIN" persist --src "$T/eph/dirty.md" --dest "$T/durable" --apply
[ ! -e "$T/durable/dirty.md" ] && ok "FEAT-12 dirty file not copied" || bad "FEAT-12 dirty file copied"
expect 0 "FEAT-12 persist --redact copies a redacted version" "$PY" "$BIN" persist --src "$T/eph/dirty.md" --dest "$T/durable" --apply --redact
if [ -f "$T/durable/dirty.md" ] && ! grep -q '@example' "$T/durable/dirty.md" && grep -q 'REDACTED' "$T/durable/dirty.md"; then
  ok "FEAT-12 redacted copy holds no PII"; else bad "FEAT-12 redaction failed"; fi
expect 0 "FEAT-12 persist --apply copies the clean file" "$PY" "$BIN" persist --src "$T/eph/clean.md" --dest "$T/durable" --apply
cmp -s "$T/eph/clean.md" "$T/durable/clean.md" && ok "FEAT-12 durable copy is byte-identical" || bad "FEAT-12 copy differs"

# ---------- FEAT-13 clipboard verified with cmp ----------
printf 'handoff text\n' > "$T/clip_src.md"
expect 0 "FEAT-13 clipboard round-trip verified" env HANDOVER_COPY_CMD="cp /dev/stdin $T/clipboard" HANDOVER_PASTE_CMD="cat $T/clipboard" "$PY" "$BIN" clip --file "$T/clip_src.md"
expect 5 "FEAT-13 clipboard mismatch detected" env HANDOVER_COPY_CMD="cp /dev/stdin $T/clipboard2" HANDOVER_PASTE_CMD="echo other" "$PY" "$BIN" clip --file "$T/clip_src.md"
expect 6 "FEAT-13 no clipboard tool → fallback signal" env HANDOVER_COPY_CMD="definitely-not-a-cmd-xyz" HANDOVER_PASTE_CMD="definitely-not-a-cmd-xyz" "$PY" "$BIN" clip --file "$T/clip_src.md"


# ---------- FEAT-34 git state anchor (branch@HEAD, dirty files named, worktrees) ----------
R="$T/repo"; git init -q "$R" && git -C "$R" -c user.email=t@t.invalid -c user.name=t commit -q --allow-empty -m init
printf 'x\n' > "$R/untracked.txt"
"$PY" "$BIN" git-anchor --repo "$R" --json > "$T/anchor.json" 2>"$T/err"; rc=$?
if [ "$rc" -eq 2 ] && "$PY" -c 'import json,sys; d=json.load(open(sys.argv[1])); assert "@" in d["anchor"]; assert any("untracked.txt" in f for f in d["dirty"])' "$T/anchor.json"; then
  ok "FEAT-34 anchor names branch@HEAD and the dirty file (exit 2 = dirty)"; else bad "FEAT-34 anchor (rc=$rc)"; fi
rm "$R/untracked.txt"
expect 0 "FEAT-34 clean repo anchors with exit 0" "$PY" "$BIN" git-anchor --repo "$R"
expect 3 "FEAT-34 non-repo path refused" "$PY" "$BIN" git-anchor --repo "$T/art"

# ---------- FEAT-14 machine output ----------
"$PY" "$BIN" validate --ledger "$T/ledger.json" --json | "$PY" -c 'import json,sys; d=json.load(sys.stdin); assert d["ok"] is True' \
  && ok "FEAT-14 --json envelope parses" || bad "FEAT-14 --json envelope"

echo "== $pass passed, $fail failed =="
[ "$fail" -eq 0 ]
