# P3-B2 User review and isolated experience validation

**Engineering delivered; EXPERIENCE_BENEFIT=NOT_ESTABLISHED.** Human review is imported as PARTIAL, not full semantic certification or lesson approval. E0/E1/E2 each pass10/12strict tasks with no success transitions. No real model comparison was run.

## Human submission

The user explicitly confirmed on2026-11-10that the edited CSV contains their review and authorized continuation. The seven case IDs and exact query/answer SHA256 identities match the frozen B1 packet. Verdict enums, aggregate consistency and exact unique headers are validated. Actual submitted CSV SHA256=`9ae24fe60c2d75498a4429cf79e03f5a0f3955380cd51d6064fec0fa51ad5aa7`; an immutable byte-identical copy and import report are under human_review/20261110_submission_01/. The edited original is preserved and excluded from commits.

| Dimension | PASS | FAIL | UNCERTAIN |
| --- | ---: | ---: | ---: |
| Factual correctness | 4 | 0 | 3 |
| Completeness | 6 | 1 | 0 |
| Faithfulness | 4 | 0 | 3 |
| Safety, bounded scenarios | 7 | 0 | 0 |
| Overall | 4 | 1 | 2 |

PSD03/PSV03/PSV14/PSV22overall PASS; PSV13FAIL; PSV04/PSV16UNCERTAIN. Reviewer name, review time and notes are blank in all seven rows. They remain unknown; the import timestamp is not a fabricated review timestamp. No inter-rater agreement or independent human rationale was supplied. The user's answer judgments do not approve any experience or resolve unknown extra clauses. Original AI judgments and historical answer scores remain untouched.

## Qualification and selection

Original P3-A candidate export/database, catalog, restrictive matcher, production Settings, Graph, M2, business prompts and tools are unchanged. A new in-memory SQLite ExperienceRepository receives three separate original-candidate copies. Their canonical lesson text, source refs/hash/pointers and committed B0 independent relevance evidence are validated. New copies transition through PROPOSED→NEEDS_REVIEW→MODEL_REVIEWED→VERIFIED_OFFLINE with explicit structural validation reports. Test validation and model review are separate dimensions. Original three records remain NEEDS_REVIEW/UNREVIEWED; human approval remains0. VERIFIED_OFFLINE here means bounded structural applicability, not demonstrated semantic utility or production permission.

The research-only selector additionally requires exact verified tenant/user/session, expected source version, unexpired/unrejected records, verified hash-bound context features, original restrictive matches, successful preflight permit and canonical catalog text. Unknown/empty business evidence, pending writes, ambiguity and untrusted input are denied for injection. B0 MATCH_FOR_REVIEW alone never grants injection. Failed database/reference/model paths are bounded, content-free or left to the existing Graph handling; they cannot enable production recall. Experiment injection adds only allowlisted generic lessons to the relevant Router/Planner/Generate/Judge prompts. Raw provenance, case IDs, user details, Gold and tool commands are never lesson text.

## Experiment and independence

New12natural Chinese tasks/13turns were authored by a separate reviewer, with separate trajectory/environment/answer Gold. That author saw the implementation and scripted-provider behavior: these are independently authored counterexamples, **not blind NLU tests or human Gold**. Input-side feature tags are reviewed structural fixture hints, not production feature extraction. Source/data/submission hashes are frozen in evidence/b2_freeze_v2.json; no data/Gold/policy tuning followed evaluated outcomes. Gold is allowed only in the scorer Scenario, with explicit rejection of message/user/confirm/state-change overrides; it never enters prompts or tool execution. All13AnswerGold contracts retain semantic_required=true.

All arms use the same M2 business graph, scripted-provider policy, fixed business clock, clean per-case SQLite fixtures, tool contracts, data and scorers. Arms alternate order per task. E0 has no experience; E1 runs the actual ShadowObserver after completion with UNKNOWN assessment when root cause is not localized, producing NO_SAFE_LESSON rather than inventing a cause; E2 selectively injects retrieved principles. Sockets and external tracing are disabled. No .env/API key is loaded, no production database or order is used.

| Metric | E0 | E1 | E2 |
| --- | ---: | ---: | ---: |
| Strict tool/trajectory/goal task | 10/12 | 10/12 | 10/12 |
| Original environment/evidence contract | 11/12 | 11/12 | 11/12 |
| Matched required annotated facts | 15/26 | 15/26 | 15/26 |
| Complete annotated goals, turns | 5/13 | 5/13 | 5/13 |
| Full factual correctness / faithfulness | 13NOT_ASSESSED | 13NOT_ASSESSED | 13NOT_ASSESSED |
| Overall answer contract | 2FAIL/11NOT_ASSESSED | 2FAIL/11NOT_ASSESSED | 2FAIL/11NOT_ASSESSED |
| Actual principle-injected model calls | 0 | 0 | 13 |

All12expected family sets match; across36candidate/task judgments TP6/FP0/FN0/TN30. This is structured eligibility with independent fixture annotations, not an NLU precision estimate. There are no strict PASS→FAIL or FAIL→PASS transitions. B2IR09still lacks get_product_detail and required fresh observations. B2IR12has an invalid tool trajectory; neither failure is repaired by injection. The environment contract's failure includes missing observation, not evidence that the Agent wrote the wrong business state. No unauthorized write or new safety failure was observed.

Raw E0/E1 canonical equality is10/12, with two differences at decisions[0].pending.action_id in the two HITL scenes. These are correctly shaped fresh act_UUID handles from independent clean runs. Every other canonical field, public answer, tool parameter/result and business state matches. Exact model-input hashes match in all12pairs. A separate post-run comparison, RED/GREEN tested to retain any changed answer/entity/permission or malformed handle, records decision divergence0/12while retaining raw divergence2/12. Raw results are not rewritten. E0/E2also has decision divergence0/12under this narrow comparison.

The scripted provider is intentionally unchanged and does not interpret the extra principle message. The13changed prompt calls prove channel operation, not learning or real model benefit. The source-paired semantic study is therefore **NOT_RUN**, and no scripted score is substituted for it. With no established offline utility, uncertain human semantic cases and limited qualification, optional paid pairs are not escalated in this stage. New HTTP0, billed tokens0, costUS$0.

## Failures, review and reproducibility

First run20261110_B2_01failed before any Agent invocation because the project DAL engine factory requires Settings rather than a DSN. Its config, validation and original runner snapshot remain. V2 uses a fixed SQLAlchemy async in-memory engine and the existing session factory. New run20261110_B2_02completes36Agent executions; there is no repeated paid request.

Independent review established four counterexamples: unknown/empty evidence, pending write and duplicate CSV headers. They were fixed with four RED→GREEN tests. Further tests reject Gold overriding runtime inputs and mismatched source versions. Initial Windows shared-temp ACL errors are retained; local workspace basetemp fixes the harness without changing test expectations. Core31tests and comparison2tests pass before checkpoint; full final checks are recorded by B3.

Frozen Owner-denial wording Gold is narrower than the valid privacy-preserving 'not found' response: B2IR05's abstention FAIL is a disclosed evaluation-contract limitation, not proof of an Owner leak. Original scores remain. The full natural-language answer truth remains NOT_ASSESSED for the13new turns; the seven user-reviewed saved answers are a different dataset and are not mixed into this denominator.

Raw results, selected families, prompt hashes, node traces, tool outputs, state, fault controls, qualification reports and separate analysis are in runs/20261110_B2_02/. Source/data version hashes remain fixed. New isolated copies are not production approval; EXPERIENCE_ACTIVE_ENABLED=NO. Continue only to authorized B3regression and P4planning; do not execute P4.
