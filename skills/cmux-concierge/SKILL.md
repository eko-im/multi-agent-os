---
name: cmux-concierge
version: "0.1.0"
description: >-
  Unattended caretaker for cmux-cloud VMs. Diagnoses a VM from the operator's Mac (local cmux
  tunnel, VM state, ssh reach, DNS, resolver, egress, and the login status of kiro-cli, claude,
  codex and kirocrew) and heals it up a ladder from lightest to heaviest: L1 relink
  /etc/resolv.conf to the systemd-resolved stub (backup + undo), L2 restart the resolver, L3
  restart the local cmux system tunnel, L4 reboot the VM (opt-in). Drives the deterministic
  executor `bin/cmux-concierge` (check · heal · undo; --dry-run). Never logs in, never prints a
  token, never resumes/creates a VM or reserves pool capacity: those come back as NEEDS-HUMAN.
  Use when "the VM has no DNS", "Could not resolve host on the cmux box", "is eko VM healthy",
  "agent on the VM says Sign in", "heal the cmux VM", "cmux VM unreachable".
allowed-tools: Read, Bash
evals:
  should_trigger:
    - "The cmux VM can't resolve github.com, fix it"
    - "Health-check my cmux cloud machine"
    - "Kiro on the cloud VM keeps asking me to sign in, why?"
    - "Is the resolv.conf on the cmux box broken again?"
    - "The cmux VM stopped answering ssh, recover it"
  should_not_trigger:
    - "Create a new cmux cloud VM (spend: human; route to cmux-cloud-vm)"
    - "cmux notifications or hooks are not firing in the app (route to cmux-diagnostics)"
    - "Rebind a cmux keyboard shortcut (route to cmux-keyboard-shortcuts)"
    - "Log kiro-cli in on the VM for me (human-only sign-in)"
---

# cmux-concierge

## §0 — BEING > Rules

This skill serves the operator's intent: keep the cmux-cloud VMs usable without a human in the
loop. If a rung obstructs that, skip it and log `Skipped <rung> — BEING > Rules`. The HUMAN
boundary is not a rung and is never skipped: sign-in, credentials, and anything that spends
(resume a paused VM, create a VM, resize, reserve pool) always return NEEDS-HUMAN.

## Purpose

cmux-cloud VMs fail in a few repeatable ways. The one measured on 2026-11-23: the platform
rewrote `/etc/resolv.conf` to a dead upstream (`10.32.0.28`), bypassing a working
systemd-resolved (DoT fallback). Every DNS lookup failed, and the harnesses on the VM could not
refresh their tokens, so they showed "Sign in". The fix was one relink to the stub
`127.0.0.53`. This skill turns that diagnosis and fix into a repeatable, guarded ladder.

| Layer | Artifact | Role |
|---|---|---|
| Knowledge + routing | `skills/cmux-concierge/SKILL.md` | when to use, ladder, boundaries, routing |
| Executor | `bin/cmux-concierge` | `check` · `heal` · `undo`, idempotent, `--dry-run` |
| Tests | `bin/tests/cmux-concierge.test.sh` | hermetic: fake cmux, sandbox root, no ssh |

## Use

```bash
bin/cmux-concierge check --ssh <ssh-alias> --vm <id|displayName>      # read-only
bin/cmux-concierge heal  --ssh <ssh-alias> --vm <id> --dry-run         # show the plan
bin/cmux-concierge heal  --ssh <ssh-alias> --vm <id>                   # L1..L3
bin/cmux-concierge heal  --ssh <ssh-alias> --vm <id> --max-level 4 --allow-reboot
bin/cmux-concierge undo  --ssh <ssh-alias> --backup /etc/resolv.conf.bak-cmux-concierge-<ts>
```

Transport: ssh first (`BatchMode`, 10 s timeout); if ssh fails and `--vm` is known, the same
script runs through `cmux vm exec <id> -- bash -c` (the user-space tunnel). `cmux vm exec`
takes the id only; `--vm` also accepts the displayName or slug and resolves it from
`cmux vm ls --json`.

Exit codes: `0` healthy · `1` error/usage · `2` needs-human · `3` degraded (a rung can fix it).

## The ladder (GUARD -> ACTION -> POST-CHECK)

| Rung | Guard (must all hold) | Action | Post-check |
|---|---|---|---|
| L1 fix-resolv | DNS fails · stub present · resolv.conf not already the stub | `cp -a` backup to `/etc/resolv.conf.bak-cmux-concierge-<UTC>`, then `ln -sfn /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf` | `getent hosts github.com` |
| L2 restart-resolver | DNS fails · resolv.conf already on the stub · tcp/443 egress ok | `systemctl restart systemd-resolved` | `getent` |
| L3 restart-tunnel | VM unreachable by ssh and exec · system tunnel was up | `cmux vpn down && cmux vpn up` (local Mac) | re-probe |
| L4 reboot | `--allow-reboot` · `--vm` resolves · VM `running` · still unhealthy | `cmux vm restart <id>`, wait up to 300 s | re-probe; L1 is re-checked (a reboot can rewrite resolv.conf again) |

Each rung re-checks its own guard on the VM, so a second run is a no-op. heal stops at the first
rung after which nothing fixable remains. `sudo -n` only: no passwordless sudo is NEEDS-HUMAN.

## Boundaries (NEEDS-HUMAN, exit 2)

- A harness shows `not-logged-in` or `unknown`. Sign-in is human-only. Fix DNS first: a fresh
  login on a VM without DNS expires again.
- VM `paused`: resuming restarts billing. VM `not-found`: wrong `--vm`.
- System tunnel down and the VM unreachable: `cmux vpn up` may need macOS approval.
- `*.cmux.internal` not resolving (`INTERNAL_DNS=fail`) is reported as INFO: only the cmux
  platform resolver serves it, so it needs a cmux ticket, not a rung.

## K12 — secrets

Login probes run on the VM and print one word per harness (`logged-in` · `not-logged-in` ·
`absent` · `unknown`), never the command output. The executor never calls `kirocrew token` or
any login verb. The test suite asserts a fake token in tool output never reaches the report.

## Routing

| Ask | Route |
|---|---|
| create, resize, pause, run agents, workspaces on a VM | `cmux-cloud-vm` (vendor skill) |
| cmux app hooks, notifications, socket, session restore | `cmux-diagnostics` (vendor skill) |
| MCP config of the harnesses on the VM | `harness-concierge` |
| name a new tool | `anima` · forge a new tool: `agentic-tool-forge` |

## Tests

`bash bin/tests/cmux-concierge.test.sh` — 13 checks with a fake `cmux`, fake `getent` (resolves
only when resolv.conf is a symlink, modelling the real fault), a sandbox root and fake harness
CLIs that print a fake token. Test seams (env, defaults = the real host):
`CMUX_CONCIERGE_TRANSPORT=local`, `CMUX_CONCIERGE_ROOT`, `CMUX_CONCIERGE_SUDO`,
`CMUX_CONCIERGE_PROBE_FILE`, `CMUX_CONCIERGE_CMUX`. Mutation-checked: removing the paused guard,
echoing raw login output, or removing the backup step each makes the suite fail.

## §DUED sunset

Deprecate when ANY: cmux ships a native guest health/heal verb (E1) · the platform stops
rewriting resolv.conf and the ladder has not fired for 90 days (E5) · operator retraction (E4).

## §Refs

- Forged with `agentic-tool-forge` (type: skill + executor, family `*-concierge`, precedent
  `harness-concierge` + `bin/harness-mcp-sync`); name decided by the operator, collision-swept
  with `anima` §5.
- Evidence: the DNS diagnosis and fix of 2026-11-23 on a cmux-cloud VM (resolv.conf rewritten
  to a dead upstream on `cmux vm pause/resume`), and the 2026-11-22 remote recon that traced
  "Sign in to Kiro" to DNS failure.
- Cross-link slug: `[[cmux-concierge]]`.

## Changelog

| Version | Date | Change |
|---|---|---|
| 0.1.0 | 2026-11-23 | Genesis: check/heal/undo executor, L1-L4 ladder, K12 login probes, hermetic tests. |
