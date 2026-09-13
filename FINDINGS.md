# FINDINGS — Email / Gmail / Outlook surface

**Lens:** reuse-first, GAP-only-for-what-nothing-covers, no `skills.sh` install-count proxies.
**Worktree:** `~/Projects/multi-agent-os/.worktrees/email-reuse-research/`
**Branch:** `research/email-reuse`
**Date:** 2026-09-13 (verified same-day)
**Operator context:** email-messenger v0.1.0 already lives at `~/.claude/skills/email-messenger/`
as the comm-egregoræ chassis router (frontmatter says so explicitly). The candidates below
are inputs into that chassis, not replacements for it.

---

## 0. Method

- `gh api repos/<owner>/<repo> --jq '{stars: .stargazers_count, pushed_at, license: .license.spdx_id, default_branch, archived, disabled, open_issues_count}'`
- `git clone --depth 1 <url>` + read of `LICENSE` (first line) + read of `SKILL.md` frontmatter.
- AAIF spec read raw from `agentskills/agentskills` repo (`docs/specification.mdx`).
- CLI probes via `which` + `--help` for any binary that ships locally.

"**tested**" in the AAIF matrix = I ran the binary or read the SKILL.md frontmatter end-to-end.
"**spec-compatible**" = frontmatter has `name` + `description` only, no `license` / `metadata` /
`allowed-tools`, but otherwise conforms to the AAIF directory layout (`SKILL.md` at root).
"**unknown**" = I have no frontmatter copy or could not reach the repo.

---

## 1. Candidate evidence blocks

Each block lists: `repo_url`, `latest_commit`, `license_api_spdx` (gh API), `license_raw`
(first line of LICENSE file), `maintenance` (pushed_at + open_issues + stars), `security`,
`capability coverage`, `provenance`. Stars are REAL upstream values — the operator's brief
listed incorrect numbers; I kept what `gh api` returned.

### 1.1 agentqq/agently-mail — claimed upstream 58.5K

- repo_url: `https://github.com/agentqq/agently-mail` — **NOT FOUND** at canonical path.
- `gh api users/agentqq` → `login=agentqq, type=User, public_repos=1`. Only **1 public repo**,
  none matching the `agent.qq.com` URL the brief claimed. Probe shows the URL does not
  resolve to a real GitHub repo.
- `gh api users/agent.qq.com` → null (no GitHub user with that handle).
- **VERDICT: GAP-via-nonexistent-source.** The candidate appears to be hallucinated. No
  evidence to merge, reuse, or even mention beyond "probe found zero repos".
- provenance: `gh api users/agentqq` (2026-09-13) + `gh api users/agent.qq.com` (404).

### 1.2 odyssey4me/agent-skills — claimed upstream 825

- repo_url: `https://github.com/odyssey4me/agent-skills`
- latest_commit: `5f003d9` `2026-09-13T00:47:01Z` `chore(deps): update dependency openclaw/gogcli to v0.39.1 (#33)`
- license_api_spdx: `Apache-2.0` (gh API returns Apache-2.0; LICENSE file states MIT — discrepancy
  → frontmatter claims MIT but gh API disagrees)
- license_raw: `MIT License` (LICENSE file first line)
- maintenance: 13 stars (NOT 825), 3 open issues, pushed today, Apache-2.0/MIT dual. Active.
- security: depends on external `gog` CLI binary (`openclaw/gogcli`); CI-pinned to v0.39.1 in
  frontmatter `metadata.gogcli-version`.
- capability coverage (gmail path only — NO outlook surface):
  - read/search/get/attachment/labels via `gog gmail search|get|raw|attachment|labels`
  - thread modify / batch delete / archive / mark-read / unread / trash
  - send / reply / reply-all / forward / autoreply (with `--to --cc --bcc --subject --body`)
  - NO draft creation (gog does have `drafts create` but odyssey SKILL.md doesn't list it)
  - NO threads-as-unit search (only message search)
  - NO IMAP/SMTP fallback — gog is Gmail-API-only via OAuth.
- AAIF frontmatter probe: `name: google` (≤64 chars), `description: 280 chars`, `license: MIT`,
  `metadata.author/version/gogcli-version/gogcli-repository` present, `allowed-tools:
  Bash(gog:*)` present. **SPEC-COMPATIBLE**, missing only `compatibility` field.
- provenance: `git clone --depth 1` 2026-09-13, `gh api repos/odyssey4me/agent-skills`.

### 1.3 sanjay3290/ai-skills — claimed upstream 489

- repo_url: `https://github.com/sanjay3290/ai-skills`
- latest_commit: `281d88d` `2026-09-11T02:19:59+0530` `feat(google-chat): ... (#23)`
- license_api_spdx: `Apache-2.0`
- license_raw: `Apache-2.0` (LICENSE file first line, matches API)
- maintenance: 422 stars (NOT 489 — operator brief off), 4 open issues, pushed 2026-09-11.
- security: standalone OAuth via `keyring` library + custom cloud function
  (`google-workspace-extension.geminicli.com/refreshToken`) — this is a **3rd-party hosted
  refresh-token endpoint**, NOT Google. Operator's secret material transits an outside
  service. Documented and intentional but a real risk surface.
- capability coverage (gmail only):
  - search/read/send/draft/labels/markRead/archive/star
  - attachments (create_mime_message + Gmail attachments API)
  - HTML body support
  - NO outlook surface
  - NO IMAP/SMTP fallback
- AAIF frontmatter probe: `name: gmail`, `description: ~470 chars`, `license: Apache-2.0`,
  `metadata.author=sanjay3290, version="1.0"`. **SPEC-COMPATIBLE**, missing only
  `compatibility` and `allowed-tools`.
- Cross-reference: `sickn33/agentic-awesome-skills/skills/gmail-automation/SKILL.md` frontmatter
  explicitly credits `metadata.author: sanjay3290, version: "1.0"` — i.e. sickn33 mirrored the
  sanjay3290 gmail skill verbatim into the awesome-list. **Reuse candidate = sanjay3290**
  (canonical source), not sickn33.
- provenance: `git clone --depth 1` 2026-09-13, `gh api repos/sanjay3290/ai-skills`,
  cross-checked against sickn33 mirror via `find sickn33 -path '*gmail-automation*'`.

### 1.4 sickn33/agentic-awesome-skills — claimed upstream 347

- repo_url: `https://github.com/sickn33/agentic-awesome-skills`
- latest_commit: `64d8916` `2026-09-13T11:33:28+0200` `Merge pull request #1437 from sickn33/automation/canonical-repo-state`
- license_api_spdx: `MIT`
- license_raw: `MIT License`
- maintenance: **46,355 stars** (NOT 347 — operator brief massively off; this is one of the
  biggest awesome-lists on GitHub), 0 open issues, pushed today. Very active.
- security: bundle of mirrored skills from many authors; security posture depends on the
  original (e.g. sanjay3290's 3rd-party refresh-token endpoint issue carries over).
- capability coverage (gmail via mirror of sanjay3290):
  - `skills/gmail-automation/` = verbatim copy of sanjay3290/ai-skills/skills/gmail
  - `skills/outlook-automation/` = Rube MCP (Composio) wrapper — depends on
    `https://rube.app/mcp` as MCP server; requires Composio OAuth connection.
  - `skills/email-security/`, `skills/cold-email/`, `skills/mailchimp-automation/`,
    `skills/agentmail/`, `skills/mailtrap-*` — niche marketing/security surfaces, NOT
    operator-relevant.
- AAIF frontmatter probe (gmail-automation): `name: gmail-automation`, `description: 96 chars`,
  `license: Apache-2.0`, `metadata.author: sanjay3290`, `metadata.version: "1.0"`,
  `risk: critical`, `source: community`. **SPEC-COMPATIBLE** (has name+desc+license+metadata).
- **NOT a primary reuse source** — it is a mirror. Reuse sanjay3290 directly.
- provenance: `git clone --depth 1` 2026-09-13, `gh api repos/sickn33/agentic-awesome-skills`.

### 1.5 glebis/claude-skills — claimed upstream 246

- repo_url: `https://github.com/glebis/claude-skills`
- latest_commit: `d0bc206` `2026-09-02T12:58:37+0200` `docs(cull-release): correct v0.6.x lessons - TDZ was the real smoke killer`
- license_api_spdx: `MIT`
- license_raw: `MIT License`
- maintenance: 376 stars (NOT 246 — operator brief off), 0 open issues, pushed 2026-09-02.
- security: standard Gmail OAuth via Google Cloud project (user manages credentials in
  `~/.gmail_credentials/`) — clean, no 3rd-party token transit.
- capability coverage (gmail only):
  - `gmail/SKILL.md` + `gmail/scripts/gmail_search.py` — search/fetch/download emails + attachments
  - search-only / read-only (no send, no draft, no labels, no modify)
- AAIF frontmatter probe: `name: gmail`, `description: ~210 chars`, NO `license`, NO
  `metadata`, NO `allowed-tools`. **SPEC-COMPATIBLE** (has required `name` + `description`,
  optional fields absent but allowed).
- provenance: `git clone --depth 1` 2026-09-13, `gh api repos/glebis/claude-skills`.

### 1.6 blink-new/claude — claimed upstream 181

- repo_url: `https://github.com/blink-new/claude`
- latest_commit: `60e8686` `2026-06-30T13:51:03-0700` `kanban-dnd: fix drag-handle hover-reveal pattern`
- license_api_spdx: `null` (gh API returns no license field)
- license_raw: **NO LICENSE FILE** at repo root (`ls LICENSE*` → not found)
- maintenance: 1 star (NOT 181 — operator brief wildly off), 0 open issues, pushed 2026-06-30
  (2.5 months stale).
- security: Gmail OAuth via Google Cloud project — multi-account capable (`accounts.mjs
  --list/--link/--unlink`). Tokens stored at `~/.cursor/skills/gmail/accounts/<name>/token.json`
  — plaintext on disk (NOT encrypted keyring). Real risk.
- capability coverage (gmail only):
  - `skills/gmail/SKILL.md` — read/search/reply/send, multi-account, HTML/attachments/CC/BCC
  - `skills/resend-inbound-emails/SKILL.md` — Resend API wrapper (transac. provider)
- AAIF frontmatter probe (gmail): `name: gmail`, `description: ~370 chars`, NO `license`,
  NO `metadata`. **SPEC-COMPATIBLE** (required fields present).
- provenance: `git clone --depth 1` 2026-09-13, `gh api repos/blink-new/claude`.

### 1.7 aws-samples/sample-strands-agent-with-agentcore — claimed upstream 56

- repo_url: `https://github.com/aws-samples/sample-strands-agent-with-agentcore`
- latest_commit: `a38e1bc` `2026-09-12T23:21:26-0600` `Merge pull request #294 from aws-samples/codex/ux-reliability-and-response-style`
- license_api_spdx: `MIT`
- license_raw: `MIT License` (Copyright 2025 Agent Chatbot Template)
- maintenance: 191 stars (NOT 56 — operator brief off), pushed 2026-09-12. Active.
- security: **FastMCP server on AgentCore Runtime** using `AgentCore Identity 3LO` OAuth with
  per-user token vault + `call_with_oauth_retry()` (forces fresh 3LO on 401/403). Production-grade.
  Has `email_approval.py` hook → confirms destructive email actions require explicit approval.
- capability coverage (gmail only — NOT outlook):
  - 11-tool MCP server: `list_labels`, `list_emails`, `search_emails`, `read_email`,
    `send_email`, `draft_email`, `delete_email`, `bulk_delete_emails`, `modify_email`,
    `get_email_thread`, plus `approval_required` hook
  - Full thread support (`get_email_thread`)
  - Bulk delete with explicit reason string for approval gate
- AAIF frontmatter probe (skills/gmail/SKILL.md): `name: gmail`, `description: ~50 chars`,
  NO `license`, NO `metadata`. **SPEC-COMPATIBLE** (required fields present). Note: minimal
  frontmatter, no `compatibility` field — AgentCore-only.
- **Most thorough Gmail implementation** in the candidate list. STRONG reuse candidate.
- provenance: `git clone --depth 1` 2026-09-13, `gh api repos/aws-samples/sample-strands-agent-with-agentcore`.

### 1.8 membranedev/application-skills@zoho-mail — claimed upstream (count unknown)

- repo_url: `https://github.com/membranedev/application-skills` — **NOT FOUND**
  (`gh api repos/membranedev/application-skills` → 404).
- `gh api users/membranedev` → `public_repos: 1`. Only 1 public repo, none matching.
- **VERDICT: GAP-via-nonexistent-source.** Same pattern as agentqq — claimed URL does not
  resolve. Note: `membrane/application-skills` (different org, 52 public repos) does exist
  but was NOT what the operator brief asked for.
- provenance: `gh api repos/membranedev/application-skills` (404),
  `gh api users/membranedev` (1 repo, not matching).

### 1.9 membranedev/application-skills@mailgun — claimed upstream (count unknown)

- Same as 1.8 — repo not found, single-repo user, **GAP-via-nonexistent-source**.
- Provenance: same gh probes.

### 1.10 tiangong-ai-staging/agent-skills@email-imap-* — claimed upstream (count unknown)

- repo_url: `https://github.com/tiangong-ai-staging/agent-skills`
  (note: not `tiangong-ai/skills` as brief listed; user `tiangong-ai` has 0 public repos,
  staging org holds the real repo)
- latest_commit: `501aacf` `2026-09-12T18:05:45+0800` `Merge pull request #129 from tiangong-ai/feature/issue-128`
- license_api_spdx: `MIT`
- license_raw: `MIT License` (Copyright 2025 linancn)
- maintenance: 9 stars, 0 open issues, pushed 2026-09-12.
- security: standalone Python with `imapclient` dep; env-driven config; no 3rd-party token
  transit (you talk to your own IMAP host). Clean. Optional OpenClaw webhook forwarding
  (openclaw is the recipient daemon, not a token relay).
- capability coverage (vendor-neutral IMAP/SMTP — covers GMAIL/OUTLOOK/163/QQ/126/YEAH/etc.
  via plain IMAP):
  - `email-imap-fetch`: IDLE-based real-time inbox monitoring, multi-account via env, snippet
    preview, no full-body transit
  - `email-imap-full-fetch`: stage-2 retrieval of full MIME body + attachments when called
  - `email-smtp-send`: SMTP outbound with attachments + optional Sent-folder APPEND sync
  - `email-imap-append`: draft creation via IMAP APPEND (RFC 5322 MIME)
- AAIF frontmatter probe: each skill has `name` + `description` only. NO `license` (despite
  repo being MIT), NO `metadata.author`, NO `metadata.version`. **SPEC-COMPATIBLE** but
  minimal.
- The most **vendor-neutral IMAP coverage** in the candidate list. Real reuse candidate
  for any non-Gmail/Outlook provider (163.com, QQ, etc.).
- provenance: `git clone --depth 1` 2026-09-13, `gh api repos/tiangong-ai-staging/agent-skills`.

### 1.11 boomsystel-code/openclaw-workspace@imap-smtp-email — claimed upstream 1.9K

- repo_url: `https://github.com/boomsystel-code/openclaw-workspace`
- latest_commit: `3a2689d` `2026-02-08T10:03:23+0800` `Update bazi learning progress (2026-02-08)`
- license_api_spdx: `null` (gh API returns no license field)
- license_raw: **NO LICENSE FILE** at repo root (`ls LICENSE*` → not found)
- maintenance: 0 stars (NOT 1.9K — operator brief wildly off), pushed **2026-02-08 (7 months
  stale)**. Effectively dead as an email source.
- security: mixed — `imap-smtp-email` is clean Python+`.env`; `email-daily-summary` requires
  `browser-use` and reuses user browser sessions (privacy concern); `sendclaw-email` is a
  third-party agent-email SaaS (`sendclaw.com`) — completely different trust model.
- capability coverage (mixed bag):
  - `skills/imap-smtp-email`: vendor-neutral IMAP/SMTP (Gmail/Outlook/163/vip.163/126/vip.126/
    188/vip.188/YEAH/QQ). Strongest provider coverage in any single candidate.
  - `skills/outlook-email`: Microsoft Graph CLI (independent GitHub: `abhiramee08b021/outlook-cli`)
  - `skills/email-daily-summary`: browser-use driven (heuristic, requires Chrome session)
  - `skills/sendclaw-email`: SendClaw SaaS API (third-party agent email)
  - `skills/agent-mail`, `skills/mailgun`, `skills/react-email-skills`: other surfaces
- AAIF frontmatter probe (imap-smtp-email): `name: imap-smtp-email`, `description: ~210 chars`,
  NO `license`, NO `metadata`. **SPEC-COMPATIBLE**.
- AAIF frontmatter probe (outlook): `name: outlook`, `description: ~120 chars`, has
  `metadata.openclaw` install hint + `homepage`. **SPEC-COMPATIBLE**.
- **NO LICENSE file = any reuse must come with provenance-preserving notice and operator
  ratification.** 7-month stale push means this repo is a snapshot, not a maintained source.
- provenance: `git clone --depth 1` 2026-09-13, `gh api repos/boomsystel-code/openclaw-workspace`.

### 1.12 Locally installed — `spark` CLI (v1.3.1)

- binary: `/usr/local/bin/spark`
- version: `1.3.1`
- operator-context: Gmail personal (`emilson.moraes@gmail.com`, "Admin", send access) +
  M365 Vek work (`emilson.moraes@vectorinf.com.br`, "Vek", send access, with alias
  `emilson.moraes@vek.com.br`)
- capability coverage (gmail + outlook via M365, both LIVE):
  - `spark accounts/folders/emails/search/thread/attachment/draft/templates/comment`
  - `spark events/event` for calendar
  - `spark meetings/meeting` for meeting transcripts
  - `spark availability/contacts`
- AAIF: NO SKILL.md in upstream repo (Spark ships CLI only); **local SSOT** is
  `~/.claude/skills/use-spark/SKILL.md` (operator-authored, v1.3.1).
- provenance: `which spark` + `spark --version` + `spark accounts` (2026-09-13).

### 1.13 Locally installed — `himalaya` CLI (v2.0.0)

- binary: `/opt/homebrew/bin/himalaya`
- version: `himalaya v2.0.0 +gmail +jmap +msgraph +smtp +rustls-ring +imap +m2dir`
- upstream: `pimalaya/himalaya` (7,233 stars, Apache-2.0, pushed 2026-09-08)
- capability coverage (the most versatile CLI tested):
  - IMAP backend (any provider) + JMAP + Gmail API + Microsoft Graph + Maildir
  - `himalaya message compose/send/reply/forward/copy/move/read`
  - `himalaya envelope list/search` (shared search query DSL)
  - `himalaya msgraph mail-folder/message/attachment` (full Outlook via MS Graph)
  - `himalaya smtp send/raw` (low-level SMTP)
  - Built-in flag composer + external `mml` integration for rich composition
- AAIF: openclaw umbrella exposes this as `skills/himalaya/SKILL.md` — has `name`,
  `description`, `metadata.openclaw` install hint, `homepage`. **SPEC-COMPATIBLE** +
  openclaw-installable.
- provenance: `which himalaya` + `himalaya --version` + `himalaya --help` +
  `himalaya msgraph --help` + `himalaya smtp --help` (2026-09-13).

### 1.14 Locally installed — `gog` CLI (v0.23.0)

- binary: `/Users/emilson.moraes/.local/bin/gog`
- version: `v0.23.0 (71a8504 2026-06-08T23:32:28Z)`
- upstream: `openclaw/gogcli` (8,406 stars, MIT, pushed 2026-09-12)
- capability coverage (Google-only — 17 surfaces):
  - Gmail/Calendar/Chat/Classroom/Drive/DriveLabels/Contacts/Tasks/People/Sheets/Forms/Sites/
    AppScript/Analytics/SearchConsole/YouTube/Photos/Maps/Groups/Admin/Keep/Meet/Docs/Slides
  - `gog gmail search/messages-search/send/drafts create/drafts send/reply` (with HTML +
    `--body-file` + `--reply-to-message-id` for threading)
  - `--gmail-no-send` agent safety flag (blocks send operations)
- AAIF: openclaw umbrella exposes this as `skills/gog/SKILL.md` — has `name`, `description`,
  `metadata.openclaw` install hint, `homepage`. **SPEC-COMPATIBLE** + openclaw-installable.
- provenance: `which gog` + `gog --version` + `gog --help` + `gog gmail --help` +
  `gog gmail send --help` (2026-09-13).

### 1.15 Locally installed — `cc-gmail` (v0.1.0)

- binary: `/Users/emilson.moraes/.local/bin/cc-gmail`
- version: `0.1.0`
- capability coverage (gmail only): Gmail OAuth account management — `accounts list/add/remove`,
  send mail, read inbox. Operator's Vek account currently shows `Status: Setup needed` —
  needs OAuth flow before live use.
- AAIF: not in current candidate list (this is a local binary, not a public skill repo).
  Used by `email-messenger` v0.1.0 surface discovery (`cc-gmail accounts list`).
- provenance: `which cc-gmail` + `cc-gmail --version` + `cc-gmail accounts list` (2026-09-13).

---

## 2. Comparison table — 5 axes

Axes: M = maintenance (push recency × stars × issues), L = license clarity, S = security posture
(0=3rd-party-token-transit / 1=plaintext-on-disk / 2=user-managed-OAuth / 3=hostile-MCP-only /
4=multi-account-vault-OAuth), C = capability coverage (read/search/draft/send/threads/
imap-smtp/oauth-google/oauth-microsoft), AA = AAIF frontmatter compliance (tested /
spec-compatible / unknown).

| Candidate | M (stars, push) | L | S | C (g/o/i) | AA |
|-----------|-----------------|---|---|-----------|----|
| agentqq/agently-mail | 0 stars, no repo | n/a | n/a | n/a | unknown |
| odyssey4me/agent-skills | 13, today | MIT (raw) ≠ Apache-2.0 (API) | 2 (OAuth via gog) | g only | spec-compatible |
| sanjay3290/ai-skills | 422, 2d ago | Apache-2.0 both | 1 (3rd-party token refresh endpoint) | g only | spec-compatible |
| sickn33/agentic-awesome-skills | 46,355, today | MIT both | mirrors upstream (inherits risk) | g + outlook-via-rube-mcp | spec-compatible |
| glebis/claude-skills | 376, 11d ago | MIT both | 2 (user OAuth credentials) | g search/read only | spec-compatible |
| blink-new/claude | 1, 2.5mo ago | NONE | 1 (plaintext tokens) | g multi-account | spec-compatible |
| aws-samples/sample-strands-agent-with-agentcore | 191, today | MIT both | 4 (AgentCore 3LO vault + approval hook) | g + threads + bulk-delete with approval | spec-compatible |
| membranedev/application-skills | 0 stars, no repo | n/a | n/a | n/a | unknown |
| tiangong-ai-staging/agent-skills | 9, today | MIT both | 2 (env-driven IMAP, no token transit) | i (any IMAP host) | spec-compatible |
| boomsystel-code/openclaw-workspace | 0, 7mo stale | NONE | mixed (1-2-3 across skills) | i + o (Graph CLI) + browser-based | spec-compatible |
| spark CLI (local) | n/a (vendor) | n/a | daemon (Spark Desktop) | g + o (M365) | local SSOT (use-spark) |
| himalaya CLI (local) | 7,233 upstream, today | Apache-2.0 | 2 (per-account TOML config) | i + g + o + jmap + maildir | spec-compatible (openclaw SKILL.md) |
| gog CLI (local) | 8,406 upstream, today | MIT | 2 (OAuth with --gmail-no-send safety) | g + 16 other Google | spec-compatible (openclaw SKILL.md) |
| cc-gmail (local) | n/a (vendor) | n/a | 2 (OAuth, setup-needed) | g only | local binary |

Legend: g = gmail/oauth-google, o = outlook/oauth-microsoft, i = IMAP/SMTP-vendor-neutral.

---

## 3. Verdict — REUSE per provider, GAP only for what nothing covers

### 3.1 Gmail / Google Workspace surface

- **REUSE (primary):** openclaw umbrella `gog` skill (already locally installed) +
  `openclaw/gogcli` upstream. Best Google coverage (17 surfaces incl. Calendar/Chat/
  Classroom/Drive/Docs/Sheets/Forms), `--gmail-no-send` agent-safety flag, thread-aware
  replies via `--reply-to-message-id`, AAIF-spec-compliant `skills/gog/SKILL.md`.
- **REUSE (secondary):** aws-samples/sample-strands-agent-with-agentcore for any
  AgentCore/Strands-hosted environment — has explicit approval hook for destructive
  operations, MCP server with 11 named tools, threaded read.
- **REUSE (canonical mirror):** sanjay3290/ai-skills/skills/gmail for environments without
  `gog` available; frontmatter explicitly says `metadata.author: sanjay3290, version: "1.0"`
  and sickn33/agentic-awesome-skills/skills/gmail-automation credits the same source.
  Note the 3rd-party token-refresh endpoint risk; document it in any local wrapper.
- **NO REUSE:** agentqq/agently-mail, glebis (search-only, too narrow), blink-new (no
  LICENSE, plaintext tokens, 2.5mo stale).

### 3.2 Microsoft Outlook / M365 surface

- **REUSE (primary):** `himalaya msgraph` subcommand (already locally installed, v2.0.0
  with `+msgraph` feature flag). Full Microsoft Graph coverage (mail folders, messages,
  attachments, profile). Apache-2.0 upstream, active maintenance, vendor-neutral IMAP/SMTP
  fallback if Graph OAuth unavailable. AAIF via openclaw umbrella `skills/himalaya/SKILL.md`.
- **REUSE (alternative):** `spark` CLI for the operator's personal M365 (`emilson.moraes@
  vectorinf.com.br`) — already live with send access, plus alias `emilson.moraes@vek.com.br`.
  Native Spark Desktop dependency is a constraint (the `use-spark` SKILL.md documents it:
  "do not try to execute it inside a sandbox, container, CI runner").
- **REUSE (out of scope for agent, but documented):** boomsystel-code/openclaw-workspace@
  skills/outlook-email — references independent `abhiramee08b021/outlook-cli`. NO LICENSE
  file at workspace root, 7-month stale — only reference, do not pull.
- **NO REUSE:** sickn33/agentic-awesome-skills/skills/outlook-automation — depends on
  Rube MCP (Composio) which is a third-party OAuth broker; introduces an unnecessary
  dependency when `himalaya msgraph` does the same thing natively.

### 3.3 IMAP/SMTP vendor-neutral (163/QQ/126/YEAH/etc.)

- **REUSE (primary):** boomsystel-code/openclaw-workspace/skills/imap-smtp-email —
  widest documented provider matrix (163/vip.163/126/vip.126/188/vip.188/YEAH/Gmail/
  Outlook/QQ). **BUT** the workspace has no LICENSE and is 7-month stale. Reuse only with
  provenance notice + operator ratification.
- **REUSE (alternative):** `himalaya` CLI — vendor-neutral via IMAP backend, Apache-2.0,
  active, locally installed. AAIF-compliant openclaw SKILL.md available.
- **REUSE (alternative for stage-2 workflows):** tiangong-ai-staging/agent-skills — has 4
  purpose-built skills (email-imap-fetch, email-imap-full-fetch, email-smtp-send,
  email-imap-append). MIT licensed, real-time IDLE support, OpenClaw webhook integration.
  AAIF frontmatter minimal (`name`+`description` only) — `spec-compatible`, not `tested`.

### 3.4 GAP — what no candidate covers

- **GAP:** Real OAuth for Microsoft personal `@outlook.com` / `@hotmail.com` accounts via
  Graph API. `himalaya msgraph` works for M365/Enterprise but the boomsystel/outlook-email
  docs note "Only works with Microsoft 365/Enterprise accounts (not @hotmail.com/@outlook.com)".
  Operator's M365 work account (`vectorinf.com.br`) IS covered by himalaya + spark; the
  personal `@hotmail.com` case is unaddressed.
- **GAP:** Outbox/Sent-mail threading preservation across surfaces (single thread visible
  in both Gmail + M365 clients). None of the candidates solve cross-client threading
  when an email is sent via SMTP but the recipient's thread lives on a different provider.
- **GAP:** Provider-agnostic OAuth token vault for multiple Google + Microsoft accounts in
  one binary. `gog` is Google-only, `himalaya msgraph` is Microsoft-only, `spark` daemon is
  operator-locked. The locally-installed `cc-gmail` v0.1.0 only handles Gmail and currently
  shows "Setup needed" for the Vek account.
- **GAP (gap-by-nonexistent-source):** agentqq/agently-mail (claimed 58.5K upstream) does
  not resolve to a real GitHub repo; membranedev/application-skills (claimed for zoho-mail
  and mailgun) does not resolve either. These are not GAPs to fill — they are **never were**
  real upstream candidates. Cross-check provenance was already done (this file's §1.1, §1.8, §1.9).

---

## 4. AAIF compatibility matrix

Per spec (raw `agentskills/agentskills` `docs/specification.mdx`): `name` ≤64 chars (lowercase
letters/digits/hyphens), `description` ≤1024 chars required; `license`, `compatibility`,
`metadata`, `allowed-tools` optional. `name` must match parent directory name.

`tested` = I read the SKILL.md frontmatter end-to-end this session.
`spec-compatible` = frontmatter has `name` + `description`, no `license`/`metadata`/`allowed-tools`,
but otherwise conforms to AAIF directory layout (`SKILL.md` at root).
`unknown` = I have no frontmatter copy or could not reach the repo.

| Skill path / CLI | Tested? | Spec-compatible? | AAIF strict-pass? | Probe |
|------------------|---------|-------------------|-------------------|-------|
| odyssey4me/agent-skills/skills/google | tested | yes | yes (has license + metadata + allowed-tools) | git clone + read SKILL.md |
| sanjay3290/ai-skills/skills/gmail | tested | yes | yes (has license + metadata) | git clone + read SKILL.md |
| sickn33/agentic-awesome-skills/skills/gmail-automation | tested | yes | yes (has license + metadata) | git clone + read SKILL.md |
| sickn33/agentic-awesome-skills/skills/outlook-automation | tested | yes | partial — no `license`/`metadata`, depends on Rube MCP | git clone + read SKILL.md |
| glebis/claude-skills/gmail | tested | yes | partial — `name`+`description` only | git clone + read SKILL.md |
| blink-new/claude/skills/gmail | tested | yes | partial — `name`+`description` only | git clone + read SKILL.md |
| blink-new/claude/skills/resend-inbound-emails | tested | yes | partial — `name`+`description` only | git clone + read SKILL.md |
| aws-samples/sample-strands-agent-with-agentcore/chatbot-app/agentcore/skills/gmail | tested | yes | partial — `name`+`description` only | git clone + read SKILL.md |
| tiangong-ai-staging/agent-skills/email-imap-fetch | tested | yes | partial — `name`+`description` only | git clone + read SKILL.md |
| tiangong-ai-staging/agent-skills/email-smtp-send | tested | yes | partial — `name`+`description` only | git clone + read SKILL.md |
| tiangong-ai-staging/agent-skills/email-imap-append | tested | yes | partial — `name`+`description` only | git clone + read SKILL.md |
| tiangong-ai-staging/agent-skills/email-imap-full-fetch | tested | yes | partial — `name`+`description` only | git clone + read SKILL.md |
| boomsystel-code/openclaw-workspace/skills/imap-smtp-email | tested | yes | partial — `name`+`description` only | git clone + read SKILL.md |
| boomsystel-code/openclaw-workspace/skills/outlook-email | tested | yes | yes (has `metadata.openclaw` + `homepage`) | git clone + read SKILL.md |
| boomsystel-code/openclaw-workspace/skills/email-daily-summary | tested | yes | partial — `name`+`description`+`allowed-tools` only | git clone + read SKILL.md |
| openclaw/openclaw/skills/gog | tested | yes | yes (has `metadata.openclaw` + `homepage`) | gh api + base64 decode SKILL.md |
| openclaw/openclaw/skills/himalaya | tested | yes | yes (has `metadata.openclaw` + `homepage`) | gh api + base64 decode SKILL.md |
| agentqq/agently-mail | unknown | unknown | unknown — repo does not resolve | gh api 404 |
| membranedev/application-skills@zoho-mail | unknown | unknown | unknown — repo does not resolve | gh api 404 |
| membranedev/application-skills@mailgun | unknown | unknown | unknown — repo does not resolve | gh api 404 |

---

## 5. Source provenance (every claim)

- `gh api` timestamps all 2026-09-13 (verified same-day).
- `git clone --depth 1` timestamps all 2026-09-13.
- AAIF spec read raw from `agentskills/agentskills` `docs/specification.mdx` at commit
  `69ef37e` (2026-08-09).
- Local CLI probes via `which` + `--help` 2026-09-13.
- This file is at `~/Projects/multi-agent-os/.worktrees/email-reuse-research/FINDINGS.md`,
  branch `research/email-reuse`, commit hash pending.

### Honest corrections to the operator brief

- agentqq/agently-mail claimed 58.5K — repo does not exist on GitHub. `gh api users/agentqq`
  shows 1 public repo total. **Number not real.**
- odyssey4me/agent-skills claimed 825 — actual 13 stars (`gh api --jq .stargazers_count`).
- sanjay3290/ai-skills claimed 489 — actual 422 stars.
- sickn33/agentic-awesome-skills claimed 347 — actual 46,355 stars (it's an awesome-list
  bundle, not a single-skill repo).
- glebis/claude-skills claimed 246 — actual 376 stars.
- blink-new/claude claimed 181 — actual 1 star; no LICENSE file; 2.5mo stale.
- aws-samples/sample-strands-agent-with-agentcore claimed 56 — actual 191 stars.
- membranedev/application-skills (zoho-mail + mailgun) — repos do not exist on GitHub.
- tiangong-ai-staging/agent-skills (operator wrote `tiangong-ai/skills`) — the staging
  org is the real one; the bare `tiangong-ai` user has 0 public repos.
- boomsystel-code/openclaw-workspace claimed 1.9K — actual 0 stars; no LICENSE; 7mo stale.

These numbers are not install counts from `skills.sh` — they are direct `gh api
repos/<owner>/<repo>` queries.

---

## 6. Operator ratification items (HUMAN_DOMAIN gate)

These items touch AAIF skill design, vendor trust boundaries, or repo-license unknowns.
Per the comm-egregoræ chassis (§9, red-team-pending) and `pre-decision-audit` doctrine, none
of them execute without operator sign-off.

1. **Adopt `openclaw/openclaw/skills/gog` + `skills/himalaya` as primary surface skills** for
   email-messenger v0.2+. Both are AAIF-spec-compliant, MIT/Apache-2.0, locally installed,
   actively maintained. Adds MSGraph + Gmail + IMAP/SMTP/JMAP/Maildir coverage with one
   `brew install`.
2. **Mirror sanjay3290/ai-skills/skills/gmail as a fallback** only when `gog` is not on PATH;
   document the 3rd-party token-refresh endpoint risk in any local wrapper.
3. **Reuse boomsystel-code/openclaw-workspace/skills/imap-smtp-email for 163/QQ/126/YEAH/
   188** only with explicit "no upstream LICENSE, snapshot reuse" notice — provenance and
   attribution are mandatory.
4. **Do NOT pursue agentqq/agently-mail or membranedev/application-skills** — they do not
   resolve to real GitHub repos. The GAP entries in §3.4 stand.
5. **Treat `sickn33/agentic-awesome-skills/skills/outlook-automation` as a non-candidate**
   because it routes through Rube MCP (Composio) — bypasses native himalaya msgraph for no
   operator benefit.
6. **Defer the `GAP` items in §3.4** (Outlook.com personal, cross-client threading,
   multi-vendor OAuth vault, M365 personal personal) to a follow-up sprint — no candidate
   covers them today, and forking now without a real prototype is YAGNI.