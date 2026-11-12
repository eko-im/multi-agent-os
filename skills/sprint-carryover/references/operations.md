# Sprint carryover: operational knowledge base

Author: Codex /root · Updated: 2026-10-16 · Applies to skill v0.1.1.

Read with [SKILL.md](../SKILL.md), which owns the invocation and output contract. This guide
adds operational checks and an anonymous incident lesson; it is not a new tracker adapter or an
instruction to run a migration. Examples use fictional project key `DEMO`.

## Best practices before a write

1. Resolve the actual site, project/board, owner union and sprint IDs. Discover the live capability
   and its input schema; neither an endpoint's name nor a successful call proves its semantics.
   Do not copy a `customfield_*` ID from another site. Verify the field mapping in the current site.
2. Keep the standard **past/closed → active** predicate. Confirm destination state directly; dates,
   names and calendar boundaries are insufficient. An explicit **active → future** request is a
   distinct variation: document that deviation, target state and exact reviewed set. It does not
   change the default or add a new CLI flag. If the surface cannot support it safely, defer.
3. Dry-run the full candidate set, paginate and positively control negative queries. Show the
   required four-column table. Capture the approved scope and before-state as audit evidence:
   sprint membership/history, status, assignee, parent/subtask relationships and timestamps.
   This record bounds the apply; it is not a persistent queue or replacement for fresh reads.
4. Inspect inherited effects of moving a parent. Include completed subtasks in impact analysis,
   while excluding them from the actionable move set. If a parent move would affect children
   outside the reviewed scope, stop for scope resolution; do not quietly include them.
5. Use only a detected operation that preserves status, assignee and closed-sprint history. Do not
   overwrite an entire Sprint array based on an assumed field shape. A sprint move does not authorize
   a workflow transition, reassignment or change to automation rules.
6. Revalidate the full predicate immediately before each write, including destination state. GO
   does not freeze tracker state. A changed owner, status, labels, component or sprint is a reported
   skip, not permission to widen the filters.

## Verify persistence, not just acceptance

For each attempted move, perform a direct issue read and inspect changelog entries after the write.
Record the observed sprint, status, assignee, closed-sprint history and affected parent/child state.
Then repeat the relevant reads after a **delayed observation window**, before moving the next item.

Choose and document the window from known site automation behavior or observed latency plus a
margin. Record start/end timestamps, read times and the rationale. There is no universal safe
number of seconds. If an adequate window cannot be established, report limited verification and
hold the remaining batch. A finite window establishes only persistence during that window.

Use these distinctions in prose and existing output text fields:

| Observation | Meaning | Reporting/action |
|---|---|---|
| Accepted | API acknowledged the request | Verify; not yet a successful migration |
| Observed persistent | Direct reads across the window and preservation checks passed | Include in final migration table and `migrated[]`, with window limits disclosed |
| Reverted | A subsequent read/changelog shows removal or replacement | Stop the batch immediately; attempted item in `failed[]` with evidence |
| Blocked | No safe write or adequate verification is possible | If unattempted, `skipped[]` with reason; if attempted but unverified, `failed[]` |

These are **not output enums**. Keep the skill's existing JSON envelope and exit-code contract.
`MIGRATED` with `dry_run:false` means an apply was attempted, including an all-failed apply. It does
not override failures. A timeout after submission is not a dry run. Put uncertainty and observation
times in `error`/`reason` and `_agent_feedback`, not in invented fields or verdicts. Do not silently
omit items left unattempted after a batch stop. Correct an earlier success classification if a
later read before the final report shows reversal.

## Stop and recovery discipline

On the first reversal, unresolved write outcome, unavailable verification or unexpected collateral
change, stop remaining writes. Read and diagnose; do not repeat the write or alternate move/restore
calls until one sticks. Compensation is another write and needs a reviewed recovery scope. A
compensation response also needs direct and delayed verification.

Restoring the original set after reversal must not silently broaden owner/status/sprint filters or
pull in newly discovered items. Compare the original authorized set with fresh state and show any
differences. Treat a changed recovery scope as a new decision. Do not roll completed subtasks into
an actionable set merely because a parent inherited a sprint change.

## Anonymous incident lesson

In an operator-observed case, the explicit request was **active → future**, unlike the skill's
standard past/closed → active carryover. The observed `transitionJiraIssue` invocation supplied
only `cloudId`, `issueIdOrKey` and `sprintId`; it did **not** supply `transitionId`, status or fields.
This describes that invocation, not a universal API recommendation. The skill does not hardcode
an endpoint, and the tool name alone does not prove a workflow transition occurred.

The API returned success. Changelog then showed an **Automation** actor removing Sprint seconds
later. A compensating move back to the active sprint was also subsequently removed. These facts
establish that acceptance did not ensure persistence and that compensation was not a working fix.

Initially, the cause was unknown: empty metadata and the Automation actor did not identify a rule
or its conditions. The future destination suggested a temporal hypothesis, and a canary after
actual sprint activation was proposed but not run. This is the investigation history, **not the
current correction**. Planned dates alone never established activation or causation.

Later, authorized audit linked successful rule executions to the affected items, and the current
configuration showed a rule triggered by Sprint changes, conditioned on the event initiator,
whose action cleared Sprint. No sprint-state condition was observed. This evidence **supersedes
the temporal hypothesis in this incident**: waiting for activation alone does not address the
observed condition. Current configuration is not an immutable historical rule version; keep that
limit explicit when correlating audit, changelog and configuration.

Changing the endpoint while retaining the same initiator and triggering event does not resolve
an initiator-based rule. Do not switch accounts, impersonate an exempt user, alternate endpoints
or retry to defeat the policy. Stop writes and escalate an authorized policy review to the rule
owner. The diagnosis is supported; a corrective policy decision and a validated solution remain
pending. Do not disable automation or alter security to test a theory.

A canary is only a **proposed experiment** after an authorized, relevant condition change or
correction has been established. Before proposing it, document why the evidence predicts a
different result, bound the authorized target and parent/child effects, define the observation
window and stop condition, and preserve before-state. In this incident, sprint activation alone
does not meet that prerequisite. Do not retry simply because time passed or an API path changed.

No tenant names, issue keys, account identifiers, site URLs, custom field IDs or raw audit payloads
from the incident belong in public/shared documentation. Keep detailed evidence only in an
approved destination; this repository contains the anonymous lesson.

## FAQ

**Does an HTTP/API success mean the item migrated?**
No. It proves acceptance at that instant. Direct reads and subsequent changelog may reveal an
asynchronous reversal. Report only the persistence observed within the documented window.

**Can I retry when a search query still returns the old sprint?**
Read the issue directly first. JQL/search lag can produce stale membership. If the direct read is
already correct, do not issue another move. If direct state was reversed, stop and diagnose.

**Is `transitionJiraIssue` forbidden or required?**
Neither follows from this incident. Discover the available schema and supported behavior in the
current environment. A call containing only sprint arguments must not be described as changing
workflow status without evidence. The skill remains capability-based and endpoint-neutral.

**Can `--active-sprint` name a future sprint?**
Not under the standard predicate: it must resolve to an active sprint. Active → future requires an
explicitly reviewed variation; a title or planned date does not waive state validation.

**Which automation rule caused the removal?**
Correlate authorized audit executions with affected items, timestamps and changelog, then inspect
the trigger, conditions and actions. An Automation actor and empty metadata alone are insufficient.
Distinguish current configuration from the version used by past executions. If audit is inaccessible,
report the access limitation and preserve the evidence.

**Will activating the sprint or choosing a different endpoint prevent an initiator-based rule?**
Neither changes the relevant initiator condition for the same triggering event. If audit and
configuration establish that condition, retire a timing-only hypothesis as superseded; preserve
it as investigation history, not a current fix. Escalate authorized review of the policy.

**Can I use another account or retry until the write survives?**
No. An exempt identity is not permission to act as that user. Do not switch accounts, impersonate,
alternate endpoints or repeat writes to evade the rule. Keep the batch stopped until the responsible
owner resolves the policy and a separately authorized, evidence-based next step is defined.

**Should the skill automatically restore the original sprint?**
No. Restoration may be removed by the same asynchronous behavior. Propose a bounded recovery only
after reconciling state and authorization; verify it separately. Never enter a compensation loop.

**Why inspect completed subtasks if the query excludes Done?**
A parent move may have inherited effects. They belong in the impact review and after-checks, not
in the actionable candidate set. Report indirect effects separately from intended moves.

## Troubleshooting

| Symptom | Read-only diagnosis | Safe next step |
|---|---|---|
| Request times out; outcome unknown | Direct issue read and changelog for the request window; distinguish no evidence from proof of no write | Hold the batch; record attempted/unverified. Do not retry automatically |
| JQL/search still shows old membership | Compare direct read with search and timestamps | Trust verified direct state for this decision; no duplicate write to cure index lag |
| API success, then Sprint disappears | Correlate immediate/delayed reads and changelog actor/time | First reversal stops the batch; preserve evidence and obtain automation audit |
| Compensating move also disappears | Read compensation's changelog and current issue state | Report failed compensation; stop move/restore loops |
| Destination is future or ambiguous | Read board/sprint state and resolve exact ID, not only name/dates | Standard apply cannot proceed; reconcile explicit variation or defer |
| Sprint field differs across sites | Discover current field ID/schema and supported move capability | Use site-local mapping; never copy another tenant's custom field ID |
| Parent move affects unexpected children | Compare parent and all relevant children, including completed subtasks | Stop, report blast radius and resolve scope before further writes |
| Audit inaccessible or metadata empty | Record exactly what history is visible and missing | Do not guess a rule ID; request authorized audit evidence through the operator |
| Audit identifies an initiator-based rule clearing Sprint | Correlate executions and changelog; inspect initiator condition and action, distinguishing current from historical configuration | Stop writes and escalate authorized policy review; no alternate account, endpoint or retry to defeat the rule |
| Earlier hypothesis blamed future sprint timing | Compare the hypothesis with the evidenced rule conditions | Mark timing-only hypothesis superseded when conditions are initiator-based; preserve investigation history, not a false fix |
| Rule/destination state allegedly changed | Read actual condition, configuration/version and state; assess relevance to the diagnosed cause | Only propose a separately authorized canary after a relevant change; activation alone does not address an initiator condition |
| Re-run discovers a wider recovery set | Compare fresh candidates to original approved scope | Report differences; no automatic scope expansion |

## Acceptance evidence

An applied batch is complete only when the authorized scope is accounted for, each reported move
has persistence observations, status/assignee/closed-sprint history are preserved, parent/child
checks match the reviewed impact, and every failure/skip is explicit. Partial results remain
partial. Document missing access, observation limits and unresolved cause without declaring Green.

## Review scenarios

These are documentary review cases, not claims of live tracker test execution.

| Scenario | Required behavior |
|---|---|
| Default dry-run / noninteractive JSON | Zero writes; exact table/envelope; proposed set only |
| GO followed by changed owner or terminal status | Per-item recheck skips and reports; no write |
| Accepted write, direct + delayed reads preserve state | Report verified move and observation window |
| Accepted write, Automation removes Sprint later | Failed item; stop batch; remainder skipped; no automatic retry |
| Timeout or history unavailable after attempted write | Unverified failure; `dry_run:false`; no invented verdict |
| Parent has completed child outside reviewed effects | Resolve scope before write; never silently move the child |
| Compensation also reverted | Report it, preserve current state, stop further compensation |
| Requested future destination / planned date crossed | Separate variation; validate actual state; no automatic activation claim |
| New run after reversal widens filters | Compare authorized scope; hold differences rather than expand |
| Audit identifies an initiator-based rule after a timing hypothesis | Preserve historical hypothesis as superseded; no activation-only fix; distinguish evidenced diagnosis from pending policy decision |
| Alternate account, endpoint or retry proposed to evade a rule | Reject circumvention; keep writes stopped and escalate authorized policy review |
| A proposed canary has not run | Label proposed/unvalidated; do not claim a solution or discard an already evidenced diagnosis |
