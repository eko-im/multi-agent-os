# on-call-shift — backlog adoption

Adoption runs only when the shift was opened without a backlog, or every item of the given
backlog has been accepted (`mark_backlog_exhausted`). When an explicitly assigned backlog is
finished, reconcile again; do not fabricate tickets to stay busy.

## 1. Tracker connectors

Read every connector the principal already authorized: issue trackers (for example a
Jira-like, a Linear-like and a forge issue tracker) and code-review queues (pull or merge
requests). None is a default and none is required. Discovery composes `work-compass` or
`work-drain` when present; otherwise the host's own connectors. Detect capability first.

Each connector reports:

| Field | Meaning |
|---|---|
| `connector`, `kind` | name and `issue-tracker` or `code-review` |
| `identity`, `scope` | who authenticated and what it can see |
| `status` | `ok` · `empty` · `denied` · `unavailable` · `partial` |
| `observed_at` | freshness |
| `error` | the error, when there is one; page or limit notes belong here too |

Only `empty` means empty. `denied`, `unavailable` and `partial` mean "not read", and the shift
waits on them with a reason instead of treating the queue as done.

## 2. Normalization

Give each item an `intent_key` (the work it stands for). Items with the same key, and the
references they link (an issue and the pull request that closes it, the same task mirrored in
two trackers), merge into **one** work item with all references kept. An issue and its pull
request are never two deliveries. When two sources name different owners (`assignee` or `in_flight_by`), both
claims are kept in `conflicts` and the item is not adoptable until they are reconciled. A
gate blocks until its effective state is `granted`; the decider's recorded gate wins over the
connector's copy. Reuse the cross-tracker key pattern of
`spec-backlog-ticket-reconciler`.

## 3. Ownership and RACI/DARCI

| Role | Meaning |
|---|---|
| `driver` | coordinates |
| `responsible` | does the work |
| `approver` | accepts the result (the authority) |
| `consulted` | asked before deciding |
| `informed` | told after |

A role the sources do not name stays `unknown`; never invent an authority. Before adopting,
read the assignee, the in-flight state, open pull requests and active leases. If someone else
holds the intent, do not adopt it: offer to remove the impediment and leave authorship with
them.

## 4. Selection

1. Drop items already adopted, owned or in flight by others, or behind a human gate (record
   each with its reason).
2. Rank the rest by GUT (gravity × urgency × tendency) and Eisenhower; break ties by key.
3. Adopt **one**, with a named recipient, a verifiable outcome and a budget share.
4. If nothing is eligible: wait for a real event with a deadline, a maximum cost and an
   escalation path. Name unreadable connectors as the reason when there are any.

Adoption is idempotent: adopting the same intent key twice changes nothing, so a replay after
a restart adds no second adoption.

## 5. Method notes
- OODA records each decision, the transition and its effect.
- 5 Whys and Ishikawa separate competing causes and name the test that tells them apart.
- 5W2H contracts an action that needs coordination with others.
