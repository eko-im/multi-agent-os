# on-call-shift — continuity, watchdog and conflicts

Executable form: `../bin/continuity.py`, `../bin/watchdog.py`, `resolve_conflict` in
`../bin/shift_engine.py`. Tests: `../tests/test_continuity.py` and `../tests/test_shift_engine.py`.

## What exists, and what does not

| Layer | State | Meaning |
|---|---|---|
| Tested | yes | synthetic scenarios, no network, no model, no timer |
| Watchdog installed | no | no native supervisor with proven identity, authorization and revocation; installing one would add a second writer/signaller with no owner |
| Wakeup live | no | without a bound notification transport (`NO_BOUND_NOTIFICATION_TRANSPORT`) nothing can wake an ended session; an existing timer only observes |

## Autosave

- `transition(state, path, fn, ...)` runs one engine transition, then `autosave`. The save is
  atomic (temp file, fsync, rename), keeps the previous revision as `.prev`, writes a `.sha256`
  sidecar and reads the file back. Only a matching read-back counts as saved.
- A failed save rolls the in-memory state back to before the transition and closes admission
  (`PERSISTENCE_FAILED`). It is never reported as saved. `reopen_admission` reopens only after a
  save that reads back correctly.
- `load_checked` loads the newest revision whose hash matches, else `.prev`, else fails.
- Children keep their own checkpoint (`checkpoint_child`); the parent stores only a pointer, the
  hash and whether it was received. A child save failure closes the parent's admission.
- Recovery (`recover_child`): the parent holder (lease + current generation) reads the new child
  checkpoint, checks the hash of the bytes read, the same child (shift and holder), a generation
  not older than the failed one, and the original cause. It removes only that pending entry,
  persists the parent first (a failed parent save leaves the parent frozen and unchanged) and
  reopens admission once, only if it was frozen by a child failure and no child is still
  pending. A repeated confirmation finds nothing pending. Gates, lease, budget and other
  freezes are untouched. A child failure never overwrites an earlier parent freeze
  (`POSTFLIGHT`, `PREFLIGHT_INCONSISTENT`, `PERSISTENCE_FAILED`), and `reopen_admission`
  waits while any child is pending. `pending.failed_at` keeps the generation, cursor and hash
  of the newest save that failed; a checkpoint older than that is refused. A later good save
  never clears `pending` by itself.
- No agent recursion just to save, no secrets copied, no rescans, no overwriting someone's WIP.

## Handoff

`render_handoff` is a pure function of the snapshot: same state, same text. It carries the
snapshot hash, generation, cursor, in-flight items, gates, pending events, UDV per item,
admission, wakeup and continuity modes, and a `STALE` marker when the last transition is older
than the caller's threshold. `write_handoff` writes it to a stable path and keeps `.prev`.

## Preflight and postflight

Preflight at every wake checks identity and generation, lease time left, budget, in-flight
work, the clock (time going backwards), the saved hash against the current state, progress
since the last preflight, the watchdog greeting, and host metrics only if the adapter supplies
them (else `unknown`). It returns one graded action: `observe` → `reduce` → `freeze` →
`save` → `propose_handoff`. It never diagnoses mental states.

Postflight closes admission, reports hash, cursor, in-flight work, gates, events and UDV, and
hands off only on the successor's ACK; without one the turn ends without relief, and says so.

## Watchdog (logic only)

- One per scope (`register`). It keeps its own state and never writes the holder's state except
  through `fence`.
- Greeting at preflight: a nonce bound to the exact holder and generation; ACK correct, wrong
  (`REJECTED`) or late (`LATE`) are distinct. No watchdog, no ACK or a late ACK = backup
  `DEGRADED`.
- Silence alone is `SUSPECT`. `CONFIRMED` needs repeated misses AND independent evidence.
- `fence` is a logical quarantine: it expires the lease and closes admission. It signals no
  process. Succession then goes through the single, consumable takeover.
- Same host = common failure domain: a watchdog on the holder's machine does not survive that
  machine sleeping or failing.
- `terminate_disposable` stops only a disposable child the caller created, re-verified at the
  moment of action (own unreaped child handle, same pid, and start time plus token when the
  host exposes the process table). A reused or changed pid is refused. Never a global or group
  signal, never a session that is not provably the disposable child.

Pros: an isolated holder failure is detected; work stays recoverable. Cons: cost, false
positives from delay, double command, common failure domain. Choice per host: logic tested
here; an installed watchdog needs a supervisor with proven identity and revocation first.

## Conflict resolver

`resolve_conflict` records facts, authority per world, alternatives, reversibility, the
decision and the review criterion. Only verified evidence counts, each digest once; never a
majority, never the latest message. Owners who disagree across worlds, or an alternative that
needs a human authorization, park only that effect (`AUTHORITY_CONFLICT`,
`HUMAN_AUTHORIZATION_NOT_ARBITRATED`); the rest of the shift continues.

## Own team

`admit_member` / `assign_member` / `member_done` / `retire_member`. Roster:
admitted → active → draining → retired (suspect or degraded is not dead). Admission checks
scope, risk (`low`/`medium` only), budget and seats; a duplicate is a no-op. Persistent
members need `review_at` and `disarm`. Retirement drains first, then writes an exit receipt
(cursor, generation); a second retirement changes nothing. A member whose owner is not this
shift raises `NOT_YOUR_MEMBER` and is left unchanged. No credentials or data are lent across
organizations; operator revocation wins. Draining a work register stays with `work-drain`.

Own tools use the same roster with `kind="tool"`, a `decision` (reuse, configure, extend,
create, none), `dependents`, `verification` and `expires_at`. `decision="none"` admits
nothing. `request_shared_change` parks any create or delete of a resource the shift does not
own. Active dependents block retirement; retirement never edits dependents.

## Limits the engine does not close

- **Identity is not authenticated by the engine.** `actor`, `decided_by`, `from` and
  `recipient` are what the host passes. The host adapter must authenticate them; the engine
  only checks that they are consistent with the lease, generation and recorded deciders.
- **Blast radius before `deliver` is the host's duty.** `deliver` records a send the host
  reports; it does not itself require `assess_effect`. A host must call `assess_effect` before
  any effect and only then deliver.
