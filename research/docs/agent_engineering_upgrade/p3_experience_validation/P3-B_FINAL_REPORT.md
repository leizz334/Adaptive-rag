# P3-B Experience validation and user semantic review

**PHASE_STATUS=PARTIAL_PASS.** B0–B3authorized engineering is delivered. The user review is imported, sandbox retrieval/injection works with strict safety gates, and full regression plus P4planning are complete. **EXPERIENCE_BENEFIT=NOT_ESTABLISHED; EXPERIENCE_ACTIVE_ENABLED=NO; P4_STARTED=NO.** No real model requests were added.

## Restored evidence and user review

B0/B1delivery local/remote aae3f996c1e8f15aebe3391b6b22e6441862c768was verified before continuation. The user explicitly supplied their edited CSV and continued B2on2026-11-10. All seven case/query/answer identities and enum/aggregate rules are verified. The exact submission SHA2569ae24fe60c2d75498a4429cf79e03f5a0f3955380cd51d6064fec0fa51ad5aa7is preserved under human_review/20261110_submission_01/. The edited original CSV remains uncommitted and byte-preserved; frozen blank B1material remains in Git. Do not regenerate the template over the user's results.

User overall judgments:4PASS,1FAIL,2UNCERTAIN. Factual correctness and faithfulness each4PASS/3UNCERTAIN; completeness6PASS/1FAIL; bounded safety7PASS. PSV13is incomplete; PSV04/PSV16remain uncertain. Reviewer identity/time/notes are not supplied and remain blank, not inferred from import time or model labels. **HUMAN_CALIBRATION=PARTIAL**: these are actual user-submitted decisions, not invented human approval, multi-rater agreement or unrestricted semantic verification. They do not approve the candidate lessons.

## Applicability and sandbox experiment

B0historical results and Gold are preserved: consumed32candidate/task judgments TP12/FP0/FN8/TN76→20/0/0/76; independent32structured judgments TP10/FP0/FN9/TN77→19/0/0/77. B0measures review relevance; the old restrictive matcher and execution exclusions are unchanged. Broader relevance is never an injection permit.

Original three P3-Arecords remain NEEDS_REVIEW/UNREVIEWED. A separate in-memory SQLite repository contains three canonical, source-resolved MODEL_REVIEWED/VERIFIED_OFFLINE copies, qualified only against independently authored structural applicability and explicit sandbox preflight. Human-approved/production-approved experiences remain0. Scope, version, expiry, rejection, feature provenance, original restrictive conditions and known-present evidence are all required. Ambiguity, untrusted input, unknown/empty evidence and pending writes deny injection. Research code has no production import/hook, does not change M2 or the business Graph, and cannot enable Active.

Twelve new independently authored Chinese tasks/13turns use separately frozen Gold. The author reviewed code and scripted-provider behavior: this is procedural independent authorship, **not a blind NLU test or human Gold**. Runtime feature tags are synthetic annotation fixtures. All arms use the unchanged scripted provider, M2, tool contracts, fixed seed clock, clean per-task DB and common scorers. Gold is restricted to the evaluator, with explicit rejection of fields that could override the runtime query/user/confirmation/state change. Model prompts receive only the canonical generic lesson, never Gold or private provenance.

| Metric | E0 no experience | E1 Shadow | E2 isolated injection |
| --- | ---: | ---: | ---: |
| Strict task success | 10/12 | 10/12 | 10/12 |
| Environment/evidence contract | 11/12 | 11/12 | 11/12 |
| Matched required annotated facts | 15/26 | 15/26 | 15/26 |
| Fully covered annotated goals, turns | 5/13 | 5/13 | 5/13 |
| Full factual correctness/faithfulness | 13NOT_ASSESSED | 13NOT_ASSESSED | 13NOT_ASSESSED |
| Overall answer score | 2FAIL/11NOT_ASSESSED | 2FAIL/11NOT_ASSESSED | 2FAIL/11NOT_ASSESSED |
| Principle-injected model calls | 0 | 0 | 13 |

Expected family sets match12/12tasks:36candidate/task judgments TP6/FP0/FN0/TN30. Precision/recall100%are bounded structural selection measurements. There are0strict negative transitions and0positive transitions. B2IR09still lacks product detail/fresh observation; B2IR12retains an invalid trajectory. No new unauthorized operation or strict safety regression is observed; this does not certify authenticated production sharing or all natural-language safety.

Raw E0/E1canonical equality10/12is retained: two HITLtasks generate distinct fresh pending act_UUID handles. Every other node/plan/tool/answer/state field matches. A presence-aware, narrowly typed comparison records decision divergence0/12, including E0/E2. It never ignores changed answers, order/owner IDs, permissions, fields missing versus null or malformed handles. An independent audit of all24pairs confirms only the four fresh-handle fields differ. Original raw scores/traces are not rewritten. Model-input hashes for all12E0/E1pairs match.

The unchanged scripted provider does not interpret extra principles;13changed prompt calls prove channel operation, not experience learning. Therefore **REAL_EXPERIENCE_COMPARISON=NOT_RUN; EXPERIENCE_BENEFIT=NOT_ESTABLISHED**. Optional paid experiments are not escalated without established useful safe offline evidence. New model HTTP0, billed tokens0, estimated costUS$0. Saved P2-Sanswers were not billed again.

## Reliability findings and retained limits

Independent REDtests found duplicate CSV headers silently overriding a verdict and injection eligibility for unknown/empty evidence or pending writes. All four are fixed before evaluation. Explicit source-version and positive-control tests prevent vacuous all-denial success. Gold cannot override runtime request fields. Final Gold/input/source hashes and trusted committed B0result bytes are checked. Original first-run engine-constructor infrastructure failure occurred before any Agent call; it is preserved with the original source/config and a new successful Run ID.

Final review found a comparison-only missing-key/null edge case. Its RED→GREEN fix does not affect any of24saved comparisons; new presence-aware evidence is separate from the frozen original analysis. No Agent/prompt/Gold tuning or paid rerun followed evaluated outcomes. Initial Windows temp ACL errors and REDoutputs remain as infrastructure/test evidence, not model-quality failures.

The frozen Owner-denial annotation omits a legitimate privacy-preserving 'not found' wording, so one abstention failure is a scoring-contract caveat, not proof of a leak. Its original score remains. New open answer semantics are13NOT_ASSESSED per arm; those cannot be replaced by tool success or merged with the seven user-reviewed saved answers. Wider semantic benefit, natural-language feature extraction, authenticated user experience sharing, live-dependency compatibility and production Active readiness remain unverified.

## Final regression and preservation

Final suite **612pytest PASS,0FAIL/ERROR/SKIP**, with one existing LangGraph pending-deprecation warning. Ruff check/format and Mypy149source files pass. This covers historical helper/answer-evaluation compatibility, M2, Planner, tools, retrieval, Judge/fallback/SSE, Owner/Session, HITL/idempotency, trace/privacy and experience lifecycle/error paths. A prior611passing suite precedes the final comparator counterexample; both evidence files remain.

Fresh214legacy strict scenarios preserve original80=80/80, old16=13/16, formerDevelopment30=30/30, formerBlind33=33/33, P2-SDevelopment24=23/24, P2-SHoldout30=22/30and long-window1/1. No old strict PASS→FAIL regression is added. The independently authored12remain consumed counterexamples with unresolved failures, not a new blind success claim.

Audit verifies1,764historical files,20original root user files, old state namespaces/B0/B1tasks/progress prefix, candidate export and source/data/submission hashes. No existing app/eval file changes relative to the B0/B1delivery. Actual credentials do not appear in phase outputs. User original CSV is excluded from staging; the explicit submitted copy is byte-identical. No production DB or external raw tracing is used.

P4_E2E_TEST_PLAN.md specifies future real HTTP API/SSE flows, disposable real-dependency integration, fresh semantic Gold/calibration, controlled real DeepSeek ledgers/budgets, authorization/HITL/idempotency/failure recovery and phase admission. It is a plan only; P4has not started.

## Delivery and recovery

B2task commit3d9c7952497222c06c9cfe6061ea2b740bac6f35. B3validation and final delivery hashes are recorded in task state/Git and evidence/b3_delivery.json. Branch codex/p3-experience-validation uses ordinary push to the authorized https://github.com/leizz334/Adaptive-rag.git followed by ls-remote verification. No force-push. The only intended remaining worktree modification is the user's edited human_review_template.csv.

Recovery sources: feature-list.json, progress.txt, RECOVERY.md, human_review/20261110_submission_01, immutable runs/20261110_B2_01and02, b2_freeze_v2, B3audit/review and612test evidence. Do not repeat successful paid historical requests, overwrite human inputs or reopen consumed holdouts as blind data. All currently authorized P3-Bwork stops after verified delivery. **EXPERIENCE_ACTIVE_ENABLED=NO; P4_STARTED=NO.** Further benefit iteration or P4execution requires a new user instruction.
