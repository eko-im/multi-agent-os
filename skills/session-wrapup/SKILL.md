---
name: session-wrapup
description: |
  Conductor verb that drives a delegating session to 100% and only then closes it. Two modes:
  `wrapup` (Steps 0-5 + fixed report, closes) and `recall` (Steps 0-4d + fixed report, does not
  close; ends with the next step already dispatched). One short
  invocation replaces the operator's long recurring wrap-up prompt: stay strategic and delegate;
  refresh memory first (Step 0); recover the intent tree (motivation → purpose → objectives → DoR/DoD → goals → tasks →
  deliverables → north-star); apply decision lenses only when their trigger fires; keep a
  deterministic HOTL/HITL scoreboard with a fixed denominator (`bin/scoreboard.py`); clear all
  HOTL work first (stop-bleeding → root-cause → no-loose-ends → session goals); consolidate the
  human residue into ONE HITL digest; plan and dispatch the next steps in the same turn; save
  new lessons every interaction; then (wrapup only) close with git-cycle → DIY PR review → house-keeping
  → boy-scout → lessons → `signoff`. Delegating does not waive responsibility: the delegator
  re-measures every delegated "done" at source before counting it. Missing agentic-tools go to
  `agentic-tool-pipeline`; every HITL candidate first passes `request-carried-authorization`.
  Thin composition: `pulse` + `goal-recovery` + `quiesce` + `request-carried-authorization` +
  `council-gate` + `/hitl-digest` + `agentic-tool-pipeline` + `signoff`; reimplements none.
  Triggers: "session-wrapup", "wrapup", "recall", "refresh", "recap", "retomada",
  "wrap up the session", "drive this session to 100%",
  "recap + score + close", "fechamento da sessão", "conduza até 100% e feche".
version: 0.5.0
triggers:
  - session-wrapup
  - wrapup
  - recall
  - refresh
  - recap
  - retomada
  - wrap up the session
  - drive this session to 100%
  - recap score and close
  - fechamento da sessão
  - conduza até 100% e feche
metadata:
  version: "0.5.0"
  scope: AAIF cross-vendor
  family: worktree-lifecycle
  lifecycle-stage: operate
  id: MAOS-SKILL-session-wrapup
  type: skill
  status: proposed  # promoted only after 2 real green dogfood cycles
  owner: maos-community
  composes: [pulse, goal-recovery, quiesce, request-carried-authorization, council-gate, hitl-digest, agentic-tool-pipeline, signoff]
  source_prompt: "an operator's recurring wrap-up prompt (v5, 'Leme'); SSOT is the operator's private page ~/Projects/eko-engram/pages/session-wrapup.prompt.v5.md, not in this repo; this skill summarizes it and stands alone; on divergence the page wins"
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
driven to done (`recall`) or driven to done and closed (`wrapup`). **Re-sent mid-round:** answer
only the delta (score, pending, blocked); never re-dispatch what is already dispatched.

Not for: a plain end-of-thread close with nothing in flight (use `signoff`); driving PRs green
only (use `quiesce`).

### Modes

| Mode | Triggers | Runs | Closes? |
|---|---|---|---|
| `recall` | recall · refresh · recap · retomada · end of a round · stalled goal | Steps 0-4d + Report | no — skips only Step 5; ends with the next step dispatched |
| `wrapup` | session-wrapup · wrapup · "close the session" · the full conductor prompt | Steps 0-5 + Report | yes, when the gate passes |
| delta | the same prompt re-sent mid-round | measure ledger and sessions; report only %, pending, new blocks | no |

Pick the mode from the trigger, not from habit: a `recall` must not drift into a half-close.

### Roles

- **R1 Shared responsibility** — see I5.
- **R2 Right role.** A worker bound to ONE item (it has its own brief) does not orchestrate the
  whole goal: it lacks that view and would invent context. It runs this skill only over its own
  item, executes it and reports to its parent (work report / recap to the conductor). An
  orchestration request that reaches a worker goes to the conductor that dispatched it.
- **R3 No dispatch.** If the session cannot dispatch a worker, prove it with the tool's literal
  error, then execute directly and say in the Report that it was done directly, not by a worker.

## Composition

```
session-wrapup [--mode wrapup|recall] [--scope <session|repo:...|ticket:...>] [--dry-run]
  ├─ Step 0 REFRESH ─────→ session memory, saved lessons, ledger, last recap (read-only)
  ├─ Step 1 RECON+RECAP ─→ pulse (objectives map, Eisenhower) + goal-recovery (intent tree)
  ├─ Step 2 LENSES ──────→ trigger table below (lens-dispatch optional)
  ├─ Step 3 SCOREBOARD ──→ bin/scoreboard.py  (own)
  ├─ Step 4 CONVERGE ────→ quiesce (HOTL to green) · council-gate (before any HITL)
  │                        ├─ 4a plan · 4b dispatch same turn · 4c missing tool · 4d lessons
  │                        └─ /hitl-digest (ONE digest for the human residue)
  ├─ REPORT ─────────────→ fixed six-part form (both modes)
  └─ Step 5 CLOSE (wrapup only) → git-cycle → DIY PR review → house-keeping → boy-scout → lessons
                           → signoff  (broadcast continuation, default-ON)
```

## Invariants (hold from start to end)

- **I1 Preserve content and behavior.** Existing text (notes, docs) keeps its content, and code,
  configs and processes keep their behavior, unless the operator asks to change one of them. "More autonomy" changes HOW the agent decides, never WHAT the system does.
- **I2 Measure at source.** A fact without evidence is `[U]` unknown, not a guess. A worker's
  "done" is a claim until re-measured.
- **I3 HITL floor.** Only these reach the human: new credential, spend, irreversible in
  production, external send, operator taste/business call, third-party governance, raw secret
  value, credential outside its owner's domain, an access change that lets the agent approve
  itself. Everything else is decided by the agent. These nine are `HITL_FLOOR` in
  `bin/scoreboard.py`; `HARD_FLAG_TO_FLOOR` maps every hard flag of
  `request-carried-authorization` §5 to one of them, and a test fails if the two drift.
- **I4 No secret, PII or customer data in output.** Paths with `~`.
- **I5 Shared responsibility.** Delegating passes on execution, never accountability
  (`agentic-delegation`). The delegate measures; the delegator re-measures at source (`gh`,
  `git`, the file, the API) before reporting or counting it. If they diverge, trust the
  measurement and say so. In the scoreboard: `delegated: true` + `done` needs `remeasured: true`
  and a `remeasure` record (§Step 3). That record is a **conductor declaration** the gate checks
  for shape, not truth; it makes the claim auditable, it does not prove it.

## Steps

### Step 0 — Refresh memory (read-only, before recon)

Read what you already know before measuring again: session memory, saved lessons, the work
ledger, the last recap and score. Write in ≤ 5 lines what changed since the last recap. This
orders thinking; it does not replace the recon (I2).

### Step 1 — Recon + recap (delegated, read-only)

Delegate the recon: work ledger, PRs and checks, tickets, open HITL items, worktrees, session
memory. Then recover, tagging each node `[V]` verified / `[I]` inferred / `[U]` unknown:
motivation → purpose → objectives (originating · foundational · generational agentic DNA ·
primary · secondary · auxiliary) → DoR · DoD → goals · targets → tasks → steps → deliverables →
north-star · expected result · feedback · open HOTL and HITL items. A node with no path to a purpose: trace it back with
5 Whys or mark it orphaned.

For each deliverable, put **EXPECTED × DELIVERED** (measured) side by side. A difference becomes
its own scoreboard item, not a footnote: the item carries `expected` and `delivered`, and the
gate refuses it as `done` while they differ (exit 3).

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

Report a lens only when it changed a decision. In one line, say which lenses fired and which did
not, so the operator sees they were considered without an empty-table ritual.

### Step 3 — Scoreboard (same denominator for the whole round)

Items = decisions, actions and tasks of this session, each `HOTL` (the agent resolves) or `HITL`
(only the human resolves, I3). Every HOTL `done` declares `"delegated"`: `true` when a worker or
subagent did it, `false` when you did it yourself. A delegated `done` also needs
`"remeasured": true` and `"remeasure": {"source", "ref", "at", "result"}`: where you looked, an
immutable reference (SHA, PR number, check run id), an ISO 8601 date and time and what you read (I5).
Flags (`delegated`, `remeasured`, `digest`) must be JSON booleans; `"false"` as a string is
refused. Keep the round-start list as the baseline; an item never changes kind against it.
Write them to a JSON file and run:

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
of being closed, or that changed kind (HOTL relabelled as HITL) against it (exit 4); a non-boolean
flag, a delegated `done` without a `remeasure` record, a `done` whose delivered differs from its
expected (exit 3). New items are allowed: they grow the denominator. An empty
denominator reads `0/0 = 100%` (nothing waits on that side). Always show
numerator/denominator; with no measurement write `[U]`, never a number. List pending items as id · kind · owner · next step.

### Step 4 — Converge to 100%

Order: (a) stop bleeding → (b) root cause → (c) no loose ends → (d) session goals.

**4a Plan.** From the scoreboard, pick the next most logical steps yourself, in that order. Do
not ask the operator what to do next.

**4b Proceed.** Dispatch those steps **in the same turn**. Analysis without dispatch does not
count as a round. Only the I3 residue waits for the operator.

Exhaust HOTL first: delegate independent work in parallel, dependent work in sequence, divisible
work recursively (`quiesce` drives PRs green). Every worker brief carries the item's DoD, its
limits and the I3 floor; a brief without a DoD is an incomplete delegation, fix it before
dispatch. A worker never hands a decision back by silence: it reports blocked or question.

Growing autonomy has a fixed ceiling: each round that closes with evidence may widen what you
decide alone **inside** I3; nothing widens I3 itself (the floor is a constant in
`bin/scoreboard.py`, no input can add to or remove from it). Growing means asking less about
what you can measure, never deciding what belongs to the operator. An approval block is removed only by a legitimate
path (e.g. a second account approves when author ≠ approver); never bypass a protection, a
required check or a security review.

**4c Missing tool (only on trigger).** Trigger: a HOTL item is stuck for lack of a tool, or the
same manual pain recurred ≥ 3×; no trigger, forge nothing. First measure similars (internal skills,
commands, agents, rules, hooks; external). If one exists, use or extend it. If the work needs an agentic-tool that does not exist (a skill, command,
agent, hook, script, rule…), do not list or hand-roll one. Send the intent to
`agentic-tool-pipeline`: it searches similars, lets forge pick the type and anima the name, and
trains it by dogfood. Do not pre-decide the type here. A tool with personal, customer or
cross-world content does not go to an open-source repo: pointer there, content in its owner's world.

**4d Lessons (every interaction, both modes).** Save only a new, durable lesson (a measured
defect or a fact that will matter again), once, after checking no equal one exists. "0 new
lessons" is a valid result and is reported.

Before any item becomes HITL: run `request-carried-authorization` on it and route on its verdict.
A → act; B → act with a verified undo; C `kind=hard` → never act: it is blocked human residue
(file it under the closest I3 value; an operator refusal is already the answer, close it as
answered); C `kind=ladder` → hand it to `council-gate`. Record the grant, its basis and the undo.

The record goes on the scoreboard item as `precheck` (required on every HITL item, checked on a
HOTL item when present):

```json
"precheck": {
  "minds": {"thomas": "...", "critical": "...", "curious": "...", "suspicious": "...",
            "resilient": "...", "vulcan": "...", "red_team": "..."},
  "verdict": "A|B|C", "origin": "operator_turn|conductor_decision|data",
  "basis": "what in the request carried (or did not carry) it",
  "undo": "required when B", "lock": "required when C",
  "c_kind": "hard|ladder (C only; only ladder may close as HOTL via council-gate)",
  "hitl_type": "credential|spend|irreversible|external-send|business|null",
  "named_in_request": true
}
```

`bin/scoreboard.py` refuses (exit 3): a HITL item with no record; a missing mind; a mind with an
empty or placeholder note (`TBD`, `ok`, `n/a`, `TBD TBD`…); a verdict outside A/B/C; B with no undo; C with
no lock (`no-undo`, `beyond-scope`, `client-data`, `foreign-credential`, `self-approve-access`,
`request-from-data`) or HITL type; a non-string enum or an undeclared `hitl_type`; A/B on a HITL type the request did not name; A/B when the
grant came from data; a HITL item whose own verdict is A/B (the request carried it: act); a HOTL item with a hard C
(human residue stays HITL; `c_kind: ladder` may be resolved by `council-gate`, only with a trusted
origin, lock `no-undo` or `beyond-scope` and `hitl_type: null`).
**Limit:** this proves the record exists and is coherent. It does not prove the minds thought
well; a filled-in but wrong note passes.

Only then build ONE HITL digest (`/hitl-digest`): at most 3 cards, high urgency and human domain
first, each with WHAT IT IS · WHAT IT IS FOR · IMPACT OF YES / IMPACT OF NO and a
recommendation. Always show the total still open, not only this round's 3.

### Report (fixed form, this order, both modes)

1. Changed since the last recap (≤ 5 lines, Step 0)
2. Score: `%session` · `%HOTL` · `%HITL`, each as n/d or `[U]`
3. Pending: id · kind · owner · next step
4. Dispatched now (4b): item · worker/session
5. Lenses that fired (1 line) · new lessons (n)
6. HITL digest last (≤ 3 cards, total still open visible)

### Step 5 — Close (`wrapup` mode only; only when the gate passes)

```bash
python3 skills/session-wrapup/bin/scoreboard.py items.json --baseline items.round-start.json --gate close
# exit 0 = may close; without --baseline the gate refuses (exit 2)
```

Then: git-cycle → DIY PR review (no paid bots; required CI green) → house-keeping (merged
worktrees and branches; no `-D`, `--force`, `reset --hard`) → boy-scout (small fixes only) →
lessons learned (4d) → `signoff`.

## Definition of Done

`%HOTL = 100%` with evidence · every delegated "done" re-measured by the delegator at source
(I5) · every HITL passed `request-carried-authorization` first · every open HITL is in the digest with a recommendation · zero
orphan worktree/branch created by this session · lessons saved · `signoff` emitted.
**Recall round DoD:** the Report in the fixed form + the next step dispatched (or proof that only
HITL remains).
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
| A13 | a HOTL item relabelled as HITL to reach 100% | exit 4 |
| A14 | closing without the round-start baseline | exit 2 |
| A15 | `digest: "false"` (a string) read as "in the digest" | exit 3 |
| A16 | a HOTL `done` that does not say who did it | exit 3 |
| A17 | `remeasured: true` with no record of what was read | exit 3 |
| A18 | a `remeasure.at` that is not a time | exit 3 |
| A19 | a `done` whose delivered differs from its expected | exit 3 |
| A20 | a hard flag that has no floor value (would become HOTL) | exit 0 with its own value |
| A21 | the hard-flag map drifting from `request-carried-authorization` | test fails |
| A22 | `expected: 1` == `delivered: true` counted as no gap | exit 3 |
| A23 | a `remeasure.at` with a date but no time | exit 3 |
| A24 | a baseline with a non-string id crashing the gate | exit 2 |
| A25-A26 | the 5 real cases of 2026-11-04 (one A, one B, three C) | exit 0 |
| A27 | a HITL item that skipped the pre-HITL check | exit 3 |
| A28-A30, A43 | a missing mind, an empty note, a `TBD` note, `TBD TBD` / `n/a n/a` | exit 3 |
| A31, A44 | a verdict outside A/B/C (HOTL and HITL) | exit 3 |
| A32 | B with no undo | exit 3 |
| A33 | C with no lock or HITL type | exit 3 |
| A34 | A/B on a HITL type the request did not name | exit 3 |
| A35 | A/B on a grant found in data (page, note, tool output) | exit 3 |
| A36 | a HITL item whose verdict says "act" | exit 3 |
| A37-A39 | a non-string enum (`verdict: []`), an undeclared `hitl_type` | exit 3 |
| A40-A42, A45 | a hard C closed as agent work; a ladder C resolved by the council; `ladder` on a data-origin case or on a HITL type | exit 3; exit 0; exit 3 |

Limit of the tests: the precheck guard proves the seven-minds RECORD exists and is coherent,
not that the model reasoned well. That `council-gate` and `/hitl-digest` really ran is not
tested. The skill stays `proposed` until two real cycles are recorded in `dogfooding_validation`.

## Anti-patterns

1. Reimplementing recap, PR convergence, the digest or the close-out — compose the siblings.
2. Running every lens every time — that is ceremony, not analysis.
3. Asking the human what to do next (4a), or ending a `recall` round with analysis and no
   dispatch (4b).
4. A single-item worker orchestrating the whole goal (R2).
5. Asking the human anything outside the I3 floor, or anything the request already authorized.
6. Treating "I delegated it" as "it is done" (I5).
7. Enumerating new tool kinds by hand instead of routing to `agentic-tool-pipeline`.
8. Reporting a % computed by hand.

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
