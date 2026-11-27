# REVIEW.md

## What this repo is

MAOS (Multi-Agent OS): a skills pack and Claude plugin for multi-agent coordination, public and community-agnostic.
Main trees: `skills/`, `agents/`, `commands/`, `hooks/`, `plugin-scripts/`, `sentinel/`, `scripts/`, `tests/`, `docs/`.
Languages seen: Markdown (skills, agents, commands), bash, Python, Node (`.mjs`), JSON.

## Review priorities (in order)

1. Correctness: hook scripts must return valid JSON; JSON configs must parse; new skills need valid `SKILL.md` frontmatter.
2. Security and privacy: no secrets, no personal data. Flag hardcoded company names, personal emails, absolute paths, internal hostnames or account identifiers (stated in `.coderabbit.yaml`).
3. Repo invariants from `AGENTS.md` / `CONTRIBUTING.md`:
   - hook scripts are bash with `set -euo pipefail` and are security-critical;
   - skills and agents have no `maos-` prefix in the filename; commands use function-specific filenames;
   - names are lowercase-hyphenated;
   - never `--no-verify`, never force-push protected branches;
   - Conventional Commits with a `Co-Authored-By:` footer for AI involvement;
   - a release is its own PR with exactly one `chore(release): ...` commit that changes only the `version` in `.claude-plugin/plugin.json` and adds one matching `CHANGELOG.md` section.

## Sensitive paths

`.github/workflows/**`, `.githooks/**`, `hooks/**`, `plugin-scripts/governance/**`, `.claude-plugin/plugin.json`, `.gitleaks.toml`, `.gitleaksignore`, `.github/CODEOWNERS`, `install/**`, `packaging/**`.

## What NOT to flag

- Missing Jira-style issue keys: tracking is optional here (per `.coderabbit.yaml`).
- Lock files and `*.jsonl` (excluded in `.coderabbit.yaml`).
- Style, which is not determined from the repo beyond the naming rules above (no formatter config found).

## How to verify (from AGENTS.md and CI)

```bash
bash tests/validate-plugin.sh          # AGENTS.md: 1 pre-existing error about plugin.json hooks field is known
python3 -m json.tool hooks/hooks.json > /dev/null
python3 -m json.tool sentinel/config.json > /dev/null
bash scripts/validate-skill-frontmatter.sh   # npm run validate:skills
python skills/pii-masking/linter_pii.py --root . --fail-on-match --paths "**/*.md"   # CI runs it with more paths and excludes; see .github/workflows/ai-governance-linter.yml
python skills/transcript-corrector/scripts/check-pii-scope.py
```

CI (`.github/workflows/ai-governance-linter.yml`) also checks that the PR title is a Conventional Commit.
