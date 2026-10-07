---
name: session-handover
version: "0.1.0"
description: |
  Close out a multi-agent work session and hand it over to a fresh, zero-context session.
  Runs only after a fail-closed gate proves every delegated agent delivered a non-empty report
  (pending or unknown ⇒ refuse, never close half the work). Then: recap · review · recon · OODA;
  rescue every prompt, instruction, motivation, DoR, DoD, goal, target, task, step, bug, gap,
  warning, failure and error into ONE typed ledger (a kind that is neither found nor declared
  empty refuses validation — no silent drop); render an N-tree/Mermaid graph with status; sync
  the todo/punch-list; a HITL list in Eisenhower order with the recommended option first; a
  roadmap; a link index; a VERIFIED recovery triple [id, link, command]; a self-contained
  handoff-as-prompt that states its own location; durable copies of ephemeral reports after a
  secret/PII scan with a runtime positive control; and a byte-verified clipboard copy.
  Triggers: "session-handover", "close out and hand over", "feche a sessão e prepare o handoff",
  "vou abrir sessão nova zerada", "handoff for a fresh session", "wrap up the delegates and hand off".
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
metadata:
  version: "0.1.0"
  scope: AAIF cross-vendor
  family: session-lifecycle
  cross_link_slug: session-handover
  soul_name: Lampas
  dogfood_status: pending-first-cycle
---

# Session-Handover (soul-name *Lampas*)

**Purpose.** End a session so the next one can start with no memory and lose nothing. The agent
does the judgment; `bin/handover.py` does everything that must not depend on judgment.

**Name.** Decided by `anima` (agent register). `session-handover` follows the operations term
*shift handover* (the outgoing shift writes a report the incoming shift can act on without asking)
and the `session-*` family. Display soul-name *Lampas* (λαμπάς, the torch passed between runners in
the Greek relay race), never used as an identifier. Rejected runner-up: `swarm-closeout` (names the
ending, not the purpose, which is continuation; "swarm" also implies a flat hive the tool does not
assume). `session-handoff` rejected: an existing third-party skill already uses that slug.

## When to use / not use
- **Use** when delegates have finished (or should have) and the operator will continue in a new
  session; or any time a session must be left recoverable by someone with no context.
- **Not** for: recovering the goal of a session that is still running (goal recovery), closing a
  single PR, or reviewing code. Do not run while delegates are still writing (the gate refuses).

## The ledger (the single source of truth for the close-out)

One JSON file, written by the agent, validated and rendered by the script. Minimal shape:

```json
{
 "session": {"id": "<session id>", "link": "https://…", "resume_cmd": "cd <cwd> && <cli> --resume <id>", "cwd": "<cwd>"},
 "title": "<campaign>", "snapshot": "<ISO-8601>", "brief": "<what the next session must do>",
 "declared_empty": ["failure", "error"],
 "nodes":   [{"id": "I1", "kind": "instruction", "title": "…", "status": "in_progress", "parent": null, "source": "…"}],
 "hitl":    [{"id": "H1", "title": "…", "quadrant": "Q1", "where": "…",
              "options": [{"label": "…", "recommended": true, "tradeoff": "…"}, {"label": "…", "tradeoff": "…"}]}],
 "roadmap": [{"phase": "F0", "item": "…", "depends_on": [], "gate": "…", "owner": "…", "done_when": "…"}],
 "artifacts": [{"path": "…", "desc": "…"}]
}
```
- `kind` ∈ prompt · instruction · motivation · dor · dod · goal · target · task · step · bug · gap · warning · failure · error.
- `status` ∈ done · in_progress · blocked · pending · dropped. `parent` builds the N-tree (no cycles, no dangling parents).
- Every kind is either present or listed in `declared_empty` ("checked, found none").
- Each HITL item: ≥2 options, exactly one recommended and it comes first, every option has a trade-off.
- Keep the ledger outside the repo when it carries session paths; it is input, not a deliverable.

## Phases (each is idempotent; re-running converges)

| # | Phase | Who | Command / output | Fails closed when |
|---|---|---|---|---|
| H0 | **Gate: all delegates delivered** | script | `handover.py gate --manifest delegates.json --timeout 900` | any delegate not `delivered`, empty/missing report, empty or unreadable manifest, timeout |
| H1 | **Recap · review · recon · OODA** | agent + script | `handover.py git-anchor --repo <each touched repo>`, then read the reports and the live state (PRs, worktrees, queues) — live state wins over any report | — (dirty files are named, never discarded) |
| H2 | **Harvest into the ledger** | agent | one node per prompt/instruction/…/error, with status and parent | — |
| H3 | **Validate** | script | `handover.py validate --ledger L` | bad kind/status, cycle, dangling parent, silent drop, HITL contract broken |
| H4 | **Todo / punch-list sync** | script + agent | `handover.py sync-todo --ledger L --todo todo.json` → drift list + punch list; fix the drift on either side, re-run until exit 0 | exit 2 = drift |
| H5 | **Recovery triple** | script | `handover.py recovery --ledger L` (transcript exists, command carries the id, link is https) | any of the three unverified |
| H6 | **Durable reports** | script | `handover.py persist --src <ephemeral dir> --dest <durable dir>` then `--apply` | scanner self-test fails; a secret/PII hit without `--redact` |
| H7 | **Render the pack** | script | `handover.py render --ledger L --out <dir>` (dry-run) then `--apply` → `HANDOFF_PROMPT.md` · `GRAFO.md` · `HITL_PENDENCIAS.md` · `ROADMAP.md` · `INDEX_ARTEFATOS.md` | invalid ledger, unverified recovery, dangling artifact link |
| H8 | **Clipboard** | script | `handover.py clip --file <dir>/HANDOFF_PROMPT.md` (copy, read back, compare bytes) | mismatch (5); no tool (6) ⇒ use a clipboard MCP, read it back, compare |
| H9 | **House-keeping report** | agent | list what was written, what was left, open worktrees/branches/PRs touched; delete nothing | — |

`delegates.json`: `{"delegates": [{"id": "<name>", "state": "delivered|running|failed", "report": "<path>"}]}`.
The agent fills it from the delegation records; a delegate that never wrote a report is not delivered.

## Rules
- **Dry-run by default.** `render` and `persist` write only with `--apply`. Writes outside the
  current repo should be shown to the operator as the dry-run list first when unattended authority is not granted.
- **No silent overwrite.** Identical content is a no-op; changed content keeps a `.bak-<UTC>` copy.
- **Secret/PII screen.** The scanner proves itself on every run with a positive control assembled at
  runtime (no key literal in source) and a negative control; if either fails it refuses. `--redact`
  replaces hits with `[REDACTED:<kind>]` and home paths with `~`.
- **Self-locating handoff.** `HANDOFF_PROMPT.md` prints its own absolute path, links the rest of the
  pack, carries the verified recovery triple, and tells the next session to verify live state first.
- **Good neighbour.** Work in your own worktree/dir; never touch another session's worktree or files;
  never switch the branch of a shared checkout; never delete. Content stays community-neutral: no
  people's names, e-mails, phones, or employer/client specifics in generic artifacts.
- **Anti-theater.** A node is `done` only with evidence; unknown is `pending`, not `done`. The gate
  result, the validation result and the clipboard comparison are quoted in the H9 report, not paraphrased.

## Exit codes (`bin/handover.py`)
`0` ok · `1` usage/internal/self-test failure · `2` drift · `3` refused (gate, validation, recovery, link) ·
`2` also = dirty work tree (`git-anchor`) · `4` secret/PII found · `5` clipboard mismatch · `6` no clipboard tool. `--json` gives a machine envelope.

## Tests
`bash skills/session-handover/tests/run-tests.sh` — 49 checks over FEAT-1…FEAT-14 and FEAT-34, fixtures built at
runtime, stdlib only. Written before the code (red), then made green.

## Feature IDs (stable)
| ID | Feature |
|---|---|
| FEAT-1 | fail-closed delegate gate with timeout |
| FEAT-2 | ledger validation (kinds, status, N-tree integrity) |
| FEAT-3 | harvest coverage — no silent drop |
| FEAT-4 | HITL contract: Eisenhower order, recommended first, trade-offs |
| FEAT-5 | verified recovery triple [id, link, command], rendered in handoff and roadmap |
| FEAT-6 | render pack, dry-run by default |
| FEAT-7 | self-locating handoff-as-prompt |
| FEAT-8 | link index + dangling-link refusal |
| FEAT-9 | N-tree + Mermaid graph with status counts |
| FEAT-10 | idempotent writes with backup on change |
| FEAT-11 | todo / punch-list sync with drift report |
| FEAT-12 | durable persistence with secret/PII scan, runtime controls, redaction |
| FEAT-13 | clipboard copy verified byte-for-byte, MCP fallback signal |
| FEAT-14 | `--json` machine envelope |
| FEAT-34 | git state anchor per repo: branch@HEAD + UTC time, every uncommitted file named, worktrees listed (`git-anchor`, exit 2 when dirty) |

## Changelog
| Version | Date | Change |
|---|---|---|
| 0.1.0 | 2026-10-07 | Bootstrap, built clean-room from the operator's close-out order and one real manual run; named by `anima`. |
