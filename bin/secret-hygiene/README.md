# secret-hygiene — keep secret values out of the model's context

A tool's stdout is the model's context, and the context is stored (session
transcripts, audit logs, memory DBs). One `op read` without a pipe puts a
password on disk in several places. These tools stop that in layers.

| Layer | Tool | What it does |
|---|---|---|
| deliver | `secret-pipe` | 1Password value → stdin / env / 0600 temp file of a child process; child output masked |
| prevent | `secret-guard` | PreToolUse hook: blocks shell commands that would print a secret, put it in argv, or read a secret file |
| detect (live) | `secret-alert` | PostToolUse hook: gitleaks over the tool output; logs `rule + sha8`, tells the agent not to repeat it |
| detect (batch) | `secret-leak-scan` | transcripts/logs scan: gitleaks patterns + exact match of agent-vault values (quota-checked) |
| commit | `pre-commit-gitleaks` + `install-pre-commit` | git pre-commit gate on staged changes, installed without clobbering |

No tool ever prints a value: findings carry path, line, rule and `sha256[:8]`.

## Doctrine

1. Value goes process → process: `op read … | cmd`, `VAR=$(op read …)`, `op run`, `op inject`, `secret-pipe`.
2. Never on a tool's stdout/stderr: no unpiped `op read`, `--reveal`, `gh auth token`, `printenv`, bare `env`, `cat .env`.
   Check presence with `${#VAR}`. Trap: `${VAR:+SET}${VAR:-UNSET}` prints the value.
3. Never in argv: no `curl -H "…$TOKEN"`, `--password=`, `gh secret set --body`.
4. No `set -x` near a secret. 5. No read tool on a secret file. 6. Cut error text from scripts that hold a secret.

## Install (per host)

```sh
for t in secret-guard secret-alert secret-pipe secret-leak-scan; do ln -s "$PWD/$t" ~/.local/bin/$t; done
mkdir -p ~/.config/secret-hygiene && printf 'vaults=eko\n' > ~/.config/secret-hygiene/config
```

- Claude Code (`~/.claude/settings.json`): `PreToolUse` matcher `Bash|Read` → `secret-guard`;
  `PostToolUse` matcher `*` → `secret-alert`.
- kiro-cli 3.x agent: `"hooks": [{"trigger":"preToolUse","matcher":"*","action":{"type":"command","command":"…/secret-guard"}}]`.
  Kiro Crew: `agent.kiro_hooks` in `~/.kiro/crew/config.json`.
- Repos: `./install-pre-commit REPO…`.

`# secret-guard:ok` inside a command is the reviewed escape hatch. Blocks are
logged (rule + command sha8) to `~/.local/state/secret-guard/blocks.log`.

## Limits

- Hooks cannot rewrite a tool result, so a value that a tool did print can only
  be detected, not masked. Prevention is the layer that matters.
- `secret-guard` is a heuristic over the command text; it fails open on
  internal errors so a bug never freezes every shell call.
- The vault exact-match reads every item of the vaults: ~450 reads. The
  1Password account quota is shared by all agents (1000/day measured), so the
  scan refuses to run with less than 450 + 300 reads left. Run it weekly.

## Tests

`tests/test_secret_guard.py` (block/allow cases + mutation per rule) and
`tests/test_secret_pipe.sh` (fake `op` on PATH + mask mutation). Both use only
fake values generated at run time.
