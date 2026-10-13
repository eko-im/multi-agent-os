# ADR-019: Pharos open choice and confidence boundary

- **Status:** Proposed; adoption/authority policy remains pending human selection and ratification
- **Date:** 2026-10-10
- **Public discussion:** [GitHub issue #486](https://github.com/ekson73/multi-agent-os/issues/486)
- **Deciders:** Pending operator decision; research synthesis is not an approval
- **Scope:** MAOS Pharos attention-block extension only. No changes to other repositories, provider settings, model installations, or the separate user-owned Pharos PR. Public tracking is recorded in issue #486 above; this ADR does not authorize model adoption or trials.
- **Evidence:** [Decision-intake dossier](../adoption/decision-intake-2026-10-10.md); existing patterns in ADR-005 (dogfood-cycle ledger) and ADR-018 (measured-denominator discipline).

## Context

A final grouped human decision block already exists in the Pharos operator-attention-block work on PR #463. At that PR base, the linter did not require a free-text alternative attached to a decision choice; this isolated follow-up branch adds that requirement but is not merged or deployed. The intended change lets a person propose another option without conflating that response with choosing an existing option, declaring all options unsuitable, requesting more context, or granting authorization.

This ADR is deliberately narrower than model adoption. Research compared hosted Jev, local Laya, BERT-family encoders and open alternatives, but no candidate was installed, called, or benchmarked on an operator workload. A model score cannot substitute for consent, permissions, policy, or task-specific validation.

The evidence also rules out treating the displayed Jev Choice confidence as an empirical probability of correctness. Its documented transform is c = (pmax − 1/n) / (1 − 1/n), where pmax is the largest output probability and n is the number of choices. It is distribution-derived, not a measured P(correct). With two options c=.90 corresponds to pmax=.95; with four it corresponds to pmax=.925. Neither mapping establishes correctness, calibrated selective risk, or appropriate coverage. Score and Noul have different confidence semantics. A high score, successful schema parse, or recommendation does not prove a safe or authorized action.

Laya evidence reinforces this boundary: its publisher card reports a confident Khmer failure and an action-probability head with AUROC .30 on 396 labeled decisions. Published cross-model benchmark tables have mismatched prompts, labels, samples, model states, and evidence ancestry. No controlled result establishes fitness for a selected workload.

## Decision

1. **Extend Pharos only.** Add an item-bound open alternative to decision-choice presentation and validation. Reuse the existing Pharos block/linter and existing audit/policy mechanisms; do not create a second approval engine, decision journal, or parallel attention block.
2. **Keep response semantics separate.** The existing choices remain distinguishable: select a proposed option; propose another option in that decision item's response; state that none fit; or request missing context. The open alternative is a proposal, not acceptance or approval. Authorization questions remain separately scoped and cannot be widened by free text.
3. **Make recommendations non-authorizing.** Neither model output, score, confidence, structured schema validity, nor a human-readable recommendation grants permission to install, execute, publish, disclose data, spend, change access, or perform a consequential action. Keep explicit human/policy authorization where required, regardless of score.
4. **No universal 90% threshold.** Do not use a global confidence cutoff as a correctness guarantee, authorization rule, or automation target. Score confidence, empirical correctness, selective error risk, and coverage are different measurements. A task-specific threshold may be considered only after workload selection, independently measured calibration, predeclared error/coverage bounds, and explicit human authorization.
5. **Shadow-first evaluation only after scope selection.** No live routing or automatic action follows from this ADR. Before any model trial, the user selects one reversible low-risk workload, acceptable error-cost/coverage limits, representative human-reviewed labels, permitted data and runtime, candidate versions, and the applicable install/egress/cost approvals. Evaluation separates training, calibration/threshold selection, and untouched test data; tests no-good-option, OOD, language, subgroup, long/truncated input, adversarial/negation, option-order, and schema changes. Recommendations begin in shadow mode.
6. **Fail closed to review.** Missing confidence/distribution, malformed output, timeout, unsupported language, invalid schema, detected drift, or an unvalidated action path yields abstention/human review, not a fallback permission. “Other” is not presumed to detect OOD.
7. **No adoption or promotion now.** Keep deterministic code and current human process as baseline. Jev is only a possible pinned hosted comparator; Laya and open encoders are evaluation candidates. Current-session dogfood was exercised but is not ratified/completed, is not a completed dogfood cycle, and contributes no cycle count or promotion eligibility.

## Alternatives rejected

- **Confidence >= 90% authorizes an action.** Rejected because a distribution transform or score threshold is not an empirical correctness rate, cannot encode consequences/consent, and may be overconfident under subgroup or distribution shift. Consequence: recommendations require review until a scoped, authorized evaluation supports a task-specific selective policy.
- **One universal 90% automation/coverage gate.** Rejected because score, correctness, and coverage are non-equivalent; risk tolerance depends on the task and error costs. Consequence: no global gate is recorded; each future workload must define and test its own error/coverage bounds before trial.
- **Adopt Jev, Laya, or a BERT-family model from published tables.** Rejected because no target workload was benchmarked, model/provider versions and protocols differ, and sources share ancestry. Laya's own card reports confident failures; Jev's hosted data boundary requires separate review; an encoder requires task-specific training/calibration. Consequence: retain baseline and defer all candidate execution.
- **Use Laya action probability or typed schema as an authorization/fallback signal.** Rejected because card evidence reports poor action-head discrimination and type correctness does not establish decision correctness. Consequence: action probability is not authority; malformed or unsupported cases go to abstention/review.
- **Create a new gate, model router, ledger, or parallel product.** Rejected because Pharos already owns the attention-block/linter surface and MAOS has existing policy/audit mechanisms. Consequence: make the smallest extension in Pharos and preserve those boundaries; do not infer that the separate PR is merged or active at root.
- **Start with no-change and omit the open alternative.** Rejected for the limited presentation requirement: people need a way to propose a missing option without pretending an existing choice fits. Consequence: add the open response only as an item-bound proposal; it does not approve or execute that proposal.
- **Choose a model or trial before workload/data approvals.** Rejected because the evidence cannot determine local fit, privacy, egress, costs, or error tolerance without a selected task. Consequence: shadow-first remains a future conditional path, not an active experiment.

## Consequences

**Positive:** preserves a single existing decision surface; makes missing options visible; separates proposal from selection and authorization; blocks confidence theater; leaves the baseline intact; makes future model evaluation falsifiable and workload-specific.

**Negative / trade-offs:** users may see more abstentions and human review; selecting a workload and collecting reviewed labels delays any model comparison; shadow recommendations provide no immediate automation benefit. These are accepted over creating an unmeasured confidence gate.

**Open questions:** selected workload and error costs; acceptable target coverage; model/data/runtime permissions; calibration design and independent reviewer; and whether a later explicitly authorized trial is worthwhile. Public issue #486 tracks this work; it does not constitute model adoption, trial authorization, or policy ratification.

## Reconsideration criteria

Reopen this decision only when a user has selected a reversible workload and authorized its data/runtime/cost boundary; a protocol has distinct training, calibration, and untouched evaluation sets; an open encoder/rules baseline and any authorized candidates are compared on the same task; task-specific risk/coverage and subgroup results meet predeclared bounds; abstention and rollback are demonstrated; and consequential actions still retain independent authorization. A score threshold alone never satisfies these conditions.

## References

- Adoption dossier: [Decision intake — 2026-10-10](../adoption/decision-intake-2026-10-10.md)
- Existing dogfood counting and ratification semantics: ADR-005
- Existing measurement/anti-theater rationale: ADR-018
- Existing Pharos contract, linter, and tests in this worktree: skills/operator-attention-block and bin/attention-block-lint
- Pharos feature PR remains separately user-owned and open; this ADR neither modifies nor declares it accepted.
