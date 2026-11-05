---
name: session-wrapup
description: Conduct a delegating session to 100% (recap, triggered lenses, HOTL/HITL scoreboard, HOTL before HITL) and only then close it via signoff
---

# /session-wrapup Command

Drive the current conductor session to 100% and then close it. Thin entry point over the
[`session-wrapup` skill](../skills/session-wrapup/SKILL.md), which composes `pulse`,
`goal-recovery`, `quiesce`, `council-gate`, `/hitl-digest` and `signoff`.

> Surfaces at runtime as `/maos:session-wrapup`.
> Naming: Anima-named (`session-wrapup`; rejected runner-up `helm`).

## Usage

```
/session-wrapup [--scope <session|repo:<name>|ticket:<id>>] [--dry-run]
```

| Step | What happens | Delegates to |
|------|--------------|--------------|
| 1 Recon + recap | intent tree with `[V]/[I]/[U]` tags | `pulse` · `goal-recovery` |
| 2 Lenses | only the lens whose trigger fires | trigger table in the skill |
| 3 Scoreboard | `%HOTL` · `%HITL` · `%SESSION` as n/d | `bin/scoreboard.py` |
| 4 Converge | HOTL first; then ONE HITL digest (≤ 3 cards) | `quiesce` · `council-gate` · `/hitl-digest` |
| 5 Close | gate `--gate close` exit 0, then git-cycle → review → house-keeping → boy-scout → lessons | `signoff` |

`--dry-run`: run Steps 1-3 and print the score and the plan; dispatch and write nothing.

Re-sent mid-round: answer only the delta; do not re-dispatch.
