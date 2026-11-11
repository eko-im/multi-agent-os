---
name: session-wrapup
description: Conduct a delegating session to 100% (refresh, recap, triggered lenses, HOTL/HITL scoreboard, HOTL before HITL, dispatch in the same turn, fixed report); wrapup mode then closes via signoff, recall mode (recall/refresh/recap/retomada) does not close
---

# /session-wrapup Command

Drive the current conductor session to 100% and then close it. Thin entry point over the
[`session-wrapup` skill](../skills/session-wrapup/SKILL.md), which composes `pulse`,
`goal-recovery`, `quiesce`, `request-carried-authorization`, `council-gate`, `/hitl-digest`,
`agentic-tool-pipeline` and `signoff`.

> Surfaces at runtime as `/maos:session-wrapup`.
> Naming: Anima-named (`session-wrapup`; rejected runner-up `helm`).

## Usage

```
/session-wrapup [--mode wrapup|recall] [--scope <session|repo:<name>|ticket:<id>>] [--dry-run]
```

`--mode` defaults from the trigger: `recall` for recall · refresh · recap · retomada · end of a
round · stalled goal (Steps 0-4d + Report, no close); `wrapup` otherwise (Steps 0-5 + Report).
Any request to close wins: "recap + score + close" is `wrapup`.

| Step | What happens | Delegates to |
|------|--------------|--------------|
| 0 Refresh | read memory, lessons, ledger, last recap; ≤ 5 lines of what changed | — |
| 1 Recon + recap | intent tree with `[V]/[I]/[U]` tags | `pulse` · `goal-recovery` |
| 2 Lenses | only the lens whose trigger fires | trigger table in the skill |
| 3 Scoreboard | `%HOTL` · `%HITL` · `%SESSION` as n/d | `bin/scoreboard.py` |
| 4 Converge | HOTL first (delegator re-measures every delegated "done"); missing tool → pipeline; pre-HITL authorization check; then ONE HITL digest (≤ 3 cards); 4a plan and 4b dispatch in the same turn; 4d new lessons | `quiesce` · `agentic-tool-pipeline` · `request-carried-authorization` · `council-gate` · `/hitl-digest` |
| Report | fixed 6 parts: changed · score · pending · dispatched now · lenses + lessons · HITL digest last | — |
| 5 Close (wrapup only) | gate `--gate close --baseline <round-start>` exit 0, then git-cycle → review → house-keeping → boy-scout → lessons | `signoff` |

`--dry-run`: run Steps 1-3 and print the score and the plan; dispatch and write nothing.

Re-sent mid-round: answer only the delta; do not re-dispatch.

A single-item worker runs it only over its own item and reports to its conductor (R2).
