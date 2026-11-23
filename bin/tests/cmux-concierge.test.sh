#!/usr/bin/env bash
# shellcheck disable=SC2034,SC2010  # vars are read inside eval'd checks; fixture names are fixed
# Tests for bin/cmux-concierge. Hermetic: no ssh, no real cmux, no real /etc.
# Run: bash bin/tests/cmux-concierge.test.sh [path-to-cmux-concierge]
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
TOOL="${1:-$HERE/../cmux-concierge}"
PASS=0; FAIL=0
ok()   { PASS=$((PASS + 1)); echo "  ok   $1"; }
bad()  { FAIL=$((FAIL + 1)); echo "  FAIL $1"; }
check(){ if eval "$2"; then ok "$1"; else bad "$1"; fi; }

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
mkdir -p "$T/bin" "$T/home" "$T/root/etc" "$T/root/run/systemd/resolve"
printf 'nameserver 127.0.0.53\n' > "$T/root/run/systemd/resolve/stub-resolv.conf"

# Fake cmux: records every call; vpn status like the real CLI.
cat > "$T/bin/cmux" <<EOF
#!/bin/sh
echo "\$*" >> "$T/cmux.log"
case "\$1 \$2" in
  "vpn status") printf 'Terminal tunnel: up (user-space WireGuard)\nTunnel: down\n' ;;
  "vm ls") echo '{"vms":[{"id":"vm-1","displayName":"box","status":"'"\${FAKE_VM_STATUS:-running}"'"}]}' ;;
esac
EOF
# Fake getent: github.com resolves only when resolv.conf is a symlink (models the real fault).
cat > "$T/bin/getent" <<EOF
#!/bin/sh
[ "\$2" = github.com ] && [ -L "$T/root/etc/resolv.conf" ]
EOF
printf '#!/bin/sh\nexit 0\n' > "$T/bin/resolvectl"
printf '#!/bin/sh\necho active\n' > "$T/bin/systemctl"
for c in kiro-cli claude codex kirocrew; do
  printf '#!/bin/sh\necho "access_token=SECRET-LEAK-123"\necho "Logged in as someone@example.com"\n' > "$T/bin/$c"
done
chmod +x "$T/bin/"*

run() {  # env-isolated invocation
  env -i PATH="$T/bin:/usr/bin:/bin" HOME="$T/home" \
    CMUX_CONCIERGE_CMUX="$T/bin/cmux" CMUX_CONCIERGE_TRANSPORT=local \
    CMUX_CONCIERGE_ROOT="$T/root" CMUX_CONCIERGE_SUDO="" FAKE_VM_STATUS="${FAKE_VM_STATUS:-running}" \
    ${PROBE_FILE:+CMUX_CONCIERGE_PROBE_FILE="$PROBE_FILE"} bash "$TOOL" "$@"
}

echo "== decision logic (probe fixtures)"
cat > "$T/p-l1" <<'EOF'
REACH=ok
RESOLV_LINK=file
RESOLV_NS=10.32.0.28
STUB=present
DNS=fail
EGRESS_443=ok
SUDO=ok
VM_STATUS=running
EOF
PROBE_FILE="$T/p-l1" run check >"$T/o" 2>&1; rc=$?
check "broken resolv.conf -> exit 3" '[ $rc = 3 ]'
check "broken resolv.conf -> L1 finding" 'grep -q "L1|dns-broken" "$T/o"'
: > "$T/cmux.log"
PROBE_FILE="$T/p-l1" run heal --dry-run >"$T/o" 2>&1; rc=$?
check "heal --dry-run announces L1" 'grep -q "\[L1\] DRY-RUN would" "$T/o"'
check "heal --dry-run touches nothing" '[ ! -e "$T/root/etc/resolv.conf" ] && [ ! -s "$T/cmux.log" ]'

printf 'VM_STATUS=paused\nREACH=skipped-paused\n' > "$T/p-paused"
: > "$T/cmux.log"
PROBE_FILE="$T/p-paused" run heal --max-level 4 --allow-reboot >"$T/o" 2>&1; rc=$?
check "paused VM -> exit 2 needs-human" '[ $rc = 2 ] && grep -q "HUMAN|vm-paused" "$T/o"'
check "paused VM -> never resume/restart/new" '! grep -Eq "resume|restart|new" "$T/cmux.log"'

echo "== L1 real action in a sandbox root"
printf 'nameserver 10.32.0.28\n' > "$T/root/etc/resolv.conf"
run heal --vm box --max-level 1 >"$T/o" 2>&1; rc=$?
bk="$(ls "$T/root/etc/" | grep -c 'resolv.conf.bak-cmux-concierge-')"
check "L1 writes exactly one backup" '[ "$bk" = 1 ]'
check "L1 links resolv.conf to the stub" '[ "$(readlink "$T/root/etc/resolv.conf")" = /run/systemd/resolve/stub-resolv.conf ]'
check "L1 post-check passes (exit 0)" '[ $rc = 0 ] && grep -q "POST=dns-ok" "$T/o"'
check "K12: no token text in output" '! grep -q SECRET-LEAK "$T/o" && ! grep -q "@example.com" "$T/o"'

run heal --vm box --max-level 1 >"$T/o2" 2>&1; rc=$?
bk2="$(ls "$T/root/etc/" | grep -c 'resolv.conf.bak-cmux-concierge-')"
check "idempotent: 2nd run is a no-op (exit 0, no new backup)" '[ $rc = 0 ] && [ "$bk2" = 1 ]'

echo "== undo"
b="$(ls "$T/root/etc/" | grep 'resolv.conf.bak-cmux-concierge-' | head -1)"
run undo --backup "$T/root/etc/$b" >"$T/o" 2>&1
check "undo restores the original file" '[ ! -L "$T/root/etc/resolv.conf" ] && grep -q 10.32.0.28 "$T/root/etc/resolv.conf"'
run undo --backup /etc/passwd >"$T/o" 2>&1; rc=$?
check "undo refuses a non-concierge path" '[ $rc != 0 ] && grep -q not-a-concierge-backup "$T/o"'

echo "== $PASS passed, $FAIL failed"
[ "$FAIL" = 0 ]
