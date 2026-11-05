# Dogfood — `session-wrapup` dry-run on its own forging task (2026-11-05)

**Case:** the real task that forged this skill (recon → type → name → write → tests → PR →
pointer PR → house-keeping). Items at round start: `2026-11-05-session-wrapup-dryrun.start.json`.
Items mid-round: `2026-11-05-session-wrapup-dryrun.now.json`.

**Cycle status:** dry-run only. Counts as 0 of the 2 real cycles required for promotion.

## Run 1 — a tactical question filed as HITL

The first draft of the items had `should-i-merge` as HITL (`floor: tactical`).

```
$ scoreboard.py now.json --baseline start.json
INVALID item[8] 'should-i-merge': HITL outside the floor ('tactical'); allowed: [...] — otherwise it is HOTL, decide it
exit=3
```

Decision taken by rule: merging a reversible, green PR is HOTL. The item was removed from HITL.

## Run 2 — the real score mid-round

```
$ scoreboard.py now.json --baseline start.json
%HOTL     5/8 = 62.5%
%HITL     0/0 = 100.0%
%SESSION  5/8 = 62.5%
  pending pr-open-review-merge [HOTL]
  pending pointer-pr [HOTL]
  pending house-keeping [HOTL]
exit=0
```

An empty HITL denominator reads 100%: nothing waits on the human.

## Run 3 — the close gate refuses an early close

```
$ scoreboard.py now.json --gate close
GATE close not met: HOTL 5/8, HITL not in digest: []
exit=5
```

## What the dry-run showed

| Check | Result |
|---|---|
| Tactical question kept away from the human | yes (exit 3) |
| Score shown as n/d | yes |
| Early close refused | yes (exit 5) |
| Gap found | none in the script; `0/0 = 100%` documented here |
