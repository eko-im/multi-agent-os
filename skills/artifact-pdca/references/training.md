# Training note — artifact-pdca 1.0.1 (dogfood candidate)

**What changed:** 1.0.0 treated the descriptive 95% coverage target as a hard threshold. A pre-dogfood editorial correction in 1.0.1 replaced that veto with two separate questions: did the critic account for every material item, and did the cycle require a material correction? This records the training decision, not an observed performance gain or an independent acceptance.

| Portable edition | SHA-256 of `SKILL.md` |
|---|---|
| 1.0.0 (predecessor, not shipped here) | `56bb7ebc1acbb061959a7846e18202307f19ece6c59c8676d479be526376e79f` |
| 1.0.1 (candidate) | `9c8dc8c6440003c3bb549d38108c76a60517b8036bfe35590f5e97d80e46b4b6` |

**Synthetic contrasts for an independent evaluator.** These are disclosed examples, not a blind test set and not execution receipts. Start with two clean cycles. The first two rows assume a distinct new delivery, all required receipts and independent review; change only the stated evidence.

| Input | Expected observable decision |
|---|---|
| 94/100 items verified; the critic accounts for the six immaterial omissions, finds no material concern and no material correction was needed. | Record 94/100, credit the third clean cycle and stop. The target was missed; the decision criterion was met. |
| 99/100 items verified; a material cost claim remains uncertain. | Record 99/100; reset the clean streak to zero and hold for discriminating evidence. |
| The delivered bytes and event ID have already been counted. | Do not advance either counter and do not generate another copy. |
| A creation acknowledgement was lost and there is no unambiguous match. | Preserve the reservation, record the missing evidence and send zero new requests. |
| A subtitle contradicts the source, but the media cannot be heard or checked. | Preserve both versions; do not change the source or claim the speaker was wrong. Hold if material. |

To evaluate the tool rather than these examples, an auditor distinct from the author keeps one new contrast out of the executor's prompt and compares observed actions with and without the skill. Record the exact version, before/after counters, external actions (if any) and evidence supporting the decision. Dry runs establish neither real delivery nor clean cycles. Use another component if the only request is transcription, language selection or one-off artifact generation.
