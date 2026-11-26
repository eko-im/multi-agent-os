---
name: on-call-shift
description: |
  Hold an on-call shift as one accountable holder: assume it with a principal, scope, backlog,
  capacity and budget (items, money measured as a delta, deadline); keep a persisted lease and
  cursor; run a work loop that dispatches in the same turn as the intake, never ends a turn
  while eligible work, budget and time remain, and idles only with a host wakeup armed (OMP: a
  background job); close at the principal's cutoff; and hand off only when an identified successor acknowledges
  the cursor, in-flight work and open gates. When no backlog was given or it is exhausted, read
  every authorized tracker (issue trackers and pull requests), merge the same intent across them,
  respect owners and RACI/DARCI, and adopt one eligible item or wait with a stated reason. Keeps
  tick, notification, wakeup and resume distinct and reports DEGRADED when the runtime cannot
  wake the exact supervisor; never claims "always on". Counts a result as done only when the
  intended recipient received it and is satisfied (UDV), checks blast radius before every
  effect, and lets only a pre-authorized successor take over a dead holder. Use for "take the on-call shift",
  "hold the shift overnight", "cover the queue until relieved", "hand the shift to the next
  agent", "assumir o plantão", "passar o plantão". Composes ooda-loop, work-drain, work-compass
  and spec-backlog-ticket-reconciler; reimplements none of them.
allowed-tools: "Read Write Edit Bash Grep Glob"
compatibility: "Portable Agent Skills core. Host-neutral: every runtime maps timer, wakeup, tracker connectors and identity through an adapter that declares its capabilities; a missing capability fails closed or reports DEGRADED. No vendor runtime is required."
metadata:
  version: "0.3.0"
  scope: AAIF cross-vendor
  family: orchestration-convergence
  cross_link_slug: on-call-shift
  dogfood_status: unit-scenarios-only  # engine scenarios pass; live night-20261125 (v0.2.0) delivered 0 items -> v0.3.0 work loop; no live v0.3.0 shift yet
---

# On-Call Shift

A thin **shift holder**. It answers one question the loop skills do not own: *who holds the
watch right now, on what lease, at what cursor, and to whom it passes*. The work inside the
shift is done by the skills it composes.

| Need | Owner skill (composed, not copied) |
|---|---|
| decide and act on one item (OODA outside, PDCA inside) | `ooda-loop` |
| drain a discovered register item by item | `work-drain` |
| discover scattered work across trackers and sessions | `work-compass` |
| reconcile the same intent across trackers and specs | `spec-backlog-ticket-reconciler` |
| triage urgency, deferred triggers | `pulse` |
| continuation seed at the end of the shift | `postflight` / `signoff` |
| successor cold start from artifacts | `session-reentry` |
| lock semantics for shared files | `anti-conflict` |

## §0 — BEING > Rules (foundational)
Serves the principal's intent. Only a presentation nicety may be skipped, logged as
`Skipped <step> — BEING > Rules`. Lease, ACK, gate, budget, privacy and independent-review checks
never skip; an unevidenced one fails closed. HUMAN_DOMAIN (secrets · production personal data ·
irreversible actions · cross-org · spend) is a hard gate: wait and report, never self-authorize.

## Inputs (all required at intake; none is guessed)

| Field | Meaning |
|---|---|
| `principal` | who owns the shift and may stop or revoke it |
| `scope` | accounts, organizations, repos and trackers the shift may touch (one string or a list) |
| `backlog` | a reference to the principal's explicit list (path#section, URL, query); its items start with `start_item`. `null` only when no list was given (then adoption rules apply) |
| `capacity` | maximum items in flight at once |
| `budget` | the principal's terms: a count of items (`adoptions`), a money cap (`currency`, `amount`, optional `freeze_at` and `baseline`) measured as a delta from a baseline, and/or a `deadline` in epoch seconds, UTC (a millisecond epoch is refused; the opening log echoes it as `deadline_utc`); a bare integer is a count of items |
| `holder` | the one agent or person holding the lease |
| `supervisor_target` | the exact address that a notification or wakeup must reach |
| `capabilities` | declared by the host adapter, not chosen by the principal: the host's self-wakeup. OMP: `{"heartbeat_transport": "omp:background-job"}`. Omit it only on a host with no self-wakeup; the shift is then `DEGRADED` |
| `mantras` | the principal's working mantras; optional |
| `successor_policy` | optional; the successor the principal pre-authorizes to take over a dead holder |

Missing field → refuse to open the shift and name it. Absent `mantras` → use the defaults
**"change the decision when the evidence changes"** and **"a verifiable increment beats an
announced plan"**. An explicit list is stored verbatim and never merged with the defaults.
Every field present → one `open_shift` call, then the work loop starts in the same turn.

## Work loop (mandatory)

Opening the shift is not the work. On night 2026-11-25 a v0.2.0 shift opened, reported
`DEGRADED`, deferred everything to "your next turn" and delivered 0 items in 11 hours, while
its lease lapsed after one. The holder runs this loop; `may_yield` is its only exit.

1. **Same turn as the intake.** Open once (no re-open ceremony) with the host's capabilities;
   on OMP: `open_shift(..., capabilities={"heartbeat_transport": "omp:background-job"})`.
   Save, take the spend baseline (`record_spend`, or `baseline` at open), then `select_next` →
   `start_item` (given list) or `adopt` (no list) until it says `wait`. Hand each item to its
   executor in this turn (an async subagent or job); the holder coordinates and keeps the state.
2. **Every wake is one iteration**: a heartbeat, a subagent or job completion, or a human
   message. First, at the cutoff (`cutoff_reason`, or preflight answering `close_at_cutoff`),
   `close_at_cutoff` before anything else: it needs no lease, so an overdue wake after a
   suspended host still closes. Otherwise `apply_tick(event_id, spend_total=…)` renews the
   lease, consumes the heartbeat, records spend and freezes admission at the cutoff; then
   collect results (`complete_item`, `deliver`), `select_next`, dispatch, and ask `may_yield`.
   When `select_next` answers `reopen_admission` (the holder's own `POSTFLIGHT` freeze from its
   last turn), call `continuity.reopen_admission(state, path, …)` first, then select again.
   Relief or takeover drops the previous holder's heartbeat: the new holder arms its own, and
   its first spend reading re-baselines on its own ledger, keeping the spend already counted.
3. **Exit gate.** `may_yield(eligible=<select_next offered an item>)`, then do its `next`:

   | `next` | Do |
   |---|---|
   | `dispatch` | start the offered item; ask again |
   | `record_spend` | measure the money ledger (pass `None` when it cannot be read); ask again |
   | `arm_heartbeat` | arm the host self-wakeup to fire by `fire_by` (at most half a lease ahead, never after the deadline: `HEARTBEAT_AFTER_DEADLINE`), record it with `arm_heartbeat`, ask again |
   | `close_at_cutoff` | `close_at_cutoff`, report what is left in flight, end the turn |
   | `postflight` (`NO_HOST_WAKEUP`) | on OMP this means `capabilities` was omitted at open: arm the heartbeat anyway (`arm_heartbeat` with `transport="omp:background-job"`, by `fire_by`) and ask again, never postflight. On a host with no self-wakeup: `postflight`; report DEGRADED, unobserved until the next turn, with the in-flight list |
   | `report_degraded` | `SPEND_UNMEASURABLE`: the meter went down or cannot be read; no new item and no new wake until the principal's `rebaseline_spend` (it keeps the spend counted); report it with the in-flight list, end the turn. `LEASE_EXPIRED`: report DEGRADED, end the turn |
   | none (`yield: true`) | end the turn: `HEARTBEAT_ARMED`, `SHIFT_ENDED` or `FENCED` |

   Never end a turn while admission is open, budget and time remain and an item is eligible.
   Never end a turn with the shift `ACTIVE` and no wakeup armed on a host that has one.
4. **A heartbeat is not busy-work.** One armed at a time, at most every half lease; a wake with
   nothing eligible only ticks, re-measures and re-arms. Its cost counts against the money
   budget. It resumes the holder's own session; it never launches sessions or agents and never
   works around caps.
5. **Cutoff.** At the deadline or the spend threshold no new item starts and the holder closes
   (`close_at_cutoff`: `STOPPED`, `stop.kind=cutoff`, reason, in-flight list), even after its
   lease lapsed. Ending earlier stays the principal's (`stop_shift`). Set `freeze_at` below
   `amount` to leave room for work in flight; past the cutoff, cancel what still runs through
   the host and list it.

### Host adapters

| Host | Wakeup transport | Heartbeat | Declare |
|---|---|---|---|
| OMP (oh-my-pi) | a background job (`bash` with `async: true`, an async `task`, `eval`) still pending when the turn ends: OMP waits it out and its result starts a follow-up turn in the same session (OMP RPC docs, "Yield vs settled") | `bash` running `sleep N`, `async: true`, `timeout` above N, N ≤ `lease_secs/2` (the tool clamps `timeout` to 3600); its job id is `job_ref`, its completion is the tick | `capabilities={"heartbeat_transport": "omp:background-job"}`; with `supervisor_target` and `bound_target` both `omp:<session-id>` (the supervisor reads that chat) the armed heartbeat is `SUPPORTED` |
| any other host | not verified | none | nothing; the shift is `DEGRADED` and `may_yield` answers `NO_HOST_WAKEUP` |

A subagent completion also wakes an OMP holder but has no bounded time, so a heartbeat stays
armed while subagents run. Add a host row only after a live dogfood proves it.

## The shift, step by step

1. **Assume.** Read the incoming handoff, if any (`session-reentry`). Open the shift with the
   inputs above. Persist state (lease, cursor, in-flight, gates, wakeup mode) with an atomic
   write. One holder per shift; a second holder is refused by the lease.
2. **Declare the watch.** Ask the host adapter which capabilities it really exposes (timer,
   wakeup transport, bound target). Record `SUPPORTED` only when a wakeup transport is bound to
   the exact supervisor. Otherwise record `DEGRADED` with the reason and the recovery route.
   The heartbeat is the host's own self-wakeup for the holder's session (Work loop, Host
   adapters): one armed at a time; never a second timer, never one that launches sessions or
   agents, never one that gets around caps.
   **Wakeup limits.** The existing timer only observes: it records a tick. It wakes nobody,
   notifies nobody and resumes nothing. A wakeup exists only when the host proves one to the
   exact supervisor. This skill never claims 24/7 or "always on" coverage; with no wakeup
   armed, the shift is unobserved until the next turn and says so.
3. **Work.** Normalize the given list with `normalize_backlog` (one `operator-backlog`
   connector) and start its items with `start_item` (same checks as `adopt`); run each through `ooda-loop` (one decision per item). For each item
   keep: objective/DoD, owner, recipient, deadline, next step, evidence, and an independent
   reviewer when the change is material. Use 5 Whys and Ishikawa to separate competing causes
   and name a test that tells them apart; use 5W2H when an action needs coordination.
4. **Adopt (only when no backlog was given or all of it is accepted).** Follow
   `references/backlog-adoption.md`: read every authorized connector, record each connector's
   outcome, merge the same intent into one work item, check owners and in-flight state, then
   adopt **one** eligible item or wait with a reason, a deadline, a maximum cost and an
   escalation path. Never invent goals, never adopt another organization's work without a
   mandate, and never spin model turns to look busy. With no backlog, look in the authorized
   trackers; never invent a need or an approval. `adopt` re-checks gate, owner, in-flight,
   budget and capacity before it changes anything; `select_next` is advice only.

   **Decision point (before assuming any work).** Answer, briefly: what is fact; what
   evidence is missing; what rival explanation fits; what else it touches; who has authority
   to accept. Then ask the short lens questions:

   | Lens | Question |
   |---|---|
   | Doubting (Tomé) | What observation or counter-proof would change the verdict? |
   | Critical | Does the conclusion follow from the data? |
   | Suspicious | Right source, version, identity and authorization, or an echo? |
   | Systemic | Which other projects, dependencies and people would feel it? |
   | Adaptive | What changed that justifies changing route? |
   | Determined | Which next reversible step still fits the mandate, and where to stop? |
   | Strategic | Which eligible item removes most of an impediment to the user's delivery? |
   | Vulcan logic | Separate premises, consequence, alternative and unknown; satisfaction and preference stay the recipient's. |

   Add a lens only on a concrete indicator: personal data, cost, data-loss risk, a cross-org
   effect, or availability. A simple task gets no meeting and no scoring. Record a lens only
   when it changed an action or prevented an error (`decide_route` stores it only on a change).
   Change route only on new evidence: the same `source#digest` seen again never changes a
   decision (`REPEATED_EVIDENCE`). An incident preempts backlog work (`raise_incident`) and
   keeps the cursor and in-flight work as they were. Ready and received without the
   recipient's satisfaction is still not UDV.

   **Precedence.** Nothing here overrides revocation of authority, the budget, host limits or
   a stop by the principal: after `stop_shift` every mutator, takeover, arming and relief is
   refused. Works of fiction that inspired the shift idea are analogies, never a source of
   authorization.
5. **Signal.** Keep the four signals apart (see `references/shift-contract.md`): a tick is not a
   notification, a notification is not a wakeup, a wakeup is not a resume. Before any outbound
   signal, check the lease and the exact target. Record the strongest signal the host receipt
   proves, not the one that was intended.
6. **Deliver and confirm (UDV).** A result is done only when the intended recipient received
   it AND is satisfied. Track three independent states per item: technical verified, delivered
   to the recipient, satisfaction `confirmed | refused | unknown`. 100% needs the last two
   positive. A file, a PR, green CI, a merge, an empty queue or a technical ACK is not UDV.
   Recipient absent: record the item as pending, invent no feeling, do not resend the same
   result; the shift may pick another eligible item, but the pending one stays below 100%.
   Acceptance with a reservation is not unequivocal satisfaction. A rejection reopens the
   intent, linked to the original result. An agent recipient accepts only within its own role,
   never on behalf of a person.
7. **Check blast radius before every effect.** Name the data, people, projects, accounts and
   dependencies it touches, whether it is reversible, the worst case, how an error would be
   detected and who owns recovery. Local, reversible and in scope → proceed. Crossing an
   authority limit (or out of scope, or irreversible) parks only that operation.
8. **Hand off or stop.** The holder owns the shift until relieved. Relief needs an identified
   successor whose ACK echoes the cursor, the in-flight items and the open gates. A heartbeat is
   not an ACK and silence is not relief: on timeout the outgoing holder keeps the shift. Only
   the principal may stop or revoke without relief; the stop record lists what was left in
   flight. At the principal's own cutoff (deadline or spend threshold given at intake) the
   holder closes with `close_at_cutoff`, distinct from a stop. If the holder dies (its lease lapses) and the principal armed a successor for the
   current generation, that successor alone takes over once, with no ACK from the dead holder
   and a new generation (fencing token). The arming is consumed: one authorization, one
   succession. A second expiry needs a new arming by the principal in the new generation, else
   DEGRADED. The holder can never be its own successor, a replayed takeover or ACK has no
   effect, and a policy armed in an older generation does not apply. Cursor, events, in-flight
   items, gates and UDV records stay as they were, and the old holder is refused if it
   returns. Without a pre-authorized successor or a real route the shift is `DEGRADED` and
   claims no uninterrupted service. Plan for concurrency, budget exhaustion, a suspended host, an empty queue, safe
   shutdown and a generation change by persisting state before every transition.

**Fencing.** Every mutator takes `generation=` and refuses a missing or stale one
(`GENERATION_REQUIRED`, `STALE_GENERATION`) as well as an invalid lease. A handoff ACK must
echo the generation and match the LIVE cursor, in-flight work and gates; if work moved after
the proposal, the ACK is refused (`PROPOSAL_STALE_REACK`) and nothing in flight is dropped.
An event ACK counts only from that event's recipient. A wakeup counts as `SUPPORTED` only when
its bound target is the exact supervisor. A late receipt (`record_receipt`) is recorded
without sending again; a different result or recipient resets technical verification and
satisfaction to unknown.

**Continuity, watchdog, conflicts** (`references/continuity.md`).

| Layer | Today |
|---|---|
| Tested (synthetic, no network, no model) | yes |
| Watchdog installed | no: no supervisor with proven identity, authorization and revocation |
| Wakeup live | OMP: yes while a heartbeat job is armed (follow-up turn in the holder's session); other hosts: not verified, `DEGRADED` |

- Autosave after every transition (children too: pointer + hash in the parent). A failed
  save rolls back and freezes admission; it is never reported as saved. A failed child save
  freezes the parent until `recover_child` accepts a new checkpoint from that same child.
- The handoff is derived from the snapshot, never hand-written; the previous revision stays.
- Preflight every wake, with one graded action (`close_at_cutoff` at the cutoff); missing
  metrics are `unknown`. Postflight only on the last turn (cutoff, handoff, or a host with no
  wakeup); its `POSTFLIGHT` freeze is lifted by `reopen_admission` on the holder's next turn.
- A separate watchdog greets with a nonce and waits for an ACK with a timeout. Silence alone
  is only suspicion. Fencing removes the lease; it signals no process. Real process stop is
  out of scope; tests stop only their own disposable child, re-verified at that moment.
- Conflicts are recorded (facts, authority per world, alternatives, reversibility, decision,
  review criterion) and settled only by verified evidence, never by majority or the latest
  message; authority conflicts and human authorizations park only that effect.
- The holder never grants a human gate. Every source's blocking gate survives the merge.
- Limits: the engine does not authenticate identities (the host must); the host must run
  `assess_effect` before `deliver`.
- **Own team.** The holder may admit members to its own team only (by scope, risk and
  budget, within a seat limit; ephemeral by default, persistent only with a review date and a
  disarm path). Roles are not instances: one executor for atomic work, a distinct judge for
  material work. Retirement drains in-flight work first, leaves an exit receipt, and is
  idempotent. Members of another owner are never touched. Nothing here stops or promotes a
  real session; reuse `work-drain` for draining a work register.
- **Own tools.** A tool, skill, CLI, MCP, app or technique is admitted through the same roster
  (`kind="tool"`), only for a proven gap in current work, with a recorded decision (reuse,
  configure, extend, create or none), scope, owner, risk, expiry, dependents, a health check
  and a safe disarm. Owning tools or a team is no power over shared resources: a request to
  create or delete one is parked for its owner. A tool with active dependents is not retired;
  retiring touches only the own capability, never another owner's dependents. Installed is
  not proof of benefit; idle is not proof of obsolescence.

## Reporting rules
- "100%" needs named criteria and proof from the recipient side. What cannot be proven stays
  visible with its reason; a provider-side HITL is never claimed as done by the shift.
- Write to people only through a valid channel, within scope, with authority and suitable
  content. Never answer a third party as if you were a person. Keep privacy per account and
  organization.
- Reconcile and remove impediments without blame or churn.

## Reference engine and tests
`bin/shift_engine.py` encodes the contract as pure state transitions (stdlib only, no network,
no model, the caller passes `now`). It decides whether I/O is allowed and records what the host
reports; it never sends anything itself. Hosts may use it directly or treat it as the executable
spec. Run the acceptance scenarios with:

```bash
python3 -m unittest discover -s skills/on-call-shift/tests -v
```

### Acceptance scenarios (tests/test_shift_engine.py)
1. Same intent in several trackers plus its pull request → one work item, one adoption.
2. Item in flight with another owner → not adopted; only an offer to remove the impediment.
3. Human gate pending → wait with reason and deadline; never marked done.
4. Handoff → relief only on the successor's ACK of cursor, in-flight work and gates; one holder.
5. Unavailable or denied connector → not an empty queue.
6. No mantra → defaults; explicit mantra kept verbatim.
7. Duplicate tick → one effect.
8. Wrong target or expired lease → nothing is sent.
9. Event without ACK → not concluded; a heartbeat is not an ACK.
10. Restart → lease, cursor and adopted work restored; replay still has one effect.
11. Human veto → respected, never faked.
12. Reviewer equals author → completion refused.
13. Wakeup → the signal kind is the one the receipt proves; no bound transport → DEGRADED.
14. Technical done alone → not UDV.
15. Recipient absent → pending, not 100%, no resend; other eligible work may continue.
16. Recipient dissatisfied → intent reopened and linked to the original result.
17. Valid acceptance → UDV 100%.
18. Acceptance with a reservation → not unequivocal satisfaction.
19. Agent recipient → accepts only for its own role, never for a person.
20. Blast radius → local reversible proceeds; crossing authority parks only that operation.
21. Holder dies with a pre-authorized successor → one takeover, new generation, old holder refused.
22. Holder dies without a successor → DEGRADED, no takeover.
23. Predecessor cannot ACK its own relief.
24. Successor policy consumed by the takeover; second expiry without re-arming → refused, DEGRADED.
25. Policy armed in an older generation does not apply after relief.
26. Replayed takeover or handoff ACK → refused, no second effect.
27. Holder as its own successor → refused at intake, arming and takeover.
28. Only the principal, in the current generation, can arm a successor.
29. Takeover without the dead holder's ACK keeps cursor, events, work, gates and UDV; stale owner fenced.
30. `adopt` re-checks gate, owner, in-flight, budget and capacity before mutating.
31. Every mutator refuses a missing or stale generation and an invalid lease, with no change.
32. A gate changes only by its own decider.
33. A stale handoff ACK is refused; in-flight work is kept; a fresh ACK relieves.
34. A late receipt is recorded without resending.
35. A changed result after acceptance resets UDV.
36. An event ACK must come from its recipient.
37. A wakeup bound to another target is DEGRADED.
38. An incident preempts backlog; the cursor stays the same.
39. A repeated source does not change a decision.
40. New evidence changes it, and the lens is recorded only then.
41. Received without satisfaction has no UDV.
42. No backlog never invents an item.
43. Stop or revocation beats everything.
44. A granted gate allows adoption; a pending one still blocks; the decider's recorded gate wins.
45. Two sources naming different owners make the item ineligible, in any order.
46. A replayed rejection of the same result reopens the intent only once.
47. Every blocking gate from every connector survives the merge, in any order.
48. A delivery is deduplicated against every result already sent (r1, r2, r1).
49. Preflight greets the watchdog; backup OK only on a timely ACK.
50. Backup absent, silent or late → DEGRADED; a wrong nonce is rejected.
51. Persistence failure rolls back and freezes admission; never "saved".
52. Recovery after the failure and after a torn write (previous revision).
53. Child checkpoint: parent keeps pointer, hash and received flag only.
54. Fencing quarantines the holder and kills no third party; one successor.
55. A reused or changed pid is not stopped; only the disposable child is.
56. Handoff derived from the snapshot and delegated to a successor with ACK.
57. Postflight without a successor ends without relief.
58. Preflight grades its action on observable signals.
59. Diagnosis is readable and carries no private data.
60. One watchdog per scope.
61. The holder never grants a human gate.
62. A linked issue and PR with different keys are one item.
63. The same digest under another source name is an echo.
64. A technical conflict is settled by verified evidence, not majority or recency.
65. An authority conflict parks only that effect; the turn continues.
66. Team admission refused by risk, budget, scope or full seats, without duplicates.
67. Draining finishes in-flight work before retiring.
68. Retirement is idempotent.
69. A member of another owner is never touched.
70. Shutdown rehearsal only on a disposable child; a replay affects no new process.
71. Creating or deleting a shared resource is parked, never done.
72. An own tool retires without touching another owner's dependents; active dependents block.
73. A child persistence failure freezes admission and records cause, identity and generation.
74. A valid new child checkpoint resolves only its pending entry, persists the parent, reopens once.
75. Another child's, an older, a wrong-hash or a repeated checkpoint is rejected with no change.
76. A failed parent save during recovery keeps the frozen state.
77. Recovery widens no privilege and never lifts a human gate or another freeze.
78. Restart keeps cursor and in-flight work through the recovery.
79. A child failure never lifts an earlier parent freeze; the parent waits for pending children.
80. A checkpoint older than the failed save is refused, even with the same generation.
81. A later good child save does not clear the pending failure without `recover_child`.
82. A checkpoint with the same generation and cursor that lacks in-flight work is refused.
83. A valid recovery after restart reopens once and keeps the item.
84. The save counter never goes back; an equal count is not newer.

Work loop (postmortem night-20261125; `test_92`–`test_116`; 112–114 are in `tests/test_continuity.py`):

92. Items of a given list start in flight (`start_item`) with the adopt checks; adoption stays closed.
93. A money cap is a measured delta from a baseline; no fresh measurement → no new work; admission freezes at the threshold; a reading that goes down freezes it.
94. At the deadline no new item starts; the holder closes at cutoff even after its lease lapsed, only at the cutoff; a principal stop stays distinct.
95. A new tick renews the lease; a replay does not; an expired lease is never revived.
96. `may_yield`: dispatch first, then measure, then arm a heartbeat (≤ half a lease, ≤ the deadline), then idle; a host with no wakeup yields DEGRADED.
97. One-call intake: scope as a list, backlog as a reference, budget as the principal's terms.
98. A v0.2.0 state file loads migrated.
99. Incident replay: the same intake works the eligible items all night and closes at the deadline.
100. The holder lifts its own POSTFLIGHT freeze on its next turn; never a cutoff or another freeze.
101. Preflight, handoff and diagnosis name the cutoff and the heartbeat.
102. `load_checked` migrates a v0.2.0 file.
103. Non-numeric or non-finite budget terms and spend readings fail closed with a contract error.
104. Relief and takeover drop the previous holder's heartbeat.
105. Team admission respects frozen admission and an unmeasured money cap.
106. Postflight never masks an earlier freeze, so its reopen cannot lift a safety freeze.
107. An overdue wake past the cutoff is routed to `close_at_cutoff`, with no lease needed.
108. A meter that goes down or cannot be read is `SPEND_UNMEASURABLE`: a degraded exit (`report_degraded`), never a loop; a stale meter with a heartbeat armed and nothing eligible yields.
109. Only the principal re-baselines (`rebaseline_spend`) and the spend already counted is kept; a new holder (relief or takeover) re-baselines on its own ledger and keeps it too.
110. The skill tells an OMP holder to declare `capabilities`; `NO_HOST_WAKEUP` carries `fire_by`, and arming by it lets the holder yield.
111. A heartbeat never fires after the deadline (`HEARTBEAT_AFTER_DEADLINE`); one armed past it counts as not armed.
112. A spend freeze that arrives after `POSTFLIGHT` survives `reopen_admission` and relief; relief lifts only the holder's own `POSTFLIGHT`.
113. `select_next` tells the next turn to lift its own `POSTFLIGHT` freeze (`reopen_admission`), never one with a child pending or past the cutoff.
114. A migrated load is saved at once (`migrated`: the hash chain holds, the legacy bytes stay in `.prev`); the schema id is `state@2`, so a v0.2.0 engine refuses a v0.3.0 file.
115. An overflowing number or a non-string currency fails closed; a tick with an unreadable reading is applied whole (and freezes), never half.
116. The deadline is epoch seconds, UTC (a millisecond epoch is refused; the log echoes `deadline_utc`); the scenario ranges in this file are current.

## Files
- `references/shift-contract.md` — state, lease, cursor, the four signals, handoff, stop.
- `references/backlog-adoption.md` — connectors, normalization, RACI/DARCI, selection, waiting.
- `templates/shift-state.schema.json` + `templates/shift-state.example.json` — persisted state.
- `templates/handoff-ack.schema.json` — the successor ACK.
- `references/continuity.md` + `bin/continuity.py` + `bin/watchdog.py` — autosave, handoff, pre/postflight, diagnosis, watchdog, conflicts.

## §DUED Sunset
Retire when the host runtime provides a native shift holder with lease, cursor and ACKed relief
(E1), when `ooda-loop` absorbs shift ownership (E6), on principal retraction (E4), or after three
false relief or false adoption incidents (E5).

## §Refs
- Practice: the Google SRE Workbook chapter on on-call describes reading the handoff at shift
  start and passing one at shift end, and separating urgent pages from tickets.
- Composed: `skills/ooda-loop` (and its `references/runtime-adapters.md` capability contract),
  `skills/work-drain`, `skills/work-compass`, `skills/spec-backlog-ticket-reconciler`,
  `skills/pulse`, `skills/postflight`, `skills/signoff`, `skills/session-reentry`,
  `skills/anti-conflict`.
- Cross-link slug: `[[on-call-shift]]`.

## Changelog
| Version | Date | Change |
|---|---|---|
| 0.3.0 | 2026-11-26 | Postmortem night-20261125 (v0.2.0 opened a shift and delivered 0 items in 11 h). Mandatory work loop with `may_yield` as the only exit; OMP host adapter (background job = wakeup, async `sleep` ≤ half a lease = heartbeat, `SUPPORTED` when bound to the supervisor's session); `start_item` for a given list; money budget measured as a delta plus deadline with automatic freeze; holder `close_at_cutoff` (`stop.kind=cutoff`); lease renewed on tick and on arming; one-call intake (scope list, typed backlog, budget dict); POSTFLIGHT freeze liftable on the next turn; `load`/`load_checked` migrate v0.2.0 files. Independent-verdict fixes: an unexplained or unreadable spend reading makes the meter `SPEND_UNMEASURABLE` (sticky, a degraded exit) until the principal's `rebaseline_spend`, which keeps the spend counted, and a new holder re-baselines on its own ledger; `capabilities` is an intake field; `HEARTBEAT_AFTER_DEADLINE`; a later safety freeze replaces `POSTFLIGHT` and relief lifts only `POSTFLIGHT`; `select_next` answers `reopen_admission`; `load_checked` saves a migrated file; schema id `state@2` (a v0.2.0 engine refuses it); deadline in epoch seconds, UTC. Scenarios 92–116. |
| 0.2.0 | 2026-11-23 | Continuity: autosave per transition (children too), handoff derived from the snapshot, preflight/postflight, diagnosis, a separate logic-only watchdog (nonce + ACK, timeout, one per scope, logical fencing, disposable-only stop). Conflict resolver. Judge fixes: holder never grants a human gate; every connector gate kept; delivery dedupe over all sent results; linked keys merge; digest echo. 72 numbered scenarios. Own team and own tools: admission, drain, idempotent retirement, shared resources parked. |
| 0.1.1 | 2026-11-23 | Review-thread fixes: adopt re-checks limits; generation required on every mutator; live handoff ACK; event ACK by recipient; late receipt; UDV reset on result change; exact wakeup target. Decision-point lenses, incident preemption, route change only on new evidence, precedence of stop/revocation. Succession hardening: successor policy bound to one generation and consumed by its takeover; replay, self-succession and stale arming refused; `arm_successor` for the principal; wakeup limits stated; schema/example sync test. 46 numbered scenarios. |
| 0.1.0 | 2026-11-23 | Genesis via `agentic-tool-forge`; name by `anima` (`on-call-shift`, runner-up `shift-handoff` rejected as covering only the end of a shift). Reference engine plus 23 acceptance scenarios (13 shift + UDV, blast radius, holder loss), stdlib only. |
