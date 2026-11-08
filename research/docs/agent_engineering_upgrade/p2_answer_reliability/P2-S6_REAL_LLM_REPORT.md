# P2-S6 real DeepSeek answer-reliability validation

**PARTIAL_PASS.** Seven source pairs completed: one development pilot and six newly authored validation cases. Strict tool/trajectory/state task success improves from **2/7 to 6/7**. This is not final-answer semantic success: candidate end-to-end results are **0 PASS / 1 FAIL / 6 NOT_ASSESSED**. Required annotated fact coverage is complete in 6/7 candidate answers, but extra natural-language claims lack independent semantic certification.

R0 is the verified P2-R source e74f01db65fb9f3df929cdf5932919e1f10e453e. R1 application remains frozen at 37a7e47d241175c0af9a110686ef6bf90c621c62. The real continuation was prepared after checkpoint d355ecd. No application or Gold tuning followed the held-out results. Both configurations use actual DeepSeekProvider, official endpoint, returned model `deepseek-flash`, M2, temperature0, the same call-site output budgets, tools, Gold and initial synthetic business state. Answer and compact Judge prompts intentionally differ and are individually hashed; identical prompts or isolated raw-model causality are not claimed.

## Execution and evaluator versions

`runs/20261105_S6_pairs_01` retains a preparation-only scope failure, zero HTTP. Run02 contains a successful real P2S_OK probe and PSD03 pair. Its original V2.0 answer scorer falsely classified quantity-before-SKU as missing. All raw responses, scores and exact V2.0 source bytes remain unchanged. The pilot was stopped before later cases. V2.1 fixes the association, exact currency normalization and unknown-versus-omission distinction, with independent negative-value/entity/usage counterexamples. It does not change required facts or business Gold. Detailed RED/GREEN and reviewer limits are in P2-S6_SCORER_REVISION.md and evidence/s6_v21_final_review.json.

Run03 (`runs/20261108_S6_pairs_03`) inherits the 11 original completed requests and successful probe reference once. It does not probe or execute PSD03 again. After frozen development capture rescoring and a fresh-validation pilot, the remaining predeclared groups run in alternating source order, concurrency1. Six validation IDs were selected using SHA256(`P2S-V21-20261105` + ID), before outcomes. All twelve new groups completed; the other18 of24 validation tasks are **NOT_RUN**. The model application and V2.1 evaluator were frozen before any fresh validation execution. Dataset authorship was independently isolated by process, not cryptography. No validation failure was used to tune this candidate.

Common V2.1 scoring is applied to copies of the pilot captures locally; original V2.0 pilot scores remain intact. This measurement correction is not counted as model improvement. The V2.1 adapter uses same-turn observations and per-turn tool failure prefixes; the unchanged environment oracle is final-case-wide. Gold is loaded only after actual execution/capture. No answer-generating LLM is used as an external semantic judge. Product Judge SUPPORTED is a runtime check and never substitutes for independent answer Gold.

| Scope / arm | Strict tool/state | Selection | Arguments | Valid trajectory | Extra tools | Environment | Complete annotated goals |
|---|---:|---:|---:|---:|---:|---:|---:|
|All7 / R0|2/7|35.71%|35.71%|28.57%|5|7/7|2/7|
|All7 / R1|6/7|85.71%|85.71%|85.71%|0|7/7|6/7|
|Development1 / R0|1/1|100%|100%|100%|0|1/1|1/1|
|Development1 / R1|1/1|100%|100%|100%|0|1/1|1/1|
|Fresh validation6 / R0|1/6|25%|25%|16.67%|5|6/6|1/6|
|Fresh validation6 / R1|5/6|83.33%|83.33%|83.33%|0|6/6|5/6|

The environment checks predominantly cover read-only final fixture invariants; they do not certify conveyed answer facts. Selection/argument/trajectory metrics retain the original frozen strict contract. Every failed tool contract remains failed even when a reasonable limitation is expressed.

| Case | R0 tool/state | R1 tool/state | R0 end-to-end | R1 end-to-end |
|---|---|---|---|---|
|PSD03 development|PASS|PASS|NOT_ASSESSED|NOT_ASSESSED|
|PSV03|FAIL|PASS|FAIL|NOT_ASSESSED|
|PSV04|FAIL|PASS|FAIL|NOT_ASSESSED|
|PSV13|FAIL|FAIL|FAIL|FAIL|
|PSV14|PASS|PASS|NOT_ASSESSED|NOT_ASSESSED|
|PSV16|FAIL|PASS|FAIL|NOT_ASSESSED|
|PSV22|FAIL|PASS|FAIL|NOT_ASSESSED|

No completed pair changes strict PASS to FAIL. Four change FAIL to PASS. Independent answer factual correctness remains NOT_ASSESSED in all7 answers per arm, owing to unmatched extra clauses. Faithfulness is R0:1FAIL/6NOT_ASSESSED; R1:7NOT_ASSESSED. There are no verified closed-contract omissions, but R0 has7 unresolved subgoals and R1 has2. These unknowns cannot be reported as zero omissions or correct unrestricted semantics. Overall R0=0PASS/5FAIL/2NOT_ASSESSED; R1=0PASS/1FAIL/6NOT_ASSESSED. Human calibration was offered but no human label was received; **NOT_RUN**.

## Remaining failure and reliability

PSV13 requests the customized product's no-reason-return description and current price. Both implementations route to RAG and execute no business tool, missing required product-detail/price evidence. R0 Judge truncates and the fallback incorrectly says the generation model is unconfigured, quoting an unrelated exchange policy. R1 instead states both facts cannot be confirmed, but still fails to retrieve available required business evidence. This is a capability/routing and goal-completeness limitation, not a reason to relax the Gold. The candidate was not changed after observing it. Full request/node/plan/tool/final-answer/database captures and score reasons remain available.

| Reliability | R0 | R1 |
|---|---:|---:|
|HTTP requests (R0 includes one shared probe)|37|40|
|Reported tokens|37,336|38,131|
|Structured length truncations|9|5|
|Judge truncations / terminal Judge errors|2|0|
|Other invalid JSON object|1 (Generate)|0|
|False model-unconfigured final answers|1|0|
|Mean/P95 task latency ms|14,129.1 / 18,411.3|13,190.7 / 23,592.2|

Fourteen total truncations: R0 Intent3, Router1, Grade1, Judge2, Planner2; R1 Router2, Rewrite3. Output budgets were not uniformly raised. The compact Judge has no observed truncation here, but small non-repeated samples cannot establish a general failure rate. All7 R1 runtime Judges report SUPPORTED, including the incomplete PSV13 limitation response; this is why final task completion requires an independent goal oracle.

## Budget, safety and reproduction

**77 actual HTTP attempts, 75,467 reported/accounted tokens**:57,104prompt+18,363completion. Estimated peak cache-miss cost **US$0.0391668**, not a settled invoice. Global hard caps350HTTP/300,000tokens/US$3; concurrency1;24HTTP maximum per arm/scenario; one attempt per generation; no automatic uncertain-request retry. Unknown usage0, pending0, transport/API timeout0, non200HTTP0. Successful HTTP model-output errors above are recorded separately from infrastructure failures. Sum HTTP latency180.656seconds; mean2,346.2ms; P954,064.5ms (nearest rank). No optional repetition was run, so model nondeterminism is unquantified.

Pricing was reverified on the client date2026-11-08: [DeepSeek official pricing](https://api-docs.deepseek.com/quick_start/pricing/), peak input cache miss$0.30/M and output$1.20/M, no cache/off-peak discounts assumed. The public alias maps to DeepSeek-V4.1-Flash-1017 according to that page; backend weights are not independently verifiable. Default thinking behavior was not changed relative to the frozen service.

All business execution uses isolated synthetic in-memory SQLite. External tracing is disabled. No production order writes, credential exposure, Owner/HITL/idempotency bypass or original strict-contract safety violations were observed. This is bounded engineering evidence, not a universal semantic-safety guarantee.

Each immutable config records code/Prompt/scorer/data/Gold/helper hashes, provider settings fingerprints, endpoint/model, prices, budgets and source bindings. Run03 validates immutable ancestor hashes before dispatch; completed requests are copied unchanged, not billed twice. Captures precede answer scoring. `evidence/s6_real_aggregate_v21.json` is a read-only derived result; `paid_report.py` recreates it without model calls. Existing paid groups and the successful probe must not be repeated. Raw historical P2-Q/P2-R uncertain ledgers remain untouched. Future experiments need a new run and explicit accounting ancestry, rather than resetting this phase's allowance.
