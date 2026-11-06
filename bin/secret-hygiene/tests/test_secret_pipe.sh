#!/bin/bash
# Tests secret-pipe with a FAKE `op` on PATH (no vault read, no quota used).
# Mutation-check: a copy of secret-pipe with masking removed must FAIL test 1.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
SP="${1:-$HERE/../secret-pipe}"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
FAKE="FAKE-pw-$(openssl rand -hex 6)"
cat > "$T/op" <<EOF
#!/bin/sh
case "\$1 \$2" in
  "read --no-newline") printf '%s' "$FAKE" ;;
  "item get") printf '{"fields":[{"label":"password","value":"%s"},{"label":"empty","value":""}]}' "$FAKE" ;;
  *) exit 9 ;;
esac
EOF
chmod +x "$T/op"; export PATH="$T:$PATH"
fail=0
ok() { echo "PASS $1"; }; ko() { echo "FAIL $1"; fail=1; }

out=$("$SP" op://eko/x/password -- sh -c 'read -r v; [ "$v" = "'"$FAKE"'" ] && echo got-it; echo "echoed:$v"' 2>&1)
case "$out" in *got-it*) ok "stdin entrega o valor";; *) ko "stdin entrega o valor";; esac
case "$out" in *"$FAKE"*) ko "stdin: saída mascarada";; *"<secret:"*) ok "stdin: saída mascarada";; *) ko "stdin: saída mascarada";; esac

out=$("$SP" --env PW 'eko:x:password' -- sh -c '[ "$PW" = "'"$FAKE"'" ] && echo env-ok; echo "$PW" >&2' 2>&1)
case "$out" in *env-ok*) ok "env entrega";; *) ko "env entrega";; esac
case "$out" in *"$FAKE"*) ko "env: stderr mascarado";; *) ok "env: stderr mascarado";; esac

out=$("$SP" --file 'eko:x:password' -- sh -c 'stat -f %Lp "$1"; [ "$(cat "$1")" = "'"$FAKE"'" ] && echo file-ok; echo "$1" > '"$T/path" sh {} 2>&1)
case "$out" in *600*file-ok*) ok "file 0600 entrega";; *) ko "file 0600 entrega ($out)";; esac
[ -e "$(cat "$T/path")" ] && ko "file apagado no fim" || ok "file apagado no fim"

"$SP" 'Personal:x:password' -- true 2>/dev/null && ko "Personal recusado" || ok "Personal recusado"
"$SP" 'eko:x:empty' -- true 2>/dev/null && ko "valor vazio recusado" || ok "valor vazio recusado"
"$SP" 'eko:x:nope' -- true 2>/dev/null && ko "campo inexistente recusado" || ok "campo inexistente recusado"
exit $fail
