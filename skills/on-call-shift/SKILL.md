---
name: on-call-shift
description: |
  Hold an on-call shift as one accountable holder: assume it with a principal, scope, backlog,
  capacity and budget; keep a persisted lease and cursor; watch with the host's existing timer;
  work one eligible item at a time; and hand off only when an identified successor acknowledges
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
  version: "0.1.0"
  scope: AAIF cross-vendor
  family: orchestration-convergence
  cross_link_slug: on-call-shift
  dogfood_status: unit-scenarios-only  # 13 scenarios pass on the reference engine; no live shift yet
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
| `scope` | accounts, organizations, repos and trackers the shift may touch |
| `backlog` | an explicit work list, or empty (then adoption rules apply) |
| `capacity` | maximum items in flight at once |
| `budget` | maximum adoptions, cost or time for the shift |
| `holder` | the one agent or person holding the lease |
| `supervisor_target` | the exact address that a notification or wakeup must reach |
| `mantras` | the principal's working mantras; optional |
| `successor_policy` | optional; the successor the principal pre-authorizes to take over a dead holder |

Missing field → refuse to open the shift and name it. Absent `mantras` → use the defaults
**"change the decision when the evidence changes"** and **"a verifiable increment beats an
announced plan"**. An explicit list is stored verbatim and never merged with the defaults.

## The shift, step by step

1. **Assume.** Read the incoming handoff, if any (`session-reentry`). Open the shift with the
   inputs above. Persist state (lease, cursor, in-flight, gates, wakeup mode) with an atomic
   write. One holder per shift; a second holder is refused by the lease.
2. **Declare the watch.** Ask the host adapter which capabilities it really exposes (timer,
   wakeup transport, bound target). Record `SUPPORTED` only when a wakeup transport is bound to
   the exact supervisor. Otherwise record `DEGRADED` with the reason and the recovery route.
   Reuse the host's existing timer or heartbeat; never install a second one and never use a
   timer to launch sessions or agents, or to get around caps.
3. **Work.** Run the given backlog through `ooda-loop` (one decision per item). For each item
   keep: objective/DoD, owner, recipient, deadline, next step, evidence, and an independent
   reviewer when the change is material. Use 5 Whys and Ishikawa to separate competing causes
   and name a test that tells them apart; use 5W2H when an action needs coordination.
4. **Adopt (only when no backlog was given or all of it is accepted).** Follow
   `references/backlog-adoption.md`: read every authorized connector, record each connector's
   outcome, merge the same intent into one work item, check owners and in-flight state, then
   adopt **one** eligible item or wait with a reason, a deadline, a maximum cost and an
   escalation path. Never invent goals, never adopt another organization's work without a
   mandate, and never spin model turns to look busy.
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
   flight. If the holder dies (its lease lapses) and the principal pre-authorized a successor
   at intake, that successor alone takes over once, with a new generation (fencing token);
   cursor, in-flight items and gates stay as they were, and the old holder is refused if it
   returns. Without a pre-authorized successor or a real route the shift is `DEGRADED` and
   claims no uninterrupted service. Plan for concurrency, budget exhaustion, a suspended host, an empty queue, safe
   shutdown and a generation change by persisting state before every transition.

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

## Files
- `references/shift-contract.md` — state, lease, cursor, the four signals, handoff, stop.
- `references/backlog-adoption.md` — connectors, normalization, RACI/DARCI, selection, waiting.
- `templates/shift-state.schema.json` + `templates/shift-state.example.json` — persisted state.
- `templates/handoff-ack.schema.json` — the successor ACK.

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
| 0.1.0 | 2026-11-23 | Genesis via `agentic-tool-forge`; name by `anima` (`on-call-shift`, runner-up `shift-handoff` rejected as covering only the end of a shift). Reference engine plus 23 acceptance scenarios (13 shift + UDV, blast radius, holder loss), stdlib only. |
