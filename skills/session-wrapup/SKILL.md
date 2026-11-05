---
name: session-wrapup
description: |
  Conductor verb that drives a delegating session to 100% and only then closes it. One short
  invocation replaces the operator's long recurring wrap-up prompt: stay strategic and delegate;
  recover the intent tree (motivation → purpose → objectives → DoR/DoD → goals → tasks →
  deliverables → north-star); apply decision lenses only when their trigger fires; keep a
  deterministic HOTL/HITL scoreboard with a fixed denominator (`bin/scoreboard.py`); clear all
  HOTL work first (stop-bleeding → root-cause → no-loose-ends → session goals); consolidate the
  human residue into ONE HITL digest; then close with git-cycle → DIY PR review → house-keeping
  → boy-scout → lessons → `signoff`. Delegating does not waive responsibility: the delegator
  re-measures every delegated "done" at source before counting it. Missing agentic-tools go to
  `agentic-tool-pipeline`; every HITL candidate first passes `request-carried-authorization`.
  Thin composition: `pulse` + `goal-recovery` + `quiesce` + `request-carried-authorization` +
  `council-gate` + `/hitl-digest` + `agentic-tool-pipeline` + `signoff`; reimplements none.
  Triggers: "session-wrapup", "wrap up the session", "drive this session to 100%",
  "recap + score + close", "fechamento da sessão", "conduza até 100% e feche".
version: 0.2.0
triggers:
  - session-wrapup
  - wrap up the session
  - drive this session to 100%
  - recap score and close
  - fechamento da sessão
  - conduza até 100% e feche
metadata:
  version: "0.2.0"
  scope: AAIF cross-vendor
  family: worktree-lifecycle
  lifecycle-stage: operate
  id: MAOS-SKILL-session-wrapup
  type: skill
  status: active
  owner: maos-community
  composes: [pulse, goal-recovery, quiesce, request-carried-authorization, council-gate, hitl-digest, agentic-tool-pipeline, signoff]
  source_prompt: "operator wrap-up prompt v4 (private vault, `pages/session-wrapup.prompt.v4.md`); pointer only, no content copied"
  naming: "Anima-named (agent register, descriptive-canonical, family-aligned with signoff/quiesce/pulse) — `session-wrapup`; rejected runner-up `helm` (needs a gloss; collides with the Kubernetes package manager)."
  dogfooding_validation:
    cycles_completed: 0
    cycles_required: 2
    promotion_eligible: false
allowed-tools: Task, Read, Write, Edit, Bash, Grep, Glob
---

# Session Wrap-up — conduct to 100%, then close

## Purpose

Operators of delegating sessions tend to paste the same long "wrap-up" prompt again and again:
be the conductor, recap the intent, use the lenses, report completeness, finish the agent work
before bothering the human, then close cleanly. `session-wrapup` turns that prompt into one verb.

It owns only three things that no sibling has:

1. **The scoreboard** — `%HOTL`, `%HITL`, `%session` as numerator/denominator, computed by
   `bin/scoreboard.py`, which refuses fake progress (see §Scoreboard).
2. **The ordering** — all HOTL before any HITL; inside HOTL, stop-bleeding → root-cause →
   no-loose-ends → session goals.
3. **The lens triggers** — each lens runs only when its trigger fires (§Step 2).

Everything else is delegated to an existing skill.

## When to use / not use

Use in a **conductor (root) session** with delegated work in flight, when the operator wants it
driven to done and closed. **Re-sent mid-round:** answer only the delta (score, pending, blocked);
never re-dispatch what is already dispatched.

Not for: a single-item worker session (it lacks the whole-goal view — report to its conductor
instead); a plain end-of-thread close with nothing in flight (use `signoff`); driving PRs green
only (use `quiesce`).

## Composition

```
session-wrapup [--scope <session|repo:...|ticket:...>] [--dry-run]
  ├─ Step 1 RECON+RECAP ─→ pulse (objectives map, Eisenhower) + goal-recovery (intent tree)
  ├─ Step 2 LENSES ──────→ trigger table below (lens-dispatch optional)
  ├─ Step 3 SCOREBOARD ──→ bin/scoreboard.py  (own)
  ├─ Step 4 CONVERGE ────→ quiesce (HOTL to green) · council-gate (before any HITL)
  │                        └─ /hitl-digest (ONE digest for the human residue)
  └─ Step 5 CLOSE ───────→ git-cycle → DIY PR review → house-keeping → boy-scout → lessons
                           → signoff  (broadcast continuation, default-ON)
```

## Invariants (hold from start to end)

- **I1 Preserve behavior.** Code, configs and processes keep their behavior unless the operator
  asks. "More autonomy" changes HOW the agent decides, never WHAT the system does.
- **I2 Measure at source.** A fact without evidence is `[U]` unknown, not a guess. A worker's
  "done" is a claim until re-measured.
- **I3 HITL floor.** Only these reach the human: new credential, spend, irreversible in
  production, external send, operator taste/business call, third-party governance. Everything
  else is decided by the agent (the same six values are `HITL_FLOOR` in `bin/scoreboard.py`).
- **I4 No secret, PII or customer data in output.** Paths with `~`.
- **I5 Shared responsibility.** Delegating passes on execution, never accountability
  (`agentic-delegation`). The delegate measures; the delegator re-measures at source (`gh`,
  `git`, the file, the API) before reporting or counting it. If they diverge, trust the
  measurement and say so. In the scoreboard: `delegated: true` + `done` needs `remeasured: true`.

## Steps

### Step 1 — Recon + recap (delegated, read-only)

Delegate the recon: work ledger, PRs and checks, tickets, open HITL items, worktrees, session
memory. Then recover, tagging each node `[V]` verified / `[I]` inferred / `[U]` unknown:
motivation → purpose → objectives (originating · foundational · generational agentic DNA ·
primary · secondary · auxiliary) → DoR · DoD → goals → tasks → steps → deliverables →
north-star · expected result · feedback. A node with no path to a purpose: trace it back with
5 Whys or mark it orphaned.

### Step 2 — Lenses (only on trigger, never all by habit)

| Trigger | Lens |
|---|---|
| always | recon, OODA (outer loop) |
| > 3 pending items | Eisenhower; tie → GUT (gravity × urgency × trend, 1-5) |
| failure / regression | 5 Whys; recurring multiple causes → Ishikawa |
| delegating / writing a ticket | 5W2H (the worker brief IS the ticket-as-prompt) |
| before writing to anything shared | blast radius + impact estimate |
| > 1 owner | RACI |
| plan ≠ measurement | route adjustment (say what changed and why) |
| before escalating | `request-carried-authorization` first (did the request already carry it?), then avoid-HITL: `council-gate` and the four questions — measured? mine? undoable? would someone see my error? |
| a needed agentic-tool is missing or recurs ≥ 3× | `agentic-tool-pipeline` (forge decides the type, `anima` names it; dogfood before promotion) |

Report a lens only when it changed a decision.

### Step 3 — Scoreboard (same denominator for the whole round)

Items = decisions, actions and tasks of this session, each `HOTL` (the agent resolves) or `HITL`
(only the human resolves, I3). Mark every HOTL item a worker or subagent completed with
`"delegated": true`, and add `"remeasured": true` only after you checked it at source yourself
(I5). The gate cannot see whether you really re-measured: an omitted or false flag is the honest
default. Write them to a JSON file and run:

```bash
python3 skills/session-wrapup/bin/scoreboard.py items.json --baseline items.round-start.json
```

```
%HOTL    = HOTL done with evidence / HOTL total
%HITL    = HITL answered / HITL total
%SESSION = (HOTL done + HITL answered) / all items
```

The script refuses: a HOTL marked done without evidence (exit 3); a delegated HOTL marked done
without the delegator's own re-measurement (exit 3, I5); a HITL outside the floor —
a tactical question is HOTL, decide it (exit 3); an item that vanished from the baseline instead
of being closed (exit 4). New items are allowed: they grow the denominator. An empty
denominator reads `0/0 = 100%` (nothing waits on that side). Always show
numerator/denominator, and list pending items as id · kind · owner · next step.

### Step 4 — Converge to 100%

Order: (a) stop bleeding → (b) root cause → (c) no loose ends → (d) session goals.
Exhaust HOTL first: delegate independent work in parallel, dependent work in sequence, divisible
work recursively (`quiesce` drives PRs green). An approval block is removed only by a legitimate
path (e.g. a second account approves when author ≠ approver); never bypass a protection, a
required check or a security review.

Missing capability: if the work needs an agentic-tool that does not exist (a skill, command,
agent, hook, script, rule…), do not list or hand-roll one. Send the intent to
`agentic-tool-pipeline`: it searches similars, lets forge pick the type and anima the name, and
trains it by dogfood. Do not pre-decide the type here.

Before any item becomes HITL: run `request-carried-authorization` on it and route on its verdict.
A → act; B → act with a verified undo; C `kind=hard` → never act: it is blocked human residue
(file it under the closest I3 value; an operator refusal is already the answer, close it as
answered); C `kind=ladder` → hand it to `council-gate`. Record the grant, its basis and the undo.

Only then build ONE HITL digest (`/hitl-digest`): at most 3 cards, high urgency and human domain
first, each with WHAT IT IS · WHAT IT IS FOR · IMPACT OF YES / IMPACT OF NO and a
recommendation. Always show the total still open, not only this round's 3.

### Step 5 — Close (only when the gate passes)

```bash
python3 skills/session-wrapup/bin/scoreboard.py items.json --gate close   # exit 0 = may close
```

Then: git-cycle → DIY PR review (no paid bots; required CI green) → house-keeping (merged
worktrees and branches; no `-D`, `--force`, `reset --hard`) → boy-scout (small fixes only) →
lessons learned (only a durable defect or fact, once) → `signoff`.

## Definition of Done

`%HOTL = 100%` with evidence · every delegated "done" re-measured by the delegator at source
(I5) · every HITL passed `request-carried-authorization` first · every open HITL is in the digest with a recommendation · zero
orphan worktree/branch created by this session · lessons saved · `signoff` emitted.
If the DoD does not close this round: report the score and the next step, and keep going.

## Acceptance scenarios (from real wrap-up failures)

Run `bash skills/session-wrapup/tests/run-tests.sh`. Each scenario also has a mutation check:
the guard is removed from a temp copy and the scenario must flip.

| # | Failure it stops | Expected |
|---|---|---|
| A1 | a percentage with no denominator | prints `n/d = p%` |
| A2 | "done" reported from a worker's word | exit 3 |
| A3 | a tactical question pushed to the human | exit 3 |
| A4 | shrinking the denominator to raise the % | exit 4 |
| A5 | new work found mid-round | allowed, denominator grows |
| A6 | closing while HOTL is still open | exit 5 |
| A7 | closing with a HITL the human never saw | exit 5 |
| A8 | a legitimate close | exit 0 |
| A10 | a delegated "done" counted on the worker's word | exit 3 |
| A11 | a delegated "done" the delegator re-measured | exit 0 |
| A12 | `remeasured: "false"` (a string) slipping past the guard | exit 3 |

## Anti-patterns

1. Reimplementing recap, PR convergence, the digest or the close-out — compose the siblings.
2. Running every lens every time — that is ceremony, not analysis.
3. Asking the human anything outside the I3 floor, or anything the request already authorized.
4. Treating "I delegated it" as "it is done" (I5).
5. Enumerating new tool kinds by hand instead of routing to `agentic-tool-pipeline`.
6. Reporting a % computed by hand.

## Related

- `skills/pulse/SKILL.md`, `skills/goal-recovery/SKILL.md` — Step 1.
- `skills/quiesce/SKILL.md`, `skills/council-gate/SKILL.md` — Step 4.
- `skills/request-carried-authorization/SKILL.md` — pre-HITL step 0.
- `skills/agentic-tool-pipeline/SKILL.md` — create/train a missing agentic-tool.
- `skills/agentic-delegation/SKILL.md` — accountability stays with the delegator (I5).
- `commands/hitl-digest.md` — the single digest.
- `skills/signoff/SKILL.md` — Step 5 close-out.
- `commands/session-wrapup.md` — the `/session-wrapup` entry point.

## License

MIT (matches the repo `LICENSE`).
