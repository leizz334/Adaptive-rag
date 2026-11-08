# P2-S Answer Reliability & Task Completeness

**PHASE_STATUS = PARTIAL_PASS.** Authorized S0–S7 engineering, source controls and bounded real validation are delivered. The compact Judge and evidence-grounded fallback improve reliability; goal/capability changes improve strict execution. Full natural-language answer correctness remains insufficiently verified. No P3/P4 work is started.

## What changed and why

The existing graph is retained. Judge errors are separated from supported/unsupported/insufficient evidence, with explicit truncated/malformed/schema/API categories. A compact verdict replaces open-ended rationale; the default512Judge token budget is retained. Safe fallbacks express only allowlisted successful tool observations and explicit limits. They never infer model misconfiguration, quote arbitrary unrelated policy as an answer, or claim an unconfirmed write succeeded. Streaming EOF/length errors are surfaced instead of silently accepted. Evidence invalidation is field-specific, preserving unchanged amount and shipment information after business actions.

A small goal/evidence mapping distinguishes live order/product/shipment facts from static policy and supports compound goals, conservative negative/conditional directives, and unresolved-goal limits. It uses current tool contracts and preserves Owner, Session, HITL and idempotency paths. Generated refusal flags cannot bypass verification. No new memory layer, framework, training or product Multi-Agent was added.

An independent answer evaluator checks annotated facts, goal coverage and actual evidence after execution, separately from tool/trajectory/environment scores. Unknown clauses and open semantics remain NOT_ASSESSED. A development real pilot exposed an evaluator association bug; its original V2.0 results and source were preserved. V2.1 was independently reviewed, tested and frozen before fresh validation. Its score changes are not application gains. Gold never enters the Agent.

## Checkpoints and frozen evidence

Baseline e74f01db65fb9f3df929cdf5932919e1f10e453e was verified against the authorized remote; its app tree matches the earlier44f1031freeze. S0 checkpoint269682e; S1 checkpoints0a876ae/fcec992/1c6b506; S2=412e410; S3 final application=37a7e47; S4=cdce3f0; S5=a77b978; paid harness=c116ea3/f8ab5fd; reviewed V2.1 checkpoint=d355ecd; real results=7db6907. Exact complete hashes and task evidence are recorded in feature-list.json, progress.txt, freeze/config files and Git. Delivery verification lives in evidence/delivery.json; the final metadata commit naturally follows the recorded validation checkpoint.

All368prior audit/report/raw-evidence files, original dataset/Gold and old task namespaces remain unchanged. Root20user files including.env are byte-preserved. The separate worktree/branch is codex/p2-answer-reliability; the original working directory remains untouched. No credentials or hidden reasoning are exported. External tracing is disabled for experiments. All business state uses isolated synthetic databases.

## Controlled offline results

Four actual source arms use common M2, scripted provider, scorer, Gold and fixed-clock fixture. S1 retains only Judge/fallback behavior; S2 retains goal/capability behavior; S3 combines them. The shared pure renderer is a necessary dependency, so these are disclosed mechanism bundles rather than perfectly disjoint file-level factorial arms. Independent source hashes, initial seed hash3836b44bab3ea8a397a566228da2ccf0f3f3cb7c78ab5c43c6ab2799cb4e9cfc and214cases/arm are retained. Initial S1 patch and seed-clock control errors were corrected in new runs; initial evidence remains intact.

| Strict tool/state tasks | S0 | S1 | S2 | S3 |
|---|---:|---:|---:|---:|
|Original80|80/80|80/80|80/80|80/80|
|Old16|13/16|13/16|13/16|13/16|
|Former Development30|27/30|27/30|30/30|30/30|
|Former Blind33, now regression|26/33|26/33|33/33|33/33|
|Long window|1/1|1/1|1/1|1/1|
|New Development24|12/24|12/24|23/24|23/24|
|New original Holdout30|12/30|12/30|22/30|22/30|

No original strict PASS becomes FAIL. The development failure is PSD06; original new-holdout failures are PSH13/18/19/20/25/26/28/30. Full causes, calls and database differences remain in P2-S5_OFFLINE_ABLATION.md and raw runs. Historical data lack final-answer Gold and remain NOT_ASSESSED for semantics; strict success is never converted to semantic success.

Under the frozen V2.0 answer contract, candidate Development24 is10PASS/2FAIL/12NOT_ASSESSED; original new Holdout30 is1PASS/13FAIL/16NOT_ASSESSED. S0/S1 are0/17/7 and0/21/9 respectively. These are scripted engineering results, not real Chinese model-language accuracy. V2.1 is a separate measurement revision; these original numbers have not been rewritten.

S1 isolated fault controls preserve both amount and shipment when Judge fails, while S0/S2 drop amount or quote unrelated material. Successful scripted execution does not measure Judge reliability; dedicated fault tests do. S2 improves goal/tool execution under the scripted model; the combination is not wholly attributed to Memory or Judge.

## Real source-paired validation

The official configured provider returned deepseek-flash. One development pair and six independently authored fresh validation pairs completed with identical per-pair seed state, common M2/tool/Gold/model/config and alternating source order. Intentional prompt/Judge differences are hashed. A first pilot caused the versioned scorer repair; no paid request was repeated. The new validation24was authored separately without implementation/result access and frozen before any application run; six cases were hash-selected, the other18NOT_RUN. Original Holdout30 and all P2-R former blind data are consumed regression data.

| Real metric | P2-R source R0 | P2-S source R1 |
|---|---:|---:|
|Strict tool/trajectory/state task|2/7|6/7|
|Fresh validation subset strict task|1/6|5/6|
|Tool selection / argument accuracy|35.71% / 35.71%|85.71% / 85.71%|
|Valid trajectories|28.57%|85.71%|
|Redundant tool calls|5|0|
|Environment invariants|7/7|7/7|
|Complete required annotated fact coverage|2/7|6/7|
|Full factual correctness|7NOT_ASSESSED|7NOT_ASSESSED|
|Full answer faithfulness|1FAIL/6NOT_ASSESSED|7NOT_ASSESSED|
|Overall end-to-end|0PASS/5FAIL/2NOT_ASSESSED|0PASS/1FAIL/6NOT_ASSESSED|
|Judge errors / truncations|2 / 2|0 / 0|
|All node truncations|9|5|
|False model-unconfigured answers|1|0|

The prior P2-R4/8→7/8 real experiment is historical context with different samples and tool/state scoring. It is not the denominator for this answer-quality comparison. There is no independently verified unrestricted semantic success rate here. Six answers convey the candidate's required annotated facts, but their extra clauses remain unknown. Human semantic calibration is NOT_RUN; product same-model SUPPORTED verdicts are not accepted as external truth.

PSV03/04/16/22 change strict FAIL→PASS, none PASS→FAIL. PSV13 remains failed: mixed static no-reason-return wording plus live product price routes to RAG without the required product facts. Candidate correctly expresses inability to confirm but does not complete available evidence retrieval. Its two unresolved subgoals cannot be called successful omissions-free completion. No post-holdout fix was attempted.

77HTTP requests,75,467reported/accountedtokens (57,104input+18,363output); estimatedUSD0.0391668, not an invoice. Limits350HTTP/300,000tokens/US$3 and concurrency1 respected. No unknown usage, pending request, HTTP error, transport failure or timeout. Fourteen model truncations and one nontruncated invalid JSON object are preserved. No infinite retries or uncertain resends. SumHTTP latency180.656s, mean2,346.2ms/P954,064.5ms. Candidate task mean13,190.7ms/P9523,592.2ms; no isolated performance or deterministic-model claim.

Pricing/source limitations and detailed conversions are in P2-S6_REAL_LLM_REPORT.md. All remaining real repetitions and semantic adjudications are NOT_RUN. No extra calls will be made in this phase.

## Final verification and limits

475pytest passed, zero failures/errors/skips, including historical evaluation helpers and new scorer/runner tests. Ruff check and format--check pass; Mypy passes140source files. Full suite covers provider compatibility, Judge/schema/API failures, SSE cleanup, owner/session isolation, HITL, idempotency, bounded retry, tracing and argument safety. P1 production-service compatibility remains13/14with its known M0context-loss limitation; this is not a new regression. RED evidence and independent counterexamples precede fixes. Initial Windows wildcard/TempACL and format-check failures are retained and corrected, not counted as model failures.

Zero observed original strict-contract safety violations and zero strict PASS→FAIL regressions across controlled offline tasks or completed real pairs. This bounded result does not certify all natural-language safety. Independent fresh validation failed cases were preserved without relaxing tool budgets, Gold or permission checks. The old16still has3known failures, new offline holdout8, and fresh real validation1; these are distinct datasets, not additive population estimates.

Outstanding: open semantic and human calibration evidence, unknown extra answer clauses, PSV13mixed capability retrieval, broader non-Judge structured truncation, limited real sample size/no repeat, and original new-holdout write/compound cases. Further model/prompt work would require a new candidate and a new independent validation contract; this phase stops after delivery.

Recovery: feature-list.json, progress.txt, RECOVERY.md, exact freezes and immutable request journals. Do not rerun successful paid groups, reuse uncertain historical ledgers or overwrite any run. Git delivery uses normal push only; actual remote verification is recorded in evidence/delivery.json and final user output. **P3_STARTED=NO; P4_STARTED=NO.**
