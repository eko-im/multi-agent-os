# HITL scorecard — contract (SSOT)

> **Version**: 1.0.0 (2026-11-24) · **Canonical source** of the scorecard view and
> selection panel of the HITL digest. The personal spec `hitl-digest-spec` §8 (v2.7.0)
> keeps a summary and points here. Entry point: the `/hitl-digest` command
> ([`commands/hitl-digest.md`](../../../commands/hitl-digest.md)); implementation:
> [`bin/hitl-scorecard.py`](../bin/hitl-scorecard.py); skill:
> [`SKILL.md`](../SKILL.md). The digest grammar (code, `Responda:`, answer rules, caps,
> parking) is `hitl-digest-spec` §§0–7; this file changes none of it.

The operator runs dozens of sessions at once, so each card is a short executive
briefing that leads with the answer (Minto pyramid; BLUF).

## 1. Card anatomy

One card per decision. Full layout, in this order:

1. title: `<n> · <urgency> [· 👤 SÓ VOCÊ] — <subject in at most 6 words>`;
2. `origem: <harness> · <repo> · <s8>`, always present; a merged duplicate adds
   `(+N sessões)`;
3. `decisão: <what is asked, one line>`;
4. `BLUF: ✅ recomendo A porque <rationale>`, only with an evidence pointer;
   otherwise `BLUF: sem recomendação: falta ponteiro de evidência`;
5. `contexto: <one line>`;
6. one line per option, letter first:
   `A ✅ <label> → <effect> · ↩️ REVERSÍVEL|🚪 SEM VOLTA · <confidence> · <pointer>`.
   No card line starts with a header glyph of the attention contract;
7. badges: `⌛ sem resposta: <cost of delay>`, `⏱ <time to decide>`, and `☑ VÁRIAS` on a
   multi-select card.

**Reversibility belongs to the option, not to the card** (one-way or two-way door).
Each option carries `reversible` and `effect` (what happens if it is chosen);
`cost_of_delay` stays on the card. A card-level `reversible` (legacy) is the default of
every option that does not set its own.

The **compact** layout goes in a reply; the **full** layout goes to a file or into the
panel. Both keep the digest header, count, `Responda:`, hint and footer lines, with every
line within 80 columns. A compact card has at most 5 lines, answer first:

1. L1 `<n> · <urgency> [· 👤 SÓ VOCÊ] — <title>`;
2. L2 `A ✅ <action> <↩️|🚪> — porque <rationale> (<confidence> · <pointer>)`; without a
   pointer, `sem recomendação: falta ponteiro de evidência`;
3. L3 the other options, each with its door glyph: `B <action> 🚪` (and `C`, `D`);
4. L4 `⌛ <cost of not deciding> · <legend>`, the legend naming each door present on the
   card's options with icon and CAPS word (`🚪 SEM VOLTA · ↩️ REVERSÍVEL`);
5. L5 the origin `<harness> · <repo> · <s8>`, only the fields that differ from the
   footer line. When the card's origin differs from the footer it is never omitted:
   it is what tells the sessions apart.

L2 starts with the letter, `A ✅`, not with `✅`: `sinal-check` reads a body line that
starts with `✅` (after indentation) as a misplaced header line and refuses the reply.

The six fixed lines (header, count, `Responda:`, hint, footer) leave 9 of the 15 body
lines of the attention contract for cards. Cards keep 5 lines while the body fits in 15;
otherwise they drop to 3 lines from the lowest-priority card up: L1, L2 and an L3 with
the other options, `⌛`, the legend and the differing origin.

Nothing is cut with `…`. A field that does not fit its line wraps, and the lint warns so
it is shortened **at the source**: `title` (L1), label + `rationale` + pointer (L2),
`cost_of_delay` (L4), an option `effect` over 60 columns, or a card that cannot fit in 3
lines. `rationale` is required whenever there is a recommendation.

## 2. Color

Every signal keeps its icon and CAPITAL word; color only adds to them. ⏫ ALTA is red,
🔼 MÉDIA amber, 🔽 BAIXA green, 👤 SÓ VOCÊ magenta, 🚪 SEM VOLTA red, ↩️ REVERSÍVEL green,
✅ green and ⌛ amber. ANSI codes are used only on a terminal (`--format ansi`), never in
chat or markdown. When `NO_COLOR` is set, no ANSI is emitted.

## 3. Panel: three surfaces, one answer surface per decision

| Consumer and harness | Surface | Mapping |
|---|---|---|
| `human-live`, Claude Code | `AskUserQuestion` | one card per question; header `<n> <URGÊNCIA>[ 👤]`, at most 12 characters; the A/B/C labels are the options (2–4), recommended first with `(recomendado)`; each option description carries its effect and its door (`Reversível.`/`Sem volta.`); the question text carries ask, context, origin and cost; the digest keeps only the `aberta no AskUserQuestion` record line |
| `human-live`, OMP | `ask` (one HTML form) | `<fieldset>`/`<legend>` per card, briefing in a `<table>`; radio for single choice, checkbox for multi; each option shows effect, door and pointer; nothing `checked`, `selected` or prefilled; an unchecked `confirm` box |
| `human-deferred`, or no tool | text digest | the durable fallback; a `machine` consumer gets no text |

Measured limits:

- **Claude Code 2.1.331 binary.**
  - `questions` takes at least 1 and at most 4 items; the schema calls the bounds
    "hard schema constraints".
  - `options` takes 2 to 4 items. `header` is "max 12 chars" (`hPl=12`). "Other" is
    added automatically.
  - The result has `answers` (question text → label; a multi-select answer is
    comma-separated) and `annotations[q].unanswered` (`skipped`, `replied_in_chat` or
    `dismissed`). `afkTimeoutMs` is set when the dialog resolved itself while the person
    was idle.
- **OMP 18.16.0 `ask`**: a single HTML form, which "submits its current values on
  timeout" (`ask.timeout`).

## 4. No preselection; timeout is pending

No surface ever pre-selects an option, not even a reversible one. The recommendation is
only visual: it comes first, with `✅` and `(recomendado)`. The following are pending,
never consent, and the card returns in the next digest:

- a timeout, or an idle auto-resolve (`afkTimeoutMs`);
- a cancel, or an `unanswered` annotation;
- free text or "Other" (the agent reads it but executes nothing);
- an OMP form sent without its `confirm` box, or with an empty field.

## 5. Single or multiple choice

- Single choice (radio) is the default: use it whenever the options exclude each other.
- Multiple choice (`multiSelect: true`, checkbox) is only for picks of the same kind that
  do not exclude each other, for example which of these items to archive.
- At most 4 options per question; split the question when there are more.
- The recommendation may be a set. The text answer is `n:A+C`. No label of a multi card
  contains a comma, because the tool returns the picks comma-separated.
- A one-way-door option never goes in a multi card.

## 6. Aggregating many sessions

The input is `NEEDS-OPERATOR` lines and decision files from N sessions, each with its
origin.

- **Dedupe** by (`origin.repo`, `id`) when the decision carries an explicit `id`;
  otherwise, the legacy path for bare `NEEDS-OPERATOR` lines, by (`origin.repo`,
  normalized ask). The session stands in for the repo only when the repo is unknown.
  Two distinct ids with the same ask in one repo are two decisions; the same id (or, in
  the legacy path, the same ask) in two repos is two decisions; from two sessions of one
  repo it is one card with `(+N sessões)`. On a merge the origins are kept, the highest
  urgency wins, `👤` is kept if any copy has it, and `unblocks` is summed.
- **2 to 4 real options.** A decision with one option is not a decision: it is refused
  (listed as `rejected`), never padded with an invented option.
- **Order**: ⏫+👤, ⏫, 👤, then parked items in their third digest, then the urgency
  class (the cost-of-delay class), then how much the decision unblocks.
- **Cap**: per `hitl-digest-spec` §4; the rest is parked or goes on the `⏭` line.
- A bare `NEEDS-OPERATOR` line has no pointer, so its card has no `✅` until evidence is
  attached.

## 7. Attention contract

The `🔴 PRECISA DE VOCÊ` line summarizes the ask and the scorecard is the last block.
With at most 3 compact cards, the body stays within 15 lines and passes `sinal-check`.

## 8. Lint

`hitl-scorecard.py lint` **fails** when:

- a line is longer than 80 columns;
- there are more than 4 cards, or a card has fewer than 2 or more than 4 real options;
- a recommendation has no `rationale`;
- the recommended option is 🚪 SEM VOLTA (own or inherited `reversible: false`) and its
  confidence is not `alta`: make the recommendation stronger or leave the card
  `sem recomendação`;
- labels repeat, or a recommendation names something that is not an option;
- the origin, context, ask or cost is missing;
- the `Responda:` line offers `-`;
- an `AskUserQuestion` bound is broken;
- the OMP form has a preselected or prefilled field;
- the compact body is longer than 15 lines.

It **warns** when a recommendation has no pointer, a title has more than 6 words, an
option has no `reversible` (own or card default) or no `effect`, or a field is over its
line budget (§1).

## 9. Schema `hitl-scorecard/v1`

Document `{"schema", "harness", "repo", "decisions": [...]}`. Each decision: `id`,
`title`, `origin{harness,repo,session}`, `context`, `ask`, `urgency` (alta|media|baixa),
`owner_only`, `cost_of_delay`, `time_to_decide`, `multi`, `unblocks`, `recommended`
(label, letter or list for multi), `rationale`, `options[]`, and the legacy card-level
`reversible` (default of every option). Each option: `label`, `effect`, `reversible`,
`confidence`, `evidence`.

`rationale`: one short line with the reason for the recommendation, rendered after
`porque` in L2 and in the full layout's `BLUF:`. Required when `recommended` is set.

## 10. Canonical example

**Synthetic fixtures only**: repo `org/exemplo`, a fictitious session and pointers marked
`exemplo:`. No data from a real machine. The three cards cover a reversible
recommendation (1), a one-way option that is **not** recommended next to a reversible
recommendation (2), and a card with no recommendation because there is no evidence
pointer (3). Compact layout, as rendered; the `🔴` line goes above it:

```
══ 🟠 HITL DIGEST · K261124-2135-exemplo1 (18:35 -03) ══
3 + 0 estac.
Responda: K261124-2135-exemplo1 1:A 2:A 3:A
(1, 2 e 3 exigem letra · omitido = pendente)
1 · ⏫ ALTA · 👤 SÓ VOCÊ — Janela do deploy exemplo
    A ✅ Amanhã 9h ↩️ — porque o runbook pede janela (alta · exemplo:runbook:12)
    B Agora ↩️
    ⌛ o release segue parado · ↩️ REVERSÍVEL
2 · 🔼 MÉDIA · 👤 SÓ VOCÊ — Destino da tabela legado_v1
    A ✅ Arquivar ↩️ — porque guarda os dados (média · exemplo:inventario:3)
    B Apagar 🚪 · ⌛ custo de disco segue · 🚪 SEM VOLTA · ↩️ REVERSÍVEL
3 · 🔽 BAIXA — Regra nova de lint
    sem recomendação: falta ponteiro de evidência
    A Adotar ↩️ · B Manter ↩️ · ⌛ só atrito · ↩️ REVERSÍVEL · org/exemplo-lib
harness: OMP · repo: org/exemplo · sessão: exemplo1
```

Card 3 has no recommendation, so `-` is not accepted there either: the hint asks for a
letter on all three. Card 2 recommends the reversible option; recommending `Apagar`
(🚪, confidence `baixa`) would be a lint error.

## Sources (non-normative)

- the answer-first order: Minto pyramid and BLUF (US Army Regulation 25-50);
- one-way and two-way doors: Amazon's 2015 letter to shareholders
  (sec.gov, d168744dex991.htm);
- cost of delay: Reinertsen, *The Principles of Product Development Flow*;
- `NO_COLOR`: no-color.org.
