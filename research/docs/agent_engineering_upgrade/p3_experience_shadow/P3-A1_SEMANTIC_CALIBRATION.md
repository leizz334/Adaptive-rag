# P3-A1 saved-answer semantic calibration

The seven saved P2-S pairs were independently reviewed as **MODEL_ASSISTED_REVIEW**, covering 14 actual public final answers and 86 atomic claims. **HUMAN_CALIBRATION=NOT_RUN.** This adds a separate interpretation layer; original V20/V21 scores, Gold, captures, app and evaluator remain unchanged.

| Arm | Model-assisted overall PASS | FAIL | NOT_ASSESSED | Completeness PASS |
|---|---:|---:|---:|---:|
| R0 | 2/7 | 5/7 | 0/7 | 2/7 |
| R1 | 4/7 | 1/7 | 2/7 | 6/7 |

R1's remaining incomplete answer is PSV13, which never acquired the product description or price. PSV16 R1 accurately reports both warranty month values but adds an unverified claim about the controlling role of electronic proof; whole-answer factual correctness and faithfulness stay NOT_ASSESSED. Revision 2 records the independent parent model's disagreement about PSV04 R1's generic residual caveat: initial reviewer dimensions/overall are retained, while final factual correctness/faithfulness/overall are conservatively NOT_ASSESSED and completeness remains PASS. The counts are a bounded review of the selected pilot, not a statistical estimate or human accuracy result.

Evidence is drawn from `20261105_S6_pairs_02` (PSD03) and `20261108_S6_pairs_03` (six continuation pairs), actual query/tool/document/final database captures, and separately frozen Gold/scorer V21. `semantic_review/evidence_packet.json` contains complete public responses and allowlisted synthetic evidence. `semantic_review/semantic_review.json` records four dimensions, atomic-claim verdicts, exact source paths/SHA256/JSON pointers, known-versus-inferred grounds, error labels and unknown extras. `semantic_review/semantic_review_cases.md` is the readable case-by-case report. `semantic_review/human_review_packet.md` prepares future human review with all annotation cells pending.

Deterministic extraction and Gold-bound tool-value comparisons are explicitly labeled separately from model-assisted text review. Gold expectations are not presented as observed warranty/policy results. Historical original and V21 aggregate scores are copied with their own immutable source references; the source scorer SHA256 is checked against the V21 freeze.

The review catches a critical provenance distinction: PSV22 R0's final public answer contains only the order-status sentence, although the earlier draft includes refund discussion. It also verifies PSD03's 2026-10-24 date against actual captured values, identifies PSV04 R0's incorrect tool-capability refusal while preserving its genuine escalation ticket, and identifies PSV13 R0's incorrect model-configuration fallback explanation after saved provider generation/judge failures. Unknown policy/UI/proof extrapolations remain recorded rather than silently accepted.

The four saved P2-R B31/dv06 groups are a separate appendix, excluded from the main denominator. Their results preserve tool/strict-score evidence but no saved per-turn real final-public-answer/node capture. They remain semantic NOT_ASSESSED; offline diagnostic traces or provider completions are not substituted and no replay was performed.

Validation (local saved synthetic artifacts only):

```powershell
python research/docs/agent_engineering_upgrade/p3_experience_shadow/semantic_review/extract.py
python -m unittest discover -s research/docs/agent_engineering_upgrade/p3_experience_shadow/semantic_review -p test_extract.py -v
```

Both commands ran successfully on 2026-11-09: extraction yielded exactly 14 answers / 86 claims, scorer hash matched the freeze, and all seven provenance/content/count tests passed. Tests verify every reported JSON reference/hash, exact public-answer selection, forbidden hidden-reasoning/memory fields, frozen clock and V20 preservation, denominator separation and deterministic tool-value comparisons. They do not validate the model's semantic opinions. Independent parent review and eventual human annotations remain separate requirements; no human calibration, inter-rater agreement or general safety certification is claimed.

No API requests, environment-secret reads, live business operations, app/eval/Gold changes, commits or global state updates were performed by this semantic-review subtask.
