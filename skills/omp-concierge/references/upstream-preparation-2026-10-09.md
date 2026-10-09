# OMP terminal-abort upstream preparation — local only

Status: **NOT PUBLISHED · NOT PR-READY**

## Decision

Do not submit the local five-line `EINTR` ignore handler or forward-port closed PR #5332 as the
current solution.

OMP #5328 and closed PR #5332 targeted Bun 1.3.14, where Darwin `read` could surface `EINTR` after
Bun had destroyed the owning stdin stream. Ignoring the later error was insufficient; #5332 rebuilt
the TTY wrapper at its owner boundary. Bun subsequently fixed the lower layer in oven-sh/bun#41086
by retrying Darwin syscall `EINTR`. Git ancestry verifies that fix in Bun 1.4.1 and 1.4.2. The active
OMP build reports Bun 1.4.2.

The current upstream candidate is therefore an **investigation**, not a code PR: reproduce and
instrument the separate `stdin ended` / `setRawMode errno: 2` / SIGHUP path on the current runtime.

## Preserved evidence

- Historical user symptom: bare OMP returned to the shell after interaction while an OMP web launch
  remained usable.
- Recent raw logs contain `stdin raw mode setup failed`, `setRawMode errno: 2`, `open-elsewhere`,
  `stdin ended`, and SIGHUP. Those logs contain no `EINTR`.
- Same-TTY concurrent-process suspension was a harness-created `SIGTTIN` artifact and must not be
  cited as reproduction.
- Independent foreground PTYs on current OMP did not reproduce the abort.
- The active local five-line handler passed a synthetic emitted-error test but did not prove that a
  destroyed stream remained usable.

## Required reproduction before an upstream issue update

Capture one genuine failure in WarpTerminal with OMP foregrounded:

1. UTC timestamp and exact user action.
2. OMP path, realpath, version, SHA, and embedded Bun version/revision.
3. PID, PPID, TTY, PGID, foreground process group, and process state.
4. Correlated PID log and session JSONL.
5. `stdin` readable/destroyed/isTTY state before and after the event.
6. Raw-mode call, errno/code/syscall/fd, signal, and exit status.
7. A second input attempt proving whether the stream remains usable.
8. A stock current-release control in a separate foreground PTY.

Do not background either contender on a shared controlling TTY.

## Code-change gate

A code proposal is justified only after the captured failure identifies an owner boundary that can
recover without hiding real disconnects. The regression must fail before the change and prove:

- continued input after the recovered event;
- raw-mode and all active listeners migrate correctly;
- cleanup removes replacement listeners;
- real EOF, revoked PTY, EIO/ENXIO, and reopen failures remain fatal;
- no process-global exception swallowing;
- current Bun 1.4.1+ behavior is exercised.

## Draft upstream update — do not post yet

> We are investigating a current macOS/Warp terminal exit that is distinct from the historical Bun
> read-EINTR path. Bun PR oven-sh/bun#41086 is included in Bun 1.4.1+ and retries Darwin syscall
> EINTR; the affected local OMP build embeds Bun 1.4.2. Recent incident logs instead show
> `setRawMode errno: 2` / `stdin ended` followed by SIGHUP, with no EINTR. We do not yet have a valid
> same-terminal reproduction, so no maintainer action or code change is requested. We are preserving
> foreground-TTY/process/log evidence and will update only if the owner boundary is reproduced with
> a regression that distinguishes real disconnects from recoverable events.

## Publication gate

Before any external issue comment or PR:

- operator reviews every changed file;
- real-current-runtime reproduction exists;
- focused and full relevant tests pass;
- branch is rebased on current upstream main;
- operator contributes at least one sentence personally, per upstream contribution requirements;
- operator confirms the exact target and text immediately before publication.

## Startup-watch review — OMP 18.8.7

The installed watcher detected OMP 18.8.7 on 2026-10-09 and requested review before update. The
release delta changes startup capability-probe concealment only (commit `300b83f1ad`); it does not
change stdin error handling, raw-mode disconnect behavior, or the relevant regression test. The
release notes contain no terminal-abort fix. Classification remains `UNRESOLVED`; do not treat
18.8.7 as the permanent correction for this case.
