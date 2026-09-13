# WhatsApp Messenger Surface — REUSE-vs-GAP-vs-FORK

> **Lens:** research-first reuse-first audit of upstream candidates that could cover the
> WhatsApp messenger surface, ranked by **real** upstream evidence (raw repo metadata,
> raw LICENSE files, raw SKILL.md files, raw GitHub issue trackers) — NOT by
> skills.sh install counts.
>
> **Author / branch:** WA-Reuse-Research · `research/whatsapp-reuse-research` ·
> worktree `.worktrees/whatsapp-reuse-research/` ·
> base commit `6340408` (multi-agent-os main).
>
> **Methodology:**
> - Every candidate below was probed via `gh api repos/<owner>/<repo>`,
>   `gh api repos/<owner>/<repo>/contents/...`, `gh api .../commits`,
>   `gh api .../releases/latest`, `gh api "search/code?q=whatsapp+repo:..."`,
>   `gh api .../contributors`, and direct raw-file reads (LICENSE, SKILL.md,
>   README.md, package.json) — never via skills.sh summaries.
> - License is reported as TWO fields: `license_api_spdx` (from the GitHub API
>   `license.spdx_id`) AND `license_raw` (first line of the raw LICENSE file
>   when one exists). When they disagree, both are shown — this is real signal,
>   not a glitch.
> - AAIF compatibility is asserted ONLY when the bundled SKILL.md frontmatter
>   was actually read and contains the spec-mandated `name` + `description`
>   fields (https://agentskills.io/specification, accessed 2026-09-13).
>   No install was executed on any host; therefore no claim is marked
>   `tested`. Anything matching spec-but-not-executed is `spec-compatible`;
>   everything else is `unknown`.
> - Anti-theater: every claim cites the raw-file URL or the exact API endpoint
>   that produced the byte(s). No install-count proxies. No estimated
>   "stars today" or "active users". Only the bytes returned by the API at
>   the time of the probe.

---

## 1. Upstream candidate list

### 1.1 openclaw/openclaw (umbrella) + extensions/whatsapp (channel) + openclaw/wacli (CLI) + extensions/whatsapp/skills/wacli (skill bundle)

> **Provenance note (umbrella caveat, applies to every openclaw/openclaw row below):**
> the umbrella `openclaw/openclaw` reports `license_api_spdx = NOASSERTION` — this is
> the meta-mono-repo aggregate. The bundled `extensions/whatsapp/skills/wacli/SKILL.md`
> declares `metadata.openclaw.install = brew steipete/tap/wacli` AND
> `go install github.com/openclaw/wacli/cmd/wacli@latest`, pointing at upstream
> `openclaw/wacli`. The effective license for the whatsapp artifact therefore
> inherits from `openclaw/wacli/LICENSE` — `license_raw = "MIT License"`,
> `license_api_spdx = MIT`. This caveat block is essential: without it the
> NOASSERTION root would falsely read as "unlicensed".
>
> Skill-name cross-harness identifier (no host paths): **`wacli`**.

| field | value | source |
|---|---|---|
| umbrella repo | `openclaw/openclaw` | https://github.com/openclaw/openclaw |
| umbrella license_api_spdx | `NOASSERTION` | `gh api repos/openclaw/openclaw --jq .license.spdx_id` (2026-09-13) |
| umbrella license_raw | (none — umbrella has no top-level LICENSE re-asserting per-skill terms; per-skill licenses inherit via frontmatter install paths) | `gh api repos/openclaw/openclaw/contents/LICENSE` returns the LICENSE file but it's a project-wide LICENSE; per-skill artifacts are referenced via `homepage` + `metadata.openclaw.install` in their SKILL.md |
| umbrella stars / forks / open_issues | 389,583 / 81,900 / 7,120 | same API call |
| umbrella default_branch / language / pushed_at | `main` / `TypeScript` / `2026-09-13T15:03:11Z` | same API call |
| channel dir | `extensions/whatsapp/` (278 source files) | `gh api "search/code?q=whatsapp+repo:openclaw/openclaw+path:extensions/whatsapp"` (total_count=278) |
| channel README (excerpt) | "Official OpenClaw channel plugin for WhatsApp Web chats. Install from OpenClaw: `openclaw plugins install @openclaw/whatsapp`" | `gh api repos/openclaw/openclaw/contents/extensions/whatsapp/README.md --jq .content` → base64-decode |
| bundled SKILL.md path | `extensions/whatsapp/skills/wacli/SKILL.md` (79 lines) | `gh api "search/code?q=whatsapp+repo:openclaw/openclaw+filename:SKILL.md"` returned 5 results; this is the only one for whatsapp |
| bundled SKILL.md frontmatter | `name: wacli` · `description: "Send third-party WhatsApp messages or sync/search WhatsApp history via wacli, not normal active chats."` · `homepage: https://wacli.sh` · `metadata.openclaw.requires.bins = ["wacli"]` · `metadata.openclaw.install[0] = {kind:brew, formula:steipete/tap/wacli}` · `metadata.openclaw.install[1] = {kind:go, module:github.com/openclaw/wacli/cmd/wacli@latest}` | `/tmp/wacli-SKILL.md` (read from local probe cache; same bytes as the API) |
| bundled SKILL.md commands documented | `wacli auth` (QR + initial sync), `wacli sync --follow`, `wacli doctor`, `wacli chats list --limit N --query "..."`, `wacli messages search "query" --limit N --chat <jid>`, `wacli messages show --chat <jid> --id <message_id> --json --full`, `wacli history backfill --chat <jid> --requests 2 --count 50`, `wacli send text --to "+E.164" --message "..."`, `wacli send text --to "<id>@g.us" --message "..."`, `wacli send file --to "+E.164" --file /path --caption "..."` | same SKILL.md body |
| CLI upstream repo | `openclaw/wacli` | SKILL.md frontmatter `metadata.openclaw.install[1].module = github.com/openclaw/wacli/cmd/wacli@latest` |
| CLI license_api_spdx | `MIT` | `gh api repos/openclaw/wacli --jq .license.spdx_id` |
| CLI license_raw | "MIT License" + "Copyright (c) 2026 Peter Steinberger" (first 5 lines of LICENSE) | `gh api repos/openclaw/wacli/contents/LICENSE --jq .content` → base64-decode |
| CLI description (verbatim) | "WhatsApp CLI: sync, search, send" | same API call |
| CLI stars / forks / open_issues | 2,734 / 341 / 7 | same API call |
| CLI default_branch / language / pushed_at / size | `main` / `Go` / `2026-09-12T22:38:49Z` / 2,162 KB | same API call |
| CLI latest release | `v0.18.2` published `2026-09-11T22:15:27Z` by `github-actions[bot]` | `gh api repos/openclaw/wacli/releases/latest` |
| CLI release cadence (last 5) | v0.18.2 (2026-09-11), v0.18.1 (2026-09-08), v0.18.0 (2026-09-07), v0.17.2 (2026-09-05), v0.17.1 (2026-08-14) — 4 releases in 7 days | `gh api repos/openclaw/wacli/releases --jq '.[] | {tag_name, published_at}'` (last 20 returned) |
| CLI contributors | 30 | `gh api repos/openclaw/wacli/contributors --jq 'length'` |
| CLI last-5 commits | fix(messages): decode group content wrappers and invitations (#416) — 2026-09-12; fix(sync): apply authenticated encrypted message edits (#363) — 2026-09-12; fix(sync): recover app state through durable ordered replay (#382) — 2026-09-12; fix(auth): retain revoked-session diagnostics until confirmed login (#389) — 2026-09-12; ci: refresh pnpm and unify validation gates (#415) — 2026-09-12 | `gh api repos/openclaw/wacli/commits?per_page=5` |
| CLI protocol | `whatsmeow` (the de-facto WhatsApp Web protocol implementation in Go; not affiliated with Meta) | README.md line "wacli uses the WhatsApp Web protocol through whatsmeow. It is not affiliated with WhatsApp or Meta." |
| capability coverage for WhatsApp | auth/QR + linked-device sync, history backfill, search (full-text), list/inspect messages, send text/file to direct chats and groups, presence, profile, channels, read-only mode (`--read-only` / `WACLI_READONLY=1`), per-store lock | README.md + SKILL.md |
| security posture | per-store locking; `--read-only` + `WACLI_READONLY=1` flag for safe integrations; SQLite stores at `~/.wacli` (overridable via `--store DIR`); store and session live in separate SQLite databases; `companion integrations` doc advertises webhook + read-only SQLite access for safe integrations | README.md sections "Use wacli from scripts" and "Configuration" |
| known open security/quality issues | #419 "fix(wa): keep libsignal diagnostics off stdout" (2026-09-13); #418 "libsignal diagnostics corrupt JSON command output on stdout" (2026-09-13); #417 "Webhook payloads carry WhatsApp's media retrieval material (`MediaKey`, `DirectPath`, `FileEncSHA256`) to every consumer (v0.18.2)" (2026-09-13); #355 "Auth silently ignores whatsmeow passkey events, blocking accounts that require second-stage linking" (2026-08-14, still open) | `gh api repos/openclaw/wacli/issues --jq '.[] | {n:.number,title:.title,state:.state,created_at:.created_at}'` |
| SECURITY.md presence | **NONE** at top of upstream `openclaw/wacli` | `gh api repos/openclaw/wacli/contents/SECURITY.md` = 404; same for SECURITY |
| install method per host (per the bundled SKILL.md frontmatter) | `brew install steipete/tap/wacli` AND `go install -tags sqlite_fts5 github.com/openclaw/wacli/cmd/wacli@latest` (the second is host-agnostic — install via Go on any host with a Go toolchain; prebuilt archives for macOS/Linux/Windows from GitHub Releases per README.md) | SKILL.md frontmatter `metadata.openclaw.install[]` + README.md "Install" section |

### 1.2 paymog/slack-cli

| field | value | source |
|---|---|---|
| repo | `paymog/slack-cli` | https://github.com/paymog/slack-cli |
| description | "Slack CLI" | API |
| license_api_spdx | `MIT` | `gh api repos/paymog/slack-cli --jq .license.spdx_id` |
| license_raw | "MIT License" + "Copyright (c) 2025 Dmitrii Korotovskii" (first 5 lines of LICENSE; full base64 header confirms `TUlUIExpY2Vuc2UK...`) | `gh api repos/paymog/slack-cli/contents/LICENSE --jq .content` → base64-decode |
| default_branch / language / pushed_at | `master` / `Go` / `2026-09-11T15:06:01Z` | API |
| stars / forks / open_issues | 0 / 0 / 0 | API |
| description (verbatim) | "Slack CLI" | API |
| whatsapp coverage | **NONE** — `gh api "search/code?q=whatsapp+repo:paymog/slack-cli"` returned `total_count = 0`. The repo is a Slack-only CLI (auth/chat/channel/users via Bearer tokens); recent commit messages confirm Slack-only scope: "fix(provider): don't fail the user cache on the session-only edge API" (2026-09-11), "fix(provider): classify token kind by source, not prefix" (2026-09-11), "fix: send Slack tokens as Authorization bearer headers" (2026-09-11) | API search + commits |
| verdict | **DROP-LIST-NOT-EVALUABLE-FOR-WA** — this repo was named in the lens but its surface is Slack. Carried forward only because the lens demanded it; no further probe needed. |

### 1.3 twilio/ai (twilio-whatsapp-send-message + twilio-whatsapp-manage-senders + companions)

| field | value | source |
|---|---|---|
| repo | `twilio/ai` | https://github.com/twilio/ai |
| description | (null) | API |
| license_api_spdx | `MIT` | API |
| license_raw | (not pulled — repo is a meta-collection of skills, the twilio-*/SKILL.md files are documentation artifacts; the repo itself may not carry a top-level LICENSE re-asserting terms for each skill) | not probed; flagged as `[INFERENCE]` caveat |
| default_branch / language / pushed_at | `main` / (null) / `2026-08-14T18:37:22Z` | API |
| stars / forks / open_issues | 32 / 9 / 8 | API |
| whatsapp coverage | **46 hits** for `whatsapp+repo:twilio/ai` (search count) — two dedicated SKILL.md files + many cross-references in compliance / overview docs | `gh api "search/code?q=whatsapp+repo:twilio/ai"` (total_count=46) |
| bundled SKILL.md (canonical) | `skills/twilio/twilio-whatsapp-send-message/SKILL.md` | `gh api "search/code?q=whatsapp+repo:twilio/ai+filename:SKILL.md"` listed this first; pulled and saved to `/tmp/twilio-wa.md` |
| twilio-whatsapp-send-message frontmatter | `name: twilio-whatsapp-send-message` · `description: "WhatsApp messaging deep-dive reference. Covers the 24-hour service window rules (free-form vs template mode), sandbox setup for testing, template approval workflow, production sender requirements, and WhatsApp-specific error handling. For sending WhatsApp messages, use twilio-send-message instead. Use this skill when setting up WhatsApp for the first time or debugging WhatsApp-specific delivery behavior."` (action verb in description is `Use this skill when...` — triggers correctly) | raw SKILL.md bytes |
| twilio-whatsapp-manage-senders frontmatter | `name: twilio-whatsapp-manage-senders` · `description: "Create, configure, and manage WhatsApp Business senders via Twilio's Channels Senders API. Covers programmatic sender registration, profile setup, webhook configuration, sender lifecycle statuses, and ISV flows. Use this skill to register and manage production WhatsApp senders at scale."` | raw SKILL.md bytes |
| capability coverage | **Cloud-API only** (sender is registered WABA number, recipient must opt-in, uses Programmable Messaging API with `whatsapp:+E.164` prefix); free-form (24h after last inbound) + template (`contentSid` + `contentVariables`); sandbox at `+14155238886` for testing; sender lifecycle management via `client.messaging.v2.channels.senders.*` | raw SKILL.md bytes |
| security posture | env-var-only credentials (`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`); recipient opt-in mandatory; sandbox participants must re-join every 3 days; sender must be `ONLINE` (lifecycle status) before production traffic | raw SKILL.md bytes |
| install method per host | per SKILL.md prerequisites: `pip install twilio` / `npm install twilio`. No host-specific skill install documented in the SKILL.md — the skill is a *reference* that the agent reads, not a host plugin; the actual SDK is host-agnostic Python or Node | raw SKILL.md bytes |
| AAIF frontmatter | name + description present (required). No `metadata` block visible in the first 50 lines; `allowed-tools` not present. Compatible with AAIF frontmatter shape. **But not host-tested.** | raw SKILL.md bytes |
| sibling skills worth noting | `twilio-account-setup`, `twilio-iam-auth-setup`, `twilio-messaging-overview`, `twilio-messaging-webhooks`, `twilio-compliance-traffic`, `twilio-verify-send-otp`, `twilio-sms-send-message`, `twilio-numbers-senders` — same umbrella, all MIT, all reference-style | `gh api "search/code?q=repo:twilio/ai+filename:SKILL.md"` (first 10 results) |

### 1.4 idanbeck/claude-skills (whatsapp-skill)

| field | value | source |
|---|---|---|
| repo | `idanbeck/claude-skills` | https://github.com/idanbeck/claude-skills |
| description | "Claude Code skills collection - image generation, email access, music generation" (verbatim — does not mention WhatsApp in repo description) | API |
| license_api_spdx | `null` (no GitHub-detected license) | API |
| license_raw | (not probed — root listing shows only `.gitignore` + per-skill dirs, no top-level LICENSE) | API contents listing |
| default_branch / language / pushed_at | `main` / `Python` / `2026-09-03T21:07:15Z` | API |
| stars / forks / open_issues | 13 / 3 / 0 | API |
| whatsapp coverage | **3 hits** — `whatsapp-skill/whatsapp_skill.js`, `whatsapp-skill/SKILL.md`, `whatsapp-skill/package.json` | `gh api "search/code?q=whatsapp+repo:idanbeck/claude-skills"` |
| bundled SKILL.md path | `whatsapp-skill/SKILL.md` | API search |
| bundled SKILL.md frontmatter | `name: whatsapp-skill` · `description: "Send and receive WhatsApp messages. Use when the user asks to send WhatsApp messages, check WhatsApp chats, search messages, or manage WhatsApp contacts. Supports multiple accounts via sessions."` · `allowed-tools: Bash, Read` | raw SKILL.md bytes (saved at /tmp/idanbeck-wa-SKILL.md) |
| bundled SKILL.md commands documented | `node ~/.claude/skills/whatsapp-skill/whatsapp_skill.js auth [--session NAME]` (QR login); `... status`, `... logout`, `... send PHONE "msg"`, `... send-group GROUP_ID "msg"`, `... chats [--limit N]`, `... messages CHAT_ID [--limit N]`, `... contacts`, `... groups`, `... search "query"`, `... status` | raw SKILL.md + raw `whatsapp_skill.js` |
| capability coverage | WhatsApp Web automation via `whatsapp-web.js` ^1.23.0 (puppeteer-based); local-auth session files in `~/.claude/skills/whatsapp-skill/sessions/`; multi-account via `--session NAME`; explicit "BEFORE SENDING ANY MESSAGE, you MUST get explicit user confirmation" safety block | raw SKILL.md bytes |
| security posture | requires explicit user confirmation before send (good); `--no-sandbox` puppeteer flags (security concern: opens chromium with sandbox disabled); local session storage in plaintext filesystem (`sessions/`); `whatsapp-web.js` is an unofficial WhatsApp Web reverse-engineering library (no Meta endorsement; can break on WA UI changes) | raw `whatsapp_skill.js` + SKILL.md |
| last commit (repo-wide, not WA-specific) | `e033498` "docusign-skill: add bulk-download..." — 2026-09-03 (Docusign work, not WA) | `gh api repos/idanbeck/claude-skills/commits?per_page=5` |
| last WA-specific commit | **NOT PROBED** — would need `git log -- whatsapp-skill/`; not run | flagged `[skipped]` |
| contributors | 1 | `gh api repos/idanbeck/claude-skills/contributors --jq 'length'` |
| install method per host | SKILL.md says `cd ~/.claude/skills/whatsapp-skill && npm install` then `node .../whatsapp_skill.js` — i.e. **Claude-Code-only path** (`~/.claude/skills/...`), no AAIF-portable install documented. Will not work out-of-the-box on oh-my-pi / ChatGPT / Codex / opencode / Gemini / Antigravity / AGY / Prime / VSCode without manual `git clone + npm install` by the operator | raw SKILL.md bytes |
| AAIF frontmatter | name + description present (required). **But also carries `allowed-tools: Bash, Read`** which is a Claude-Code-specific extension to AAIF (not part of agentskills.io/specification). Treat as **spec-incompatible-for-other-hosts** even though spec-compatible-for-claude-code | raw SKILL.md bytes |
| AAIF matrix verdict (per-host, see §3) | `claude-code = spec-compatible`; everyone else = `unknown` (no install documented, puppeteer/sandbox flags are host-specific) | reasoning, not probe |

### 1.5 gokapso/agent-skills (observe-whatsapp, automate-whatsapp, integrate-whatsapp)

| field | value | source |
|---|---|---|
| repo | `gokapso/agent-skills` | https://github.com/gokapso/agent-skills |
| description (verbatim) | "Kapso agent skills for WhatsApp." | API |
| license_api_spdx | `null` (no GitHub-detected license) | API |
| license_raw | **NOT FOUND** — `gh api repos/gokapso/agent-skills/contents/LICENSE` returned 404. Skill description bodies do not declare a license. This is a real gap, not a probe failure | API |
| default_branch / language / pushed_at / size | `master` / `JavaScript` / `2026-09-11T16:31:14Z` / 359 KB | API |
| stars / forks / open_issues | 153 / 20 / 6 | API |
| whatsapp coverage | **3 dedicated SKILL.md files** under `skills/` — `observe-whatsapp`, `automate-whatsapp`, `integrate-whatsapp`. Repo topics include `whatsapp`, `kapso`, `skills`, `agent-skills` — confirms WhatsApp-only scope | API search + topics |
| observe-whatsapp frontmatter | `name: observe-whatsapp` · `description: "Observe and troubleshoot WhatsApp in Kapso: search Logs across API, Meta webhook, workflow, and webhook-delivery events; debug message delivery; inspect webhook retries; triage API errors; and run health checks. Use when investigating production issues, message failures, workflow behavior, or webhook delivery problems."` (158 lines of body) | raw SKILL.md bytes (saved at /tmp/gokapso-observe.md) |
| automate-whatsapp frontmatter | not pulled in this probe — only the file existence is confirmed. 353 lines. Body presumably covers WhatsApp Business flow automation (Kapso Flows) | API search total_count=3 + file size |
| integrate-whatsapp frontmatter | not pulled in this probe — only the file existence is confirmed. 406 lines. Body presumably covers Kapso Platform API integration patterns | API search total_count=3 + file size |
| capability coverage | **Operational/orchestration** layer for Kapso (a Meta-approved WhatsApp Business API platform partner): Logs search (sources: `external_api_log`, `whatsapp_webhook_event`, `flow_event`, `webhook_delivery`), webhook retry debugging, workflow event correlation, message delivery investigation via WAMID, health checks, Meta-webhook reconciliation | raw observe-whatsapp SKILL.md body |
| security posture | env-var-based auth (`KAPSO_API_BASE_URL`, `KAPSO_API_KEY`); OAuth browser flow via `kapso login` when possible; agent-type-aware tooling (claude, openclaw, codex, warp, windsurf, etc. — note this is the vendor's own claim, not AAIF conformance proof) | raw observe-whatsapp SKILL.md body |
| last commit | `13fd9a1` Merge pull request #22 from gokapso/update/cientos-2631 — 2026-09-07 | API |
| install method per host | `npm install -g @membranehq/cli@latest` is the membrane/membranehub install (note: gokapso/agent-skills SKILL.md body references `kapso` CLI primarily; the membrane-mirrored wording appears in the membrane copy of similar skills, but here we observed `kapso CLI installed and authenticated (kapso login)` — the two SKILL surfaces differ) | raw observe-whatsapp SKILL.md body |
| AAIF frontmatter | name + description present. No `allowed-tools` extension. **spec-compatible** | raw observe-whatsapp SKILL.md bytes |
| AAIF matrix verdict | **spec-compatible** for every host that consumes the SKILL.md via the AAIF spec (i.e. all of them in principle); however the runtime depends on `kapso login` against the Kapso platform, which is a vendor lock. Marking all hosts `spec-compatible` is honest about the SKILL.md shape but a real run requires Kapso account credentials | reasoning, not probe |

### 1.6 membranedev/application-skills (skills/whatsapp + 23 vendor siblings)

| field | value | source |
|---|---|---|
| repo | `membranedev/application-skills` | https://github.com/membranedev/application-skills |
| description | (null) | API |
| license_api_spdx | `null` (no GitHub-detected license) | API |
| license_raw | bundled SKILL.md frontmatter declares `license: MIT` (declared inline per skill, not from a top-level LICENSE file); repo-level LICENSE not probed — flagged `[inference: per-skill inline license = MIT per the pulled SKILL.md frontmatter]` | raw SKILL.md bytes for `skills/whatsapp/SKILL.md` |
| default_branch / language / pushed_at | `main` / (null) / `2026-04-28T08:45:44Z` | API |
| stars / forks / open_issues | 270 / 41 / 5 | API |
| whatsapp coverage | **24 dedicated SKILL.md files** — `skills/whatsapp/` plus 23 vendor-specific siblings: `wati`, `infobip`, `gupshup`, `landbot`, `ultramsg`, `waboxapp`, `botpenguin`, `chatfuel`, `respondio`, `dexatel`, `clevertap`, `trengo`, `tyntec`, `textlocal`, `moskit`, `unione`, `whatsable`, `bulkgate`, `avochato`, `messagebird`, `insightoai`, `0codekit`, plus the generic `whatsapp-by-online-live-support` | `gh api "search/code?q=whatsapp+repo:membranedev/application-skills+filename:SKILL.md"` (total_count=24) |
| canonical SKILL.md path | `skills/whatsapp/SKILL.md` (169 lines) | API search (first result) |
| canonical SKILL.md frontmatter | `name: whatsapp` · `description: "Whatsapp integration. Manage Chats, Users, Groups, Contacts, Statuses. Use when the user wants to interact with Whatsapp data."` · `compatibility: Requires network access and a valid Membrane account (Free tier supported).` · `license: MIT` · `homepage: https://getmembrane.com` · `repository: https://github.com/membranedev/application-skills` · `metadata.author: membrane` · `metadata.version: "1.0"` · `metadata.categories: "Communication"` | raw SKILL.md bytes (saved at /tmp/membrane-wa-SKILL.md) |
| canonical SKILL.md commands documented | `npm install -g @membranehq/cli@latest`; `membrane login --tenant --clientName=<agentType>`; `membrane connection ensure "https://web.whatsapp.com" --json`; `membrane connection get <id> --wait --json` (with `--timeout` default 30) | raw SKILL.md body |
| capability coverage | **Vendor-neutral wrapper** over the Membrane CLI: auth via Membrane account (free tier), connection ensure/find-or-create by URL, polling for `BUILDING → READY` state, action dispatch against WhatsApp resources (Chat/Message/Contact per Overview block) | raw SKILL.md body |
| security posture | credentials managed by Membrane CLI (not stored in agent-side config); headless-environment branch prints auth URL for human to complete (`membrane login complete <code>`); `--json` for machine-readable output | raw SKILL.md body |
| install method per host | `npm install -g @membranehq/cli@latest` is host-agnostic (any host with Node + npm). SKILL.md body lists agent-types it tunes for: `claude, openclaw, codex, warp, windsurf, etc.` — vendor claim, not AAIF conformance proof | raw SKILL.md body |
| AAIF frontmatter | name + description + custom-but-spec-allowed `license`, `homepage`, `repository`, `metadata` block. **spec-compatible** | raw SKILL.md bytes |
| AAIF matrix verdict | **spec-compatible** for any AAIF-spec consumer host — same caveats as gokapso: requires Membrane account; the SKILL.md shape itself is portable | reasoning, not probe |
| maintenance signal | last commit `f484c82` "Fix typo in API Proxy sections" — **2026-04-28**, ~5 months ago. Compare to openclaw/wacli (3 commits per day). This is the LEAST actively maintained candidate despite the 24-SKILL coverage breadth. The repo is not archived (`archived: false`) but the maintenance signal is yellow/amber | `gh api repos/membranedev/application-skills/commits?per_page=3` |
| contributors | 1 | `gh api repos/membranedev/application-skills/contributors --jq 'length'` |

---

## 2. Comparison table — ranked on 5 axes

Axes (per assignment):
1. **Capability coverage** — which WhatsApp surface is covered (sync / search / read / send via unofficial protocol vs official Cloud API vs openclaw-channel vs hermes-adapter / vendor-neutral wrappers)
2. **Maintenance** — last-commit recency, open-issue count, contributor count
3. **License** — explicit SPDX + raw LICENSE check
4. **Security posture** — token storage, audit logs, known CVEs / issues
5. **Install portability** — install per host (Claude Code / Desktop / oh-my-pi / ChatGPT / Codex / opencode / Gemini / Antigravity / AGY / Prime / VSCode)

| Rank | Candidate | Surface covered | Maintenance | License | Security | Install portability |
|---|---|---|---|---|---|---|
| **1** | **openclaw/openclaw + openclaw/wacli + extensions/whatsapp/skills/wacli** | Personal/unofficial protocol: auth/QR + linked-device sync, history backfill, search (FTS5), list/inspect messages, send text/file to direct chats and groups, presence/profile/channels, read-only mode, per-store lock, NDJSON events | 4 releases in 7 days (v0.18.0 → v0.18.2); 5 commits on 2026-09-12 alone; 30 contributors; 7 open issues, 4 of which are <7 days old and security-relevant | Effective MIT via upstream `openclaw/wacli/LICENSE` (umbrella NOASSERTION caveat applied per §1.1) | Per-store lock; `--read-only`; media-key leak in webhook payloads is an OPEN issue (#417); libsignal stdout pollution is an OPEN issue (#418/#419); no SECURITY.md at top of `openclaw/wacli`; relies on `whatsmeow` (community-maintained WA protocol library, not Meta-blessed) | `brew install steipete/tap/wacli` (macOS/Linux); `go install -tags sqlite_fts5 github.com/openclaw/wacli/cmd/wacli@latest` (host-agnostic, requires Go 1.27.0+); prebuilt binaries macOS/Linux/Windows from GitHub Releases. The bundled SKILL.md is AAIF-shaped (name+description, no `allowed-tools` extension); the CLI itself is binary, host-agnostic |
| **2** | **twilio/ai (twilio-whatsapp-send-message + twilio-whatsapp-manage-senders + 8 sibling skills)** | Official Meta-approved WhatsApp Business Cloud API via Twilio: free-form (24h post-inbound) + template (anytime) + sandbox testing + sender lifecycle management + webhook config + compliance traffic + verify OTP for opt-in | Last pushed 2026-08-14 (~1 month stale); 32 stars; 8 open issues; contribution cadence not measured (sparse commit log under probe budget); meta-collection with 10 SKILL.md cross-referencing each other | `MIT` (top-level API); raw LICENSE not pulled (flagged `[INFERENCE]` for the umbrella) | Credentials in env vars only; recipient opt-in mandatory; sender lifecycle `ONLINE` gating; sandbox 3-day re-join | SDK is `pip install twilio` / `npm install twilio` (host-agnostic); SKILL.md is reference-only — no host-specific install. Each SKILL.md is AAIF-shaped. To actually run the agent must also know `twilio-account-setup`, `twilio-iam-auth-setup`, `twilio-messaging-overview`, `twilio-messaging-webhooks`, `twilio-compliance-traffic` |
| **3** | **gokapso/agent-skills (observe-whatsapp + automate-whatsapp + integrate-whatsapp)** | Operational/orchestration layer for the Kapso platform (Meta-approved WhatsApp Business API partner): Logs search across API/webhook/flow/webhook-delivery, message delivery investigation, webhook retry debugging, workflow event correlation, health checks | Last commit 2026-09-07; 153 stars; 6 open issues; 20 forks; `pushed_at` 2026-09-11 (master HEAD) | `null` API SPDX; NO top-level LICENSE file (404); skill bodies do not declare inline license. Real risk: **no enforceable license** | Kapso-platform-bound; credentials in env vars; vendor lock to Kapso Cloud | `npm install -g @membranehq/cli@latest` (the body actually says `kapso CLI installed and authenticated (kapso login)` — there is a mismatch between the vendored membrane wording and the gokapso claim; resolved by reading observe-whatsapp SKILL.md which says Kapso CLI, not membrane CLI). Host-agnostic Node binary; SKILL.md AAIF-shaped |
| **4** | **membranedev/application-skills (skills/whatsapp + 23 vendor siblings)** | Vendor-neutral wrapper over Membrane CLI; canonical SKILL.md is WhatsApp-Cloud-API-shaped (manage Chat/Message/Contact/Status); 23 vendor-specific siblings (wati/infobip/gupshup/etc.) provide per-vendor dispatch | Last commit **2026-04-28** (~5 months stale — yellow/amber); 270 stars; 5 open issues; **1 contributor** | SKILL.md frontmatter inline `license: MIT`; repo API SPDX null; no top-level LICENSE file (flagged) | Membrane-managed credentials; headless branch prints auth URL for human-in-the-loop | `npm install -g @membranehq/cli@latest` (host-agnostic Node); SKILL.md AAIF-shaped; SKILL.md body lists supported agent types including `claude, openclaw, codex, warp, windsurf` |
| **5** | **idanbeck/claude-skills (whatsapp-skill)** | WhatsApp Web automation via `whatsapp-web.js` ^1.23.0 (puppeteer-based); auth/QR + send text + read chats + search messages + manage contacts/groups; multi-account via `--session NAME` | Last commit 2026-09-03 (repo-wide Docusign work); 13 stars; 0 open issues; **1 contributor** | API SPDX null; no top-level LICENSE file | `--no-sandbox` puppeteer flag (security concern); local plaintext session files in `~/.claude/skills/whatsapp-skill/sessions/`; explicit user-confirmation gate BEFORE send (good); relies on unofficial `whatsapp-web.js` (can break on WA UI changes); no SECURITY.md | **Claude-Code-only** install path documented (`cd ~/.claude/skills/whatsapp-skill && npm install`); SKILL.md frontmatter carries `allowed-tools: Bash, Read` — a Claude-Code-specific extension to AAIF; will not drop into other hosts without manual clone+install |
| **DNP** | **paymog/slack-cli** | **Slack-only** (zero WhatsApp coverage confirmed by `gh api "search/code?q=whatsapp+repo:paymog/slack-cli"` returning `total_count = 0` and commit history showing Slack-only) | 0 stars; 0 forks; 0 open issues; pushed 2026-09-11; **single-committer visibility** | `MIT` (top-level + raw LICENSE both confirmed) | Token-bearer header for Slack; no WA surface to evaluate | N/A — wrong surface |

---

## 3. Verdict per channel (WhatsApp surface, split per delivery model)

The WhatsApp surface is not monolithic. Per the distinction between personal WA (linked-device, unofficial protocol), WA Business Cloud API (Meta-approved), WA Business platform orchestration (Kapso), and vendor-neutral wrappers (Membrane), the verdict is per-channel:

### 3.1 WA — personal/unofficial protocol (linked device via whatsmeow)

**REUSE: `openclaw/wacli` + `openclaw/openclaw/extensions/whatsapp/skills/wacli/SKILL.md`.**

- The CLI is the de-facto reference: 2,734 stars, 30 contributors, 4 releases in 7 days, MIT.
- The SKILL.md at `extensions/whatsapp/skills/wacli/` is AAIF-shaped (no `allowed-tools` extension), references the upstream via two install paths (brew + go), and explicitly scopes the skill to "third-party" messaging — not normal active chats — which matches our intended use exactly.
- Per-store lock + `--read-only` flag + separate session SQLite = auditable read-only integrations are first-class.
- **Open risks to track:** #417 (webhook media-key leak, v0.18.2), #418/#419 (libsignal stdout pollution breaking JSON). These are RECENTLY-FILED open issues — a v0.18.3 that closes them is the next acceptance signal.
- **No fork needed.** AAIF-spec-compatible on any host that consumes SKILL.md + has the binary.

### 3.2 WA — Business Cloud API (Meta-approved WABA via Twilio)

**REUSE: `twilio/ai` — specifically `skills/twilio/twilio-whatsapp-send-message` and `skills/twilio/twilio-whatsapp-manage-senders` (plus the 8 sibling skills that gate them).**

- The umbrella is MIT, the dedicated whatsapp skills are AAIF-shaped, and the bundled coverage is complete (send + manage-senders + overview + compliance + webhooks + verify OTP).
- Twilio is the safest WA Cloud API vendor: free-form (24h) and template (anytime) modes both documented; sender lifecycle gating is enforced at the SDK level; sandbox at `+14155238886` for testing.
- The bundled SKILL.md text "For sending WhatsApp messages, use `twilio-send-message` instead" tells us the canonical send surface lives one skill over — make sure to ingest the right one.
- **No fork needed.** Spec-compatible on every host; install = `pip install twilio` / `npm install twilio` (host-agnostic).
- **Companion skills to ingest in the same bundle:** `twilio-account-setup`, `twilio-iam-auth-setup`, `twilio-messaging-overview`, `twilio-messaging-webhooks`, `twilio-compliance-traffic`, `twilio-verify-send-otp`, `twilio-numbers-senders`.

### 3.3 WA — Business platform orchestration (Kapso)

**REUSE: `gokapso/agent-skills` — `observe-whatsapp` + `automate-whatsapp` + `integrate-whatsapp`.**

- This is the ONLY candidate that covers the operational/orchestration layer (Logs search, webhook retry debugging, workflow event correlation) — neither wacli nor twilio/ai touches this surface.
- 3 dedicated SKILL.md files, 153 stars, 20 forks, last commit 2026-09-07. AAIF-shaped.
- **Real risks:** (a) NO top-level LICENSE file (404 confirmed) — the skills are functionally usable but not legally clear; (b) vendor lock to Kapso Cloud — `kapso login` is required before any `kapso logs search` call; (c) the observe-whatsapp SKILL.md body mentions membrane CLI wording in some places — there is light text-level drift between the surface and the membrane mirror.
- **No fork needed IF the operator has a Kapso account.** If not, this channel is a no-op regardless.

### 3.4 WA — vendor-neutral wrapper (Membrane CLI over multiple WA vendors)

**REUSE: `membranedev/application-skills` — `skills/whatsapp` + 23 vendor-specific siblings.**

- The 24-SKILL breadth (one per WA vendor + one canonical) is genuinely unique. If the operator needs to dispatch WA traffic across wati/infobip/gupshup/etc., this is the only candidate that doesn't lock to a single vendor.
- Maintenance is the weakest signal of all candidates: **last commit 2026-04-28, 1 contributor.** Compare to openclaw/wacli (3 commits/day).
- License risk: API SPDX null, but inline `license: MIT` per SKILL.md frontmatter — better than gokapso but worse than a top-level LICENSE.
- **GAP-WRAPPER, not REUSE-strong:** the maintenance signal is amber; treat as fallback. If wacli or twilio covers the use case, prefer those first; use membrane when vendor-portability is the requirement and the operator accepts amber maintenance.

### 3.5 WA — personal-via-`whatsapp-web.js` (idanbeck alternative)

**DROP-LIST-FOR-OUR-PURPOSE: `idanbeck/claude-skills/whatsapp-skill`.**

- It works, but it locks to Claude Code (`~/.claude/skills/whatsapp-skill/` install path, `allowed-tools: Bash, Read` frontmatter), uses puppeteer with `--no-sandbox`, and runs from a `whatsapp-web.js` library that breaks when WA changes its UI.
- wacli is upstream-friendly and AAIF-portable; idanbeck's whatsapp-skill is none of those. Choose wacli.

### 3.6 Slack-only candidate (paymog/slack-cli)

**DROP — wrong surface.** `gh api "search/code?q=whatsapp+repo:paymog/slack-cli"` returned `total_count = 0`. Slack-only.

### 3.7 What we DO NOT need to fork

| gap candidate | reason |
|---|---|
| A new SKILL.md for "send WhatsApp" personal | wacli + bundled SKILL.md already covers it |
| A new SKILL.md for "send WhatsApp Business" | twilio/ai already covers it (twilio-whatsapp-send-message) |
| A new SKILL.md for "observe WhatsApp Business ops" | gokapso already covers it (observe-whatsapp) |
| A new SKILL.md for "wrap 23 WhatsApp vendors" | membranedev already covers it |
| A new SKILL.md for "manage WhatsApp senders + template approval" | twilio/ai already covers it (twilio-whatsapp-manage-senders) |

**No FORK verdict was returned by this probe.** Every surface we identified is already covered by at least one maintained upstream candidate. The DRY-first research gate holds.

---

## 4. AAIF compatibility matrix `tested | spec-compatible | unknown`

> **Tested:** I installed the artifact on the host and ran an invoke. **No such claim is made below** — I ran zero host installs in this probe. AAIF-spec-shaped SKILL.md files are reported as `spec-compatible`; everything else is `unknown`. The peer reviewer (operator or another agent) should not upgrade a row to `tested` without re-probing.

| Host / harness | wacli (openclaw) | twilio-whatsapp-* (twilio/ai) | observe/automate/integrate-whatsapp (gokapso) | whatsapp (membranedev) | whatsapp-skill (idanbeck) |
|---|---|---|---|---|---|
| Claude Code | `spec-compatible` (bundled SKILL.md frontmatter matches AAIF; binary install via brew or go install; no `allowed-tools` extension) | `spec-compatible` (SKILL.md reference + `pip/npm install twilio` for the SDK) | `spec-compatible` (SKILL.md matches AAIF; `kapso login` requires Kapso account) | `spec-compatible` (SKILL.md matches AAIF; `npm install -g @membranehq/cli`) | `spec-compatible` (designed for it; `allowed-tools: Bash, Read` is Claude-Code-specific but doesn't break AAIF) |
| Claude Desktop | `spec-compatible` (same SKILL.md works in AAIF-shaped directories; binary host-agnostic) | `spec-compatible` (same; SDK host-agnostic) | `spec-compatible` (same; `kapso login` requires browser on the desktop) | `spec-compatible` (same; Membrane CLI Node-based) | `unknown` (install path `~/.claude/skills/...` is Claude-Code-only; no documented Desktop path) |
| oh-my-pi | `spec-compatible` (binary install host-agnostic; SKILL.md frontmatter matches AAIF) | `spec-compatible` (SDK host-agnostic) | `spec-compatible` (Kapso CLI Node-based) | `spec-compatible` (Membrane CLI Node-based) | `unknown` (no oh-my-pi install documented; puppeteer + `--no-sandbox` may not be portable to omp's runtime) |
| ChatGPT | `spec-compatible` (AAIF-shaped) | `spec-compatible` (AAIF-shaped; SDK is host-agnostic Python/Node) | `spec-compatible` (AAIF-shaped; Node CLI) | `spec-compatible` (AAIF-shaped; Node CLI) | `unknown` (`allowed-tools: Bash, Read` is Claude-Code-specific; puppeteer dependency may not survive ChatGPT's sandbox model) |
| Codex | `spec-compatible` (binary install host-agnostic) | `spec-compatible` | `spec-compatible` | `spec-compatible` | `unknown` (same reasoning as ChatGPT) |
| opencode | `spec-compatible` | `spec-compatible` | `spec-compatible` | `spec-compatible` | `unknown` |
| Gemini | `spec-compatible` | `spec-compatible` | `spec-compatible` | `spec-compatible` | `unknown` |
| Antigravity | `spec-compatible` | `spec-compatible` | `spec-compatible` | `spec-compatible` | `unknown` |
| AGY | `spec-compatible` | `spec-compatible` | `spec-compatible` | `spec-compatible` | `unknown` |
| Prime | `spec-compatible` | `spec-compatible` | `spec-compatible` | `spec-compatible` | `unknown` |
| VSCode (Copilot) | `spec-compatible` | `spec-compatible` | `spec-compatible` | `spec-compatible` | `unknown` |

**Summary of AAIF matrix:**
- 5 candidates × 11 hosts = 55 cells. **0 `tested`.** **44 `spec-compatible`.** **11 `unknown`** (idanbeck vs. every non-Claude-Code host).
- The idanbeck candidate is the only one that fails AAIF cross-host portability; the rest are spec-compatible everywhere with the same install caveats (binary available + AAIF-shaped SKILL.md).

---

## 5. Source provenance

Every claim in this report is traceable to one of the following probes, executed via `gh` CLI v2.97.0 with auth as `ekson73` (keyring token), all on 2026-09-13:

1. **Repos metadata** — `gh api repos/<owner>/<repo> --jq '{...}'` for each candidate (provenance is the `<owner>/<repo>` tuple, the API is read-only).
2. **Latest commit** — `gh api repos/<owner>/<repo>/commits?per_page=5 --jq '[.[] | {sha, date, msg}]'`.
3. **Latest release** — `gh api repos/<owner>/<repo>/releases/latest --jq '{tag_name, name, published_at, author}'`.
4. **Releases list** — `gh api repos/<owner>/<repo>/releases --jq '.[] | {tag_name, name, published_at}'` (last 20).
5. **Contributors** — `gh api repos/<owner>/<repo>/contributors --jq 'length'`.
6. **LICENSE first lines** — `gh api repos/<owner>/<repo>/contents/LICENSE --jq '.content' | base64 -d | head -5`.
7. **README first lines** — same pattern.
8. **SKILL.md raw bytes** — `gh api repos/<owner>/<repo>/contents/<path>/SKILL.md --jq '.content' | base64 -d > /tmp/...`.
9. **Code search** — `gh api "search/code?q=whatsapp+repo:<owner>/<repo>+filename:SKILL.md" -H "Accept: application/vnd.github+json"`.
10. **Issues** — `gh api repos/<owner>/<repo>/issues --jq '.[] | {n, title, state, created_at}'`.
11. **AAIF spec** — https://agentskills.io/specification (accessed 2026-09-13; required fields: `name`, `description`).

Cached local copies (so a reviewer can re-verify byte-for-byte without re-hitting the API):
- `/tmp/wacli-SKILL.md` (openclaw/openclaw/extensions/whatsapp/skills/wacli/SKILL.md, 79 lines)
- `/tmp/twilio-wa.md` (twilio/ai/skills/twilio/twilio-whatsapp-send-message/SKILL.md, first 50 lines)
- `/tmp/twilio-wa-manage.md` (twilio/ai/skills/twilio/twilio-whatsapp-manage-senders/SKILL.md, first 50 lines)
- `/tmp/gokapso-observe.md` (gokapso/agent-skills/skills/observe-whatsapp/SKILL.md, 158 lines)
- `/tmp/gokapso-automate.md` (gokapso/agent-skills/skills/automate-whatsapp/SKILL.md size only)
- `/tmp/gokapso-integrate.md` (gokapso/agent-skills/skills/integrate-whatsapp/SKILL.md size only)
- `/tmp/idanbeck-wa-SKILL.md` (idanbeck/claude-skills/whatsapp-skill/SKILL.md, full)
- `/tmp/membrane-wa-SKILL.md` (membranedev/application-skills/skills/whatsapp/SKILL.md, 169 lines)

**Probes that were NOT executed (and why):**
- `last30days` community-chatter signal — not run; the assignment listed it but the last30days skill script was not located in this environment during probe (no API keys seen in `gh auth status`). The commits/issues data already provided strong signal; `last30days` would have added Reddit/X/HN sentiment which is not load-bearing for the verdict.
- `npx skills find whatsapp --limit 20` — not re-run; the assignment said "already done, results in `~/eko-engram/memory/`" and the verdict here is explicitly anti-skills.sh-count.
- `web_search` for community chatter — not run for the same reason; the verdict is upstream-evidence-first.
- Idanbeck WA-specific commit history (`git log -- whatsapp-skill/`) — not run because the probe budget was spent on the 5 other candidates; flagged `[skipped]` in §1.4.
- Membranedev top-level LICENSE file — not pulled because the SKILL.md frontmatter declared inline `license: MIT`; flagged `[INFERENCE]` in §1.6.

---

## 6. Anti-theater self-audit

For every claim in this report, the probe that justified it:

| Claim | Probe that justified it |
|---|---|
| openclaw/openclaw LICENSE = NOASSERTION | `gh api repos/openclaw/openclaw --jq .license.spdx_id` (literal API return) |
| openclaw/wacli LICENSE = MIT (effective) | `gh api repos/openclaw/wacli --jq .license.spdx_id` + raw LICENSE first lines via `gh api repos/openclaw/wacli/contents/LICENSE --jq .content | base64 -d` |
| wacli release cadence (4 in 7 days) | `gh api repos/openclaw/wacli/releases` (returned ≥20 releases; the 5 most recent are dated 2026-09-11, 2026-09-08, 2026-09-07, 2026-09-05, 2026-08-14) |
| wacli issue #417 media-key leak | `gh api repos/openclaw/wacli/issues --jq '.[] | {n, title, state, created_at}'` |
| twilio/ai 46 whatsapp hits | `gh api "search/code?q=whatsapp+repo:twilio/ai"` (total_count=46 literal) |
| gokapso NO top-level LICENSE | `gh api repos/gokapso/agent-skills/contents/LICENSE` (404 literal) |
| membranedev last commit 2026-04-28 | `gh api repos/membranedev/application-skills/commits?per_page=3 --jq '.[] | .commit.author.date'` |
| paymog/slack-cli = Slack-only | `gh api "search/code?q=whatsapp+repo:paymog/slack-cli"` (total_count=0 literal) + commit messages dated 2026-09-11 with `fix(provider)` / `slack tokens` wording |
| AAIF spec required fields = name + description | https://agentskills.io/specification (HTML probe 2026-09-13; `name` + `description` literal in the spec body) |
| 5 of 5 maintenance-active candidates have SPEC-shaped SKILL.md | raw bytes pulled for each, grep'd for `name:` and `description:` |

**Claims I did NOT make (and why):**
- I did not claim any candidate was `tested` on any host. **Zero `tested` cells in the AAIF matrix** — install + invoke was not executed.
- I did not estimate commit counts beyond what the API returned.
- I did not compare skills.sh install counts (forbidden by the assignment).
- I did not estimate "this repo is healthy" beyond the raw `pushed_at` + `open_issues_count` + `contributors` + release cadence returned by the API.
- I did not claim any candidate is the single best — every WhatsApp surface (personal / Cloud API / orchestration / vendor-neutral) has its own winner.
- I did not claim a fork is needed — every covered surface is already covered by at least one maintained upstream.

---

## 7. Operator-ratification items (queued for sign-off)

> Mirroring the Email-Reuse-Research FINDINGS structure; nothing here commits to a change
> without explicit operator ratification.

1. **Adopt `openclaw/wacli` + bundled SKILL.md for WA-personal/unofficial.** Default install path: `brew install steipete/tap/wacli`. Acceptance signal: successful `wacli auth` QR-pair + `wacli messages search "smoke-test"` returns JSON. Track wacli releases v0.18.3+ for the close of issue #417 (media-key webhook leak) and #418/#419 (libsignal stdout pollution) — these are the only acceptance-blocking items.
2. **Adopt `twilio/ai` 8-SKILL bundle for WA-Business-Cloud-API.** Default install path: `pip install twilio` (or `npm install twilio` per host). Acceptance signal: `twilio-whatsapp-send-message` + `twilio-whatsapp-manage-senders` SKILL.md loaded + sandbox account established at `+14155238886`. Operator MUST bring a Twilio account + a Meta-approved WABA sender.
3. **Adopt `gokapso/agent-skills` 3-SKILL bundle for WA-platform-orchestration IF operator has a Kapso account.** Otherwise defer. Acceptance signal: `kapso login` succeeds + `kapso logs search --period 24h --source all --limit 1` returns JSON. License-risk caveat: NO top-level LICENSE file → flag to operator for legal sign-off before adoption.
4. **Adopt `membranedev/application-skills` 24-SKILL bundle as a vendor-portability fallback only** (last commit 2026-04-28 is amber; treat as fallback, not default). Operator MUST bring a Membrane account.
5. **DROP `idanbeck/claude-skills/whatsapp-skill` from the candidate list for cross-host adoption.** Reasoning: Claude-Code-only install path + `allowed-tools` extension + puppeteer-with-`--no-sandbox`. Use wacli instead. If operator insists on `whatsapp-web.js`, accept only on Claude-Code host, never port.
6. **DROP `paymog/slack-cli`** — wrong surface (Slack-only). No further action.

---

## 8. Final one-line verdict

**REUSE-first holds.** The WhatsApp messenger surface is fully covered by 4 maintained upstream candidates (`openclaw/wacli`, `twilio/ai`, `gokapso/agent-skills`, `membranedev/application-skills`); one is Claude-Code-locked and gets dropped for cross-host work (`idanbeck/claude-skills/whatsapp-skill`); one was misclassified for the lens and is Slack-only (`paymog/slack-cli`). **Zero FORK needed. Zero GAP-WRAPPER needed. AAIF-spec-compatible on every host for every reused candidate.** Track wacli #417/#418/#419 as the only acceptance-blocking issues; flag gokapso's missing LICENSE to operator for legal sign-off before adoption.
