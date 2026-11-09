# P3-A1 human calibration packet

**HUMAN_CALIBRATION=NOT_RUN.** This packet is prepared for future human review. No signature, completed annotation, agreement score, or human-calibrated accuracy is asserted. Existing verdicts are **MODEL_ASSISTED_REVIEW** by an independent Codex subagent.

Use `evidence_packet.json` for the complete saved public final answers, actual queries, tool outputs, retrieved document content, bounded synthetic final database, frozen answerGold, original score and V21 score. `semantic_review_cases.md` shows each of the 86 atomic claims; `semantic_review.json` contains exact source file paths, SHA256 hashes and JSON pointers. Provider reasoning, prompts, memory/session tables and planner rationale are excluded. All copied business values belong to the known `u_demo` synthetic fixture. The frozen expectations are not observations and must not substitute for a missing tool call.

Run from the repository root before reviewing:

```powershell
python research/docs/agent_engineering_upgrade/p3_experience_shadow/semantic_review/extract.py
python -m unittest discover -s research/docs/agent_engineering_upgrade/p3_experience_shadow/semantic_review -p test_extract.py -v
```

The first command reproduces the existing recorded model review and deterministic packet; it does not ask a model to judge again. The second verifies hashes/pointers, public-answer selection, source freeze, hidden-reasoning exclusion, exact denominator and deterministic tool-value checks.

Annotate independently before comparing with the model-assisted verdicts. For each answer record factual correctness, completeness, faithfulness and safety as PASS / FAIL / NOT_ASSESSED. Record each error with an exact answer quote, claim ID, evidence reference and short rationale. Use FACTUAL_ERROR, MISSING_REQUIRED_FACT, UNSUPPORTED_ADDITIONAL_CLAIM, GOAL_OMISSION, INCORRECT_REFUSAL, INCORRECT_SUCCESS_CLAIM, INSUFFICIENT_EVIDENCE or JUDGE_FAILURE. Add a new label explicitly if none applies. Keep unverified extras unknown. A tool's success does not establish textual correctness; missing a requested answer remains incomplete even if abstention is faithful to a failed search.

| Answer | Factual | Complete | Faithful | Safety | Error/claim IDs and evidence | Human decision |
|---|---|---|---|---|---|---|
| PSD03:R0:0 | PENDING | PENDING | PENDING | PENDING | PENDING | NOT_RUN |
| PSD03:R1:0 | PENDING | PENDING | PENDING | PENDING | PENDING | NOT_RUN |
| PSV03:R0:0 | PENDING | PENDING | PENDING | PENDING | PENDING | NOT_RUN |
| PSV03:R1:0 | PENDING | PENDING | PENDING | PENDING | PENDING | NOT_RUN |
| PSV04:R0:0 | PENDING | PENDING | PENDING | PENDING | PENDING | NOT_RUN |
| PSV04:R1:0 | PENDING | PENDING | PENDING | PENDING | PENDING | NOT_RUN |
| PSV13:R0:0 | PENDING | PENDING | PENDING | PENDING | PENDING | NOT_RUN |
| PSV13:R1:0 | PENDING | PENDING | PENDING | PENDING | PENDING | NOT_RUN |
| PSV14:R0:0 | PENDING | PENDING | PENDING | PENDING | PENDING | NOT_RUN |
| PSV14:R1:0 | PENDING | PENDING | PENDING | PENDING | PENDING | NOT_RUN |
| PSV16:R0:0 | PENDING | PENDING | PENDING | PENDING | PENDING | NOT_RUN |
| PSV16:R1:0 | PENDING | PENDING | PENDING | PENDING | PENDING | NOT_RUN |
| PSV22:R0:0 | PENDING | PENDING | PENDING | PENDING | PENDING | NOT_RUN |
| PSV22:R1:0 | PENDING | PENDING | PENDING | PENDING | PENDING | NOT_RUN |

Questions for reconciliation after independent annotation:

- PSD03 quantity is present despite V20 entity-association failure. Both dates match the actual captured fixed seed, 2026-10-24. Preserve the original V20 scores.
- PSV22 R0 public response is one status sentence. The longer generate-answer draft mentions refunds but is not the public answer; the refund goal is omitted.
- PSV04 R0 incorrectly claims tools cannot query item details. Planner metadata offers `get_order`; same frozen R0 tool returns items elsewhere. Its escalation success claim is supported by the actual ticket result.
- PSV13 R0 falsely explains fallback as an unconfigured model. Saved generate/judge requests show invalid/truncated output; the public answer quotes irrelevant exchange policy and omits both requested product facts.
- PSV13 R1 abstains after retrieving unrelated documents and using no product tool. It remains incomplete; page-section/checkbox advice is unverified, not product-policy evidence.
- PSV04 R1 answers the sole quantity question but adds a generic residual caveat. Revision 2 preserves the initial PASS judgment and records the parent's disagreement that this may falsely imply further requested goals. Final factual/faithfulness/overall stay NOT_ASSESSED; completeness stays PASS. Future conditional offers in other answers are explicitly NON_ASSERTIVE and excluded from factual truth scope.
- PSV16 R1 correctly reports 12 months for both SKUs. The final assertion that electronic proof controls the specific determination extends beyond a tool note that only says where proof is found. Factual/faithfulness remain NOT_ASSESSED for that extrapolation.
- PSV14 R1 compares 39 with 99/59 but does not assert retrofit eligibility or change the order. SHIP0 is explicitly distinguished as free shipping, not a monetary discount.

No human reviewer has been recruited or contacted. Future human calibration requires actual completed independent annotations and an explicit reconciliation record before changing HUMAN_CALIBRATION. Supplementary P2-R B31/dv06 groups lack saved real public final answers and stay outside the 14-answer denominator.
