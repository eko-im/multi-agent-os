# OMP terminal-abort case — 2026-10-09

## Scope and epistemic status

This record preserves one operator workstation incident involving `can1357/oh-my-pi` on macOS,
WarpTerminal, and Bun. It intentionally separates proved behavior from hypotheses. It is a case
record and routing reference, not a claim that every OMP terminal exit shares one cause.

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
6. The latest correlated raw-mode/EOF logs did not contain `EINTR`. The EINTR patch is a validated
   mitigation for one subpath, not proof of the root cause of the full symptom.
7. Full-config tests did not prove an MCP/hook/skill/plugin caused the terminal failure.
8. A same-TTY dual-process experiment produced normal shell job-control suspension (`SIGTTIN`).
   Independent-PTY controls falsified the earlier `autoResume` ownership-collision claim.
9. The full TUI suite result observed during the investigation was 3428 pass, 7 skip, 15 fail.
   Static checks passed. The 15 failures were suspected to be environment-related but were not
   independently proven as such; do not report the suite as fully green.
10. No upstream issue comment, branch push, or PR was published for the 18.8.6 local patch during
    this investigation.

## Active local mitigation snapshot

At the close of the investigation, the user's launcher resolved to a locally built OMP 18.8.6 with
an EINTR filter and Bun 1.4.2. The exact executable identity must be re-measured every time; never
trust this dated snapshot or a directory label. The local source was preserved on branch
`fix/eintr-v18.8.6-local`, commit `0be1fae0c368d0475f3723df67f3f59611fa0dd6`.

Operational classification at that point: **healthy with mitigation for cautious normal use**,
not permanently fixed and not safe to forget.

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

Do not declare this case permanently corrected until all are true:

1. The official source contains equivalent handling for the demonstrated recoverable error and any
   separately reproduced raw-mode/EOF defect.
2. Official regression tests exercise the actual failure boundary and keep real descriptor errors
   fatal.
3. The fix commit is included in a tagged official release.
4. The official unmodified release passes the focused behavioral regression.
5. The official unmodified release passes a clean first-turn/continued-turn scenario in the
   affected terminal class, with logs showing no disconnect path.
6. The operator launcher resolves to that official build; no local patch is required.

Until then, report the best attained state (`CANDIDATE`, `MERGED`, or `RELEASED`) and retain update
warnings.

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
