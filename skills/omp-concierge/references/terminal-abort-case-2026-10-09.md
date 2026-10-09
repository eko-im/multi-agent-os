# OMP terminal-abort case — 2026-10-09

## Scope and epistemic status

This record preserves one operator workstation incident involving `can1357/oh-my-pi` on macOS,
WarpTerminal, and Bun. It intentionally separates proved behavior from hypotheses. It is a case
record and routing reference, not a claim that every OMP terminal exit shares one cause.

**Historical EOF/raw-mode case: OPEN.** The later local SIGSTOP/CONT → SIGTTIN occurrence
has an App Tamer mitigation supported by the A/B checkpoint below. That result does not close
the older terminal-disconnect path or establish a complete upstream fix.

## Operator-applied update — 2026-10-09

The operator reports successful `omp update` from 18.8.6 to official 18.8.7, with download
SHA-256 `cf0227bdefca0c486bd2aed1771de3ab98930266883eb69d341caf5665caee14`.
The updater reports replacing the executable at
`~/.local/share/omp/18.8.6-eintr/bin/bun-1.4.2-6895c85f/omp`.
Those directory labels are now stale: they do not identify the installed version, local
patch state, or embedded Bun. The reviewed official 18.8.7 source lacks the local EINTR filter.
Do not continue asserting that the launcher contains the former patched hash.

Post-update agent checks (not a repetition of the operator's successful pre-upgrade test):
the exact replaced executable returned `smoke-test: ok`; App Tamer's `omp` pause and
foreground/background limit flags remain false, with global App Tamer control still enabled.
No additional update, reinstall, configuration change, or session restart was performed.
The new official binary still needs its own visible-Warp `/model`, real-turn, and normal-quit
validation in a new process. Existing running processes may retain the old image.
The updater left `omp.1791585906313.21780.0.bak`; its SHA matched the former patched build.
It was copied, without executing it, outside the updater sweep namespace to
`~/.omp/agent/backups/omp-before-18.8.7.vbm5GI/omp` (directory and executable mode 0700).
The copied SHA was verified as
`6895c85fafb76ec981f245bf3a01d7e8ed566032c154df8ab3b8097797c82e85`.
This preserves executable rollback, not a complete snapshot of mutable agent databases.
The historical EOF/raw-mode case remains open; the App Tamer mitigation remains in place.

## Real recurrence — `omp --yolo`, observed 2026-10-09 18:03 UTC

The operator reported the same return-to-shell failure. Direct terminal use is now **degraded**;
do not repeat the previous general recommendation that the patched TUI is safe for normal use.
The matched launch in shell history was 17:16:51 UTC, PID 87256, cwd `/private/tmp`, TTY `ttys014`.
Its executable vnode and SHA matched the recorded local 18.8.6 build (`6895c85f...e85`).
At capture it remained alive: kernel `KERN_PROC_PID` reported `p_stat=4` (SSTOP),
`p_xstat=21` (SIGTTIN), with start epoch 1791566211. SDK/compiler-verified ABI, not guessed offsets.
This establishes its current stop signal, not the sender or the original stop timestamp.
SIGTTIN is consistent with background-terminal input; an explicit sender is not excluded.

PID 87256 had PGID 87256; foreground PGID 79806 belonged to a later `omx --yolo` launch
at 17:24:05 UTC under the same parent zsh 75649. Do not disturb that unrelated active session.
The only recorded action for session `01a121aa-ee61-7609-a5a7-94ad03625a16` was `/model`
at 17:17:04 UTC. The operator confirmed return occurred on opening `/model`, before selection,
and did not notice/remember a shell message. Its fresh TTY breadcrumb exists; JSONL was not
materialized, consistent with lazy persistence before an assistant entry, not evidence of deletion.
Log `~/.omp/logs/omp.2026-10-09.87256.log` has 43 records and no EOF, EINTR, raw-mode failure,
SIGHUP, or exit record. Paste-MCP connection, memory429, and compression warnings are co-occurrences,
not demonstrated causes. Keep this real stopped process separate from historical harness SIGTTIN.

Pinned source `0be1fae0` shows `--yolo` aliases `--auto-approve`, but both also bypass early
composer prepaint; startup timing differs from bare OMP. No causal relationship is established.
The explicit Ctrl-Z handler sends SIGSTOP17, not the observed SIGTTIN21. No fix, signal,
foreground transfer, or interactive reproduction was attempted during this capture.
Pinned `selector-controller.ts:716-721,877-896,1144-1145,214-224` opens ModelHub and mounts a
fullscreen overlay. No foreground-transfer or suspend call was found in that inspected opening
path; this does not exclude deeper dependencies or external actors.
Missing evidence: who/when changed foreground ownership and which read or sender caused the stop.
The current SIGTTIN may follow the initial return; it is not proof of its original cause.
Next discriminating test must capture foreground PGID and signals around the user-confirmed
`/model` opening in a dedicated Warp terminal, not merely rerun a generic smoke/PTY test.
Do not resume/signal the stopped process while unrelated OMX owns its TTY. Prefer the operator-
verified web frontend for current work. Never suppress SIGTTIN or steal foreground as a fix.

## App Tamer A/B checkpoint — 2026-10-09 21:39 UTC

**Local suspension: mitigation validated for this trial; App Tamer is the A/B-supported cause.**
This is a separate outcome from the still-unresolved historical EOF/raw-mode path. No binary
patch, update, or reinstall occurred. The same local 18.8.6 executable was used throughout:
SHA-256 `6895c85fafb76ec981f245bf3a01d7e8ed566032c154df8ab3b8097797c82e85`.

The operator authorized a separate Warp window, then explicitly authorized “Testar e manter se
resolver” for disabling only App Tamer’s OMP background limit. App Tamer PID 1008 and helper
PID 2656 were active; its GUI showed OMP limited below 51% and red “Stopped”. Before the change,
`omp.limitInBackground=true`, `omp.cpuLimit=0.5096` (rounded), and global
`autoStopEnabled=true`. The GUI change set only `omp.limitInBackground=false`.
A full structural comparison of `~/Library/Preferences/com.stclairsoft.AppTamer.plist` against
`~/.omp/agent/backups/apptamer-20261009/before.plist` found that single changed leaf:
other OMP fields, all other 34 top-level keys, Bun/Node/Warp rules, and the global setting were
preserved. The backup is retained; this is not authorization to disable other limits.

| Trial | UTC evidence | Result |
| --- | --- | --- |
| Before 1 — PID 15611, dedicated `ttys021` | Full-config launch, fresh session directory; selector opened before STOP17 and shell foreground were first sampled together at 21:26:48.868339; CONT19 at 21:26:48.951055; first TTIN21 at 21:26:49.237948 | Failed continued foreground operation; this run does not resolve stop-versus-foreground-loss ordering |
| Before 2 — PID 79797, same terminal | STOP17 at 21:31:44.657760 while still foreground; shell foreground at 21:31:44.778858; CONT19 at 21:31:44.842308; TTIN21 at 21:31:45.240901 | Failed before `/model`; selector opening is not required for this failure |
| After — PID 12373, same window/TTY and executable | Foreground sample at 21:37:08.640812; `/model` visibly opened at 21:37:58.869, 21:38:23.223, and 21:38:28.094 | Three selector passes in one fresh session; no sampled stop or foreground loss |
| After — real turn and exit | TUI/accessibility evidence showed `OMP_DIAG_OK`; `/quit` submitted at 21:39:47.468; shell printed `OMP_POST_FIX_STATUS=0` | Real model turn and normal exit completed; observer saw root absent at 21:39:48.191 and children gone by 21:39:51 |

The second before-run and the after-run used the same temporary `process.kill` tracing
extension and separate fresh session directories. The trace recorded no JS STOP/CONT call;
its only nonzero calls were self-directed SIGWINCH. It does not trace native, cached-function,
child-process, or external signal senders, and log-write failures can be silent. The desktop
harness audit found no direct generated STOP/CONT or Ctrl-Z in the inspected paths, not proof
that every harness interaction is excluded. The short model turn performed an internal todo
operation despite the no-tools request; do not describe it as a tool-free turn.

Evidence is preserved at `~/.omp/agent/state/diagnostics/omp-apptamer-20261009/`:
`omp-warp-foreground-capture.jsonl`, `omp-warp-foreground-capture-2.jsonl`,
`omp-warp-foreground-capture-3.jsonl`, and `omp-warp-kill-trace.jsonl`. SHA-256 comparison
confirmed all four copies match their `/private/tmp/` originals. The directory also contains
the capture/trace scripts and selected screenshots. These are local evidence, not upstream
artifacts; the App Tamer preference backup remains at the separate path above.

The observer records changed state, nominally polling every 25 ms with one-second PID discovery;
it can miss brief events and startup activity. Three selector passes are not three independent
post-change launches, and no reverse A/B/A was run. The controlled setting change strongly
supports keeping this scoped mitigation, but does not identify the signal sender directly,
guarantee permanence, or retrospectively prove the cause of PID 87256 or every older abort.
Original PID 87256 and unrelated OMX on `ttys014` were preserved. If recurrence occurs,
recapture foreground and suspend state before proposing another OMP patch or reinstall.

## Operator-visible symptom

Bare `omp` could return to the shell after the first interaction while an `omp-web` launch remained
usable. The initial suspicion was an agentic tool such as an MCP, hook, skill, rule, or plugin.

## Proven facts

1. Historical OMP logs contain fatal terminal paths including `stdin ended`, `SIGHUP`, and a
   separate `stdin raw mode setup failed` / `setRawMode errno: 2` event.
2. Stock OMP 18.8.6 unconditionally treats a synthetic stdin `EINTR` as terminal failure.
3. A narrow local patch that ignores only `EINTR` while preserving fatal handling for ENXIO passed
   its focused behavioral suite: stock 4/5, patched 6/6.
4. The locally installed patched 18.8.6 completed two structured turns in an independent foreground
   PTY without disconnect or `Operation aborted`.
5. The successful PTY used `TERM=xterm-256color`; a clean visible-Warp before/after reproduction was
   not obtained. Therefore, the PTY success does not prove the original Warp incident resolved.
6. The latest correlated raw-mode/EOF logs did not contain `EINTR`. The filter passed the
   synthetic-error subpath only; that does not prove stream recovery or the full symptom's cause.
7. Full-config tests did not prove an MCP/hook/skill/plugin caused the terminal failure.
8. A same-TTY dual-process experiment produced normal shell job-control suspension (`SIGTTIN`).
   Independent-PTY controls falsified the earlier `autoResume` ownership-collision claim.
9. The full TUI suite result observed during the investigation was 3428 pass, 7 skip, 15 fail.
   Static checks passed. The 15 failures were suspected to be environment-related but were not
   independently proven as such; do not report the suite as fully green.
10. No upstream issue comment, branch push, or PR was published for the 18.8.6 local patch during
    this investigation.

## Active local mitigation snapshot

At the recorded checkpoint, the user's launcher resolved to a locally built OMP 18.8.6 with
an EINTR filter and embedded Bun 1.4.2. The exact executable identity must be re-measured every time; never
trust this dated snapshot or a directory label. The local source was preserved on branch
`fix/eintr-v18.8.6-local`, commit `0be1fae0c368d0475f3723df67f3f59611fa0dd6`.

At that earlier checkpoint, classification was **usable cautiously in the exercised independent
PTY; affected Warp scenario unvalidated**. The later App Tamer checkpoint above supplies bounded
visible-Warp mitigation evidence; it does not retroactively validate this EINTR patch.

### Installer, runtime, and frontend boundaries

npm, Bun/bunx, and Volta describe package or launcher management, not proof of the runtime inside
a compiled executable. Global `bun --version` is distinct from embedded Bun; upgrading global Bun
does not replace an already compiled OMP runtime. Reinstalling the identical artifact leaves its
code/runtime unchanged, so it is not a fix; replacing the target can also discard a local patch.
The successful `omp-web` observation concerns a different frontend and possibly a different
backend launch path; it is a workaround observation, not proof that the Warp TUI is repaired.

## Update risk proved by inspection

The OMP updater can resolve a foreign symlink and atomically replace its final target after checking
release version, without validating a local patch hash or behavior. Consequences:

- `omp update --force` can overwrite the patch immediately;
- a normal update can overwrite it when a newer stable release appears;
- the containing directory can retain a misleading `eintr`/patched label after replacement;
- a detect-only watchdog can report drift but does not block or restore an update.

Use `omp update --check` for read-only discovery. Before any mutation, preserve an executable
rollback, source commit, current SHA, and post-update regression plan.

## Upstream leads, not conclusions

- `can1357/oh-my-pi#5328`: stdin EINTR report.
- `can1357/oh-my-pi#5332`: related proposed change, closed without merge at the time observed.
- `can1357/oh-my-pi#6098`: MCP/child-process theory; not proof of this incident.

Search current official source, issues, commits, tags, releases, and tests afresh. Issue state and
source may have changed after this record.

## Permanent-fix gate

For the historical EOF/raw-mode path, do not declare a permanent upstream fix until all are true:

1. The official source contains equivalent handling for the demonstrated recoverable error and any
   separately reproduced raw-mode/EOF defect.
2. Official regression tests exercise the actual failure boundary and keep real descriptor errors
   fatal.
3. The fix commit is included in a tagged official release.
4. The official unmodified release passes the focused behavioral regression.
5. The official unmodified release passes a clean first-turn/continued-turn scenario in the
   affected visible Warp terminal, with logs showing no disconnect path.
6. The operator launcher resolves to that official build; no local patch is required.

Until then, keep the case OPEN, report only the best evidenced upstream state (including
`ABSENT` or inconclusive when appropriate), and retain update warnings.

## Baseline review checkpoint — 2026-10-09 14:33 UTC

Status remains **OPEN / UNRESOLVED**. No patch or installation changed in that baseline round.
The explicit user launcher still resolves to the recorded local 18.8.6 build, SHA-256
`6895c85fafb76ec981f245bf3a01d7e8ed566032c154df8ab3b8097797c82e85`.
Version and smoke commands exited 0 (`omp/18.8.6`, `smoke-test: ok`).
Installed and versioned watcher SHA-256 matched:
`9048715ad1c3393b79fe53d9b25321ed23b51589ae916275d7728cc8a986b863`.
Existing watcher tests passed 5/5 with 13 assertions. The exported startup function reused
its fresh cache; a separate read-only collection made seven successful HTTP requests.
No interactive TUI or model execution occurred in this round.

Fresh upstream main was `95d1bef0486d8a6e518fc27972c764c83e7215fe`; observed tag was `v18.8.7`.
Main changed relative to the cache, but both watched terminal source/test hashes were unchanged.
This is a broad review signal, not evidence of a terminal-abort fix.

OODA: observe launcher/watcher evidence; orient around the unexplained raw-mode/EOF path;
retain cautious use rather than add an unproven patch; next capture the affected visible-Warp
failure and compare candidate source/release evidence. Smoke, fixtures, cache, or generic
upstream activity cannot close this incident.

## Cache-validity repair checkpoint — 2026-10-09

The later v1.1.1 worktree repair changes warning accuracy, not terminal-abort handling. The
baseline watcher hash and 5/5 result above describe the pre-fix watcher, not this repaired file.
Two added behavioral regressions failed before the repair: a runtime downgrade reused cached
safe-runtime advice (info instead of error), and a future timestamp skipped refresh (0 instead
of 7 fixture requests). After the repair, the same scoped command passed 7/7 with 18 assertions:
`bun test skills/omp-concierge/tests/omp-upstream-watch.test.ts`.

An actual exported `runStartupWatch` smoke used temporary cache and fake read-only fetch only.
Ten cases passed: default execution runtime, zero age, just under six hours, exactly six hours,
future timestamp, invalid timestamp, runtime mismatch, valid cache offline, runtime mismatch
offline, and future timestamp offline. Cache hits made no requests; successful refreshes made
the existing seven fixture GETs. Offline refresh attempts retained the existing five-request
initial batch and emitted a fail-soft warning without cached safe-runtime advice. No real network,
model, updater, installation, or interactive-TUI action occurred; the temporary cache was removed.
The parent then removed an incidental request-count assertion: final suite 7/7, 17 assertions.
The watcher was installed with a preserved backup and atomic rename at
`~/.omp/agent/extensions/omp-upstream-watch.ts`. Source and installed SHA-256 both equal
`abcf072241624c068bf70cff84202b752e223e20277c9e64b193bad64f3341e2`.
A fresh Bun process imported that installed file and exercised its actual startup export;
it exited 0 and delivered the unresolved-status message to the notification callback.
This is module/callback proof, not a new visible-Warp UI test. The incident stays **OPEN / UNRESOLVED**.

## Startup monitor boundaries

The [versioned watcher](../bin/omp-upstream-watch.ts) is triggered by OMP `session_start`,
not by a persistent scheduler. Cache reuse requires the current execution Bun version and a
finite age in `[0, 6 hours)`; missing, stale, invalid, future-dated, or runtime-mismatched state
triggers refresh. Failed refreshes can retry at a later startup. A cache hit is not a fresh source
review or verification of the executable's identity.
It does not inspect local App Tamer preferences or detect CPU-limiter rules; local mitigation
verification is separate from this upstream monitor.

It observes main/tag, issue, and source/test-hash changes. Initial observation and unrelated
changes may also alert: a review candidate is not a confirmed fix. It does not automatically
validate source semantics, release inclusion, or Warp behavior, and its permanent status remains
`UNRESOLVED`. Notifications are OMP-UI-only (`hasUI`); headless runs have no notification delivery,
UI delivery may fail, and no startup means no check. Network failure leaves startup running and
can report the last cached timestamp through an available UI. For the full interpretation and
manual review procedure, use [the concierge](../SKILL.md#startup-review-and-notification).

## Recurrence capture

For the next real abort, preserve before restarting:

- exact UTC timestamp;
- launcher path, final realpath, version, SHA, and embedded runtime provenance;
- PID, PPID, TTY, PGID, foreground process group, and process state;
- correlated OMP PID log and top-level session JSONL;
- terminal and shell identity;
- whether the process was bare OMP, `bunx`, web wrapper, resumed, or fresh;
- exact last successful UI action and first failure;
- signal/exit status and any `EINTR`, raw-mode errno, EOF, ENXIO, or SIGHUP evidence.

Do not manufacture the reproduction by backgrounding an interactive process on the same controlling
TTY. Each contender must be foregrounded in its own independent PTY or terminal tab.

## Runtime-level EINTR correction

A later source review changed the interpretation of the local five-line EINTR handler.

- OMP issue #5328 documents that Bun 1.3.14 destroyed the owning stdin stream before the error
  reached OMP. Merely swallowing that emitted error can leave input unusable, so the local handler
  is a mitigation experiment, not an upstream-grade recovery design.
- Closed OMP PR #5332 demonstrated owner-boundary stream recreation and listener migration for the
  old runtime. It is historical evidence, not a patch to forward-port blindly.
- Bun PR oven-sh/bun#41086 moved the correct retry into Darwin syscall wrappers. Git ancestry
  verifies that the merge commit is present in Bun 1.4.1 and 1.4.2. The active OMP build embeds Bun
  1.4.2, so the specific Bun-1.3.14 read-EINTR escape is runtime-fixed before reaching OMP.
- This does not resolve or explain the separately observed `stdin ended`, `setRawMode errno: 2`,
  `open-elsewhere`, and SIGHUP path. That incident remains `UNRESOLVED`.

Do not submit the five-line handler or the old 81-line recovery port as the current upstream
solution unless a current Bun runtime first reproduces destroyed stdin after read EINTR. Upstream
work should instead instrument and reproduce the raw-mode/EOF path, while monitoring Bun and OMP
release provenance.
