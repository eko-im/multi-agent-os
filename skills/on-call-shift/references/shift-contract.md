# on-call-shift — shift contract

Executable form: `../bin/shift_engine.py`. When this text and the engine disagree, the tests in
`../tests/` decide which one is wrong, and both are fixed in the same change.

## 1. Persisted state

One JSON document per shift (`../templates/shift-state.schema.json`, schema id
`on-call-shift/state@2`; a `state@1` file from v0.2.0 is migrated on load). A v0.2.0 engine's
`load()` refuses `state@2`, but its `load_checked()` checks no schema and resumes it: with a
count cap it runs with the money cap and the deadline silently ignored (fail-open); without one,
`select_next` raises. After a rollback to v0.2.0, never resume a `state@2` file: open a new
shift (copy the `state@1` file before upgrading; `.prev` keeps the legacy bytes only until the
next save). Write it atomically (temporary file, fsync, rename) before and after every
transition, so a crash leaves the last good state.

| Field | Rule |
|---|---|
| `holder` | exactly one; changes only by ACKed relief |
| `lease` | `{holder, expires_at, lease_secs}`; valid only while `now < expires_at`, the status is `ACTIVE` or `HANDOFF_PENDING`, and the lease holder is the shift holder |
| `cursor` | `{seq, last_event_id}`; advances once per new event id |
| `processed_events` | ids already applied; a replayed id has no effect |
| `adopted` / `in_flight` | adopted intent keys and the ones not yet completed |
| `gates` | open human gates per item (`approval` or `veto`, with `deadline`) |
| `pending_events` | events waiting for a recipient ACK |
| `wakeup` | `SUPPORTED` or `DEGRADED`, with `reason` and `recovery`; `always_on_claim` is always `false` |
| `mantras`, `mantras_source` | explicit list verbatim, else the two defaults with `source=default` |
| `generation` | fencing token; +1 on every relief or takeover; an older token is refused |
| `successor_policy`, `continuity`, `consumed_takeovers` | successor armed by the principal for one generation (`armed_generation`, `nonce`), consumed by its takeover; `continuity.mode` is `DEGRADED` without one, `uninterrupted_claim` is always `false` |
| `deliveries` | per item: `technical_verified`, `delivered_to_recipient`, `satisfaction` (`confirmed`, `refused`, `unknown`), `attempts`, `result_ref`, `reservations`, `reopened_as` |
| `reopened`, `parked` | reopened intents linked to the original result; operations parked by blast radius |
| `budget`, `capacity` | `{limit, spent, money, deadline}`: no new item when the count reaches `limit` (null = no count cap), in-flight reaches capacity, the deadline (epoch seconds, UTC) passes, or measured spend (`money.spent`, a delta from `money.baseline`) reaches `money.freeze_at`; a money cap needs a measurement no older than one lease. A reading that contradicts the meter (goes down, NaN, infinite, negative, not a number) sets `money.inconsistent_at`: the meter is `SPEND_UNMEASURABLE` until the principal's `rebaseline_spend`, which keeps `money.spent` (baseline = reading − spent). A read that fails (`None`) sets `money.read_failed_at`: `SPEND_NOT_READ` until the next good reading, never sticky. Either way no new item starts and the holder keeps a tick-only heartbeat chain, so the lease holds and the deadline close runs. A new holder's first reading re-baselines on its own ledger, keeping the spend counted; the outgoing holder takes a final reading before `propose_handoff` |
| `heartbeat` | the holder's own scheduled wakeup `{transport, job_ref, armed_at, fires_at, bound_target}`; armed at most half a lease ahead, consumed by the tick it produces |
| `stop` | `null` while running; `{kind: cutoff \| principal_stop \| principal_revoke, by, reason, at, in_flight_left}` |

## 2. Lease

- Only the lease holder may mutate state, and every mutator also requires the current
  `generation` (fencing token); a missing or older one is refused before any change.
- Renewal requires a valid lease; an expired lease cannot be renewed by its old holder. A new
  holder comes only through relief or a fresh shift opened by the principal. A new tick and
  arming a heartbeat renew the lease (the holder is acting); a replayed tick does not.
- Concurrency: two writers compete on the lease, not on the work. The loser reads state and
  stops.

## 3. Four signals

| Signal | Proven by | Is not |
|---|---|---|
| `tick` | the host timer ran and the event id is new | a notification |
| `notification` | a bound transport delivered to the exact `supervisor_target` | a wakeup |
| `wakeup` | the runtime woke the exact supervisor through a supported mechanism (`wakeup.mode = SUPPORTED`) | a resume |
| `resume` | the holder consumed the event within the deadline with exactly one effect | "the process is running" |

The host adapter reports a receipt; the engine records the strongest signal the receipt proves
and flags `downgraded` when the claim was stronger. A tick records
`notification=NOT_SENT_BY_TIMER` and `execution=NOT_REQUESTED`.

Before any outbound signal, `authorize_send` checks the lease and that the target equals
`supervisor_target`. A wrong target or an expired lease sends nothing.

### DEGRADED
When the runtime does not expose a wakeup transport bound to the exact supervisor, the shift
reports `DEGRADED` with a reason (`NO_BOUND_WAKEUP_TRANSPORT`, `NO_BOUND_TARGET` or
`BOUND_TARGET_MISMATCH`) and a recovery route: arm the host's self-wakeup for the holder
(`arm_heartbeat`; OMP: a background job) and bind it to the exact supervisor, or, with no host
wakeup, report what is in flight and that the shift is unobserved until the next turn. The
shift never claims continuous coverage, never starts sessions or agents from a timer, and
never keeps a model busy to simulate presence: a heartbeat fires at most every half lease.

## 4. Events and ACK

An event the shift opens (a page, a request to a person, a hand-over of a result) is concluded
only when its recipient ACKs it with the same event id. A missing ACK leaves it pending; a
heartbeat is not an ACK.

## 5. Handoff and stop

1. The holder proposes relief to an identified successor. State becomes `HANDOFF_PENDING` and
   records the cursor seq, the in-flight keys and the open gates.
2. The successor ACKs with `kind=handoff_ack`, the generation, and echoes all three; the
   ACK must also match the LIVE state at acceptance, else it is refused
   (`PROPOSAL_STALE_REACK`), the proposal is refreshed and the successor ACKs again
   (`../templates/handoff-ack.schema.json`). Any mismatch refuses relief and names the field.
3. On a correct ACK the lease moves to the successor; there is never a moment with two
   holders. In-flight work and gates stay as they were.
4. On timeout without ACK the outgoing holder keeps the shift (`ACTIVE`). Silence is not relief.
5. Only the principal may stop (`STOPPED`) or revoke (`REVOKED`) without relief. The record
   lists what was left in flight so the next shift can pick it up.
6. At the principal's own cutoff (the deadline or the spend threshold given at intake) the
   holder closes with `close_at_cutoff`: `STOPPED`, `stop.kind=cutoff`, the reason and the
   in-flight list. It may close after its lease lapsed, never before the cutoff, and never as
   a stale or another holder.

Use `postflight`/`signoff` to write the continuation seed that the successor reads; the seed is
the content of the handoff, the ACK is the proof it was received.

## 6. User-delivered value (UDV)

| State | Set by | Never set by |
|---|---|---|
| technical verified | completion with an independent reviewer | the author alone |
| delivered to recipient | a receipt whose `received_by` is the recipient | a transport or a merge |
| satisfaction | the recipient's own feedback | the shift, a heartbeat, silence, or an agent speaking for a person |

`udv_percent` is 100 only when all three are positive (`confirmed`). Pending reasons:
`AWAITING_RECIPIENT`, `QUALIFIED_ACCEPTANCE`, `REJECTED_REOPENED`, `SATISFACTION_UNKNOWN`,
`TECHNICAL_NOT_VERIFIED`. The same result is never sent twice; a reopened intent delivers a new
result.

## 7. Blast radius

Before each effect: data, people, projects, accounts, dependencies, reversible, worst case,
detection, recovery owner, crosses authority, in scope. A missing field refuses the effect.
Local, reversible, in scope → proceed. Otherwise → park that operation with its reason and
recovery owner; the shift keeps running.

## 8. Holder loss

Takeover needs the holder's lease to have lapsed and the claimant to be the successor the
principal armed for the current generation (at intake, or later with `arm_successor`, which
only the principal may call and only with the current generation). The claimant is never the
current holder. Takeover happens once per arming: the policy is consumed (its nonce goes to
`consumed_takeovers`), the generation goes up, the lease moves, and cursor, events, in-flight
items, gates and UDV records are kept. A replay with a used nonce is refused. A policy armed in
an older generation (for example before a voluntary relief) does not apply. A second expiry
without a new arming leaves the shift `DEGRADED`. The old holder, back with the old generation, is
refused. With no pre-authorized successor, `continuity` is `DEGRADED`
(`NO_PREAUTHORIZED_SUCCESSOR`) and nobody takes over; voluntary relief still needs the exact
successor's ACK, never the predecessor's word alone.

## 9. Edge cases to plan for

| Case | Behaviour |
|---|---|
| budget exhausted | no new adoption; finish or hand off in-flight work |
| host suspended | lease may expire; on return, the old holder re-reads state and does not act on an expired lease |
| empty queue | wait for a real event with a deadline, a cost cap and an escalation path |
| generation change (new model or agent version) | treat as a handoff: the new generation ACKs cursor, in-flight work and gates |
| safe shutdown | persist state, then stop or hand off; never leave an unpersisted transition |
