# P2-R5 real DeepSeek source-paired validation

Status **PARTIAL**: 8/11 planned source pairs completed. Both actual official DeepSeek configurations returned model `deepseek-flash`; the common model/endpoint, M2, source fixtures/Gold/scorer/seed clock, temperature0and output caps were frozen. R0 source0981935; R1 source44f1031with metadata snapshotHEADaef3101. Planner Prompt differs intentionally; app/prompts/planner.py hash changes and actual input-schema catalog changes are recorded. No claim of identical prompts or raw-model-only causality.

Probe succeeded, first source-pair pilot had no request errors, and continuation alternated variant order. Five predeclared Development tasks and six SHA256-ID-selected Blind tasks were planned. No outcome-based case selection or tuning followed the candidate freeze. The old P2-Q pending request194was never opened/replayed; this is a separate explicitly authorized P2-R budget.

| Scope / arm | Strict task | Selection | Arguments | Valid trajectory | Surplus | Environment | Fresh reads | Mean/P95 task ms |
|---|---|---|---|---|---|---|---|---|
|all_complete_pairs/R0|4/8|0.7500|0.6364|0.6667|1|0.8750|7/12|14864.7/24180.3|
|development/R0|3/5|0.8750|0.7143|0.7500|1|0.8000|5/7|15971.0/18688.2|
|blind_subset/R0|1/3|0.5000|0.5000|0.5000|0|1.0000|2/5|13020.8/24180.3|
|all_complete_pairs/R1|7/8|0.9167|0.9091|0.9167|0|1.0000|11/12|15169.7/23505.8|
|development/R1|5/5|1.0000|1.0000|1.0000|0|1.0000|7/7|15801.0/19118.8|
|blind_subset/R1|2/3|0.7500|0.7500|0.7500|0|1.0000|4/5|14117.4/23505.8|

Task success uses completed pairs, including application-fallback recovery from model output errors. Uncertain/incomplete groups are not task failures and are excluded from paired scoring. The registered driver retains raw model_evaluation=NOT_RUN; the outer real-provider record and durable actual HTTP journal establish real execution. R0 P2R-B10 has zero HTTP calls because its Context gate prematurely clarifies an explicit multi-target goal; this is an actual pre-model Agent decision failure under the real-provider configuration, not a DeepSeek response or a simulated LLM result. Other completed groups have real responses. Do not infer direct model semantic accuracy for the zero-call group.

| Case | Split | R0 | R1 |
|---|---|---|---|
|dv01|development|PASS|PASS|
|dv06|development|PASS|PASS|
|dv08|development|FAIL|PASS|
|dv16|development|FAIL|PASS|
|dv18|development|PASS|PASS|
|P2R-B31|blind|FAIL|FAIL|
|P2R-B01|blind|PASS|PASS|
|P2R-B10|blind|FAIL|PASS|
|P2R-B05|blind|UNSCORABLE_CONNECTERROR|NOT_RUN|
|P2R-B30|blind|NOT_RUN|NOT_RUN|
|P2R-B25|blind|NOT_RUN|NOT_RUN|

Development changes3/5→5/5; completed Blind subset1/3→2/3; all completed pairs4/8→7/8. Improved cases aredv08张-form reference,dv16fresh re-read after state event,andP2R-B10explicit multi-target. No completed pair changesPASS→FAIL. These gains belong to the combined context/decision/execution implementation; offline C1/C2 controls do not prove real component-only causal effects.

P2R-B31 fails in both sources because the SKU warranty follow-up takes RAG without the frozen required get_warranty event. The final public model answer can be inspected in the request ledger; tool/state scoring does not independently certify final-answer semantics. Contract disputes remain separate and original failures are retained. Remaining predeclared B05/B30/B25 pairs and the optional repeated pair are NOT_RUN/UNSCORABLE; the latter cannot test nondeterminism.

## Full request accounting and reliability

109attempts;88,858provider-reportedtokens;92,839accountedtokens. Unknown reservation=3,981tokens. Peak-rate estimateUS$0.0472881, including unknown reservation; not a settled invoice. Global limits420HTTP/420ktokens/US$3and per-group24were respected. Concurrency1and generation attempts1; no paid retry. Full measured HTTP-attempt latency=230.909s, including failed connection latency. Token usage includes probe, all node calls, output truncations and recovery calls.

| Arm completed groups | HTTP | Prompt tokens | Completion tokens | Truncations | HTTP mean/P95 ms |
|---|---|---|---|---|---|
|R0|51|28814|10818|4|2166.8/3834.5|
|R1|56|38667|10502|3|2011.3/3400.9|

Request diagnostics: `{"lexical_errors": 7, "schema_errors": 0, "http_errors": 0, "truncations": 7, "transport_failures": 1, "latency_observations": 109, "schema_checked_stages": ["intent", "router", "planner", "generate", "self_correct", "judge"]}`.

Seven truncations remain: six Judge and one R0Planner, all at the common512output cap. Lexical truncation and schema categories are not double-counted as separate model failures; no additional schema errors were observed. Every raw finish_reason/public completion is preserved even when task fallback succeeds. No JSON cap/repair changed between arms and no reliability gain is attributed to Memory or Planner.

The109thattempt (B05/R0, Intent) hit ConnectError; its completion/billing is unknown. A3981-token reservation and measured failure latency remain durablyPENDING. No automatic retry, replacement run or further model call was issued. This is infrastructure failure, not evidence of model quality. No timeout or HTTP error response was observed. Partial execution order may bias which tasks completed; the3real blind pairs cannot establish a population success rate or replace the full33offline result.

## Reproduction and limitations

experiment_config.json records exact source/import/Prompt/helper/harness hashes, common cap expressions/settings fingerprints, datasets/Gold, fixed seed clock, endpoint/model, prices and deterministic selection. Requests are reserved before dispatch; responses checkpoint before downstream parsing. Exact completed responses replay locally only on matching full request/source hashes; any uncertain row prevents automatic resume. API alias/sampling/backend can vary despite temperature0. Repetition was NOT_RUN. Original Gold/scorers and all failed cases remain immutable. All business state was isolated synthetic SQLite; no production order write or raw external tracing.

Prices reverified2026-11-05: https://api-docs.deepseek.com/quick_start/pricing/ ; peak cache-miss input$0.30/M, output$1.20/M, no discounts assumed. No further paid work is part of this stopped experiment. Future reconciled/authorized work must preserve the pending ledger and never resend an uncertain request.

Supplementary Fresh reads counts required successful business-read observations in their required turn, including order/shipment/items/refund/SKU inventory/product/warranty tools and changed order status where specified. It excludes expected Owner/not-found refusals and is separate from the unchanged task score. Order-only freshness remains separately available in analysis.json. The reused raw diagnostic helper counted the unfinished transport as an eighth lexical error; raw_harness_diagnostics preserves that value while the corrected model-output count is7. The missing network response is infrastructure, never a model JSON failure.

## Exact local replay and final-answer limitations

All16completed groups were reexecuted with network/DNS forbidden and MockTransport-only exact method/URL/body response-hash matching. Every recorded response was consumed in sequence, original oracles matched and live ledger/config/results hashes stayed unchanged; new paid calls/tokens0. These are explicitly LOCAL_REPLAY_OF_COMPLETED_PAID_RESPONSES, not fabricated original historical node traces. Initial replay wrongly used integer0 instead of actual provider float0.0; it failed closed, then an independent wire RED/GREEN test fixed only the helper and newv2 outputs succeeded. Initial UNKNOWN outputs remain.

Evidence/r5_replay_R0_v2 andR1_v2 record actual generated versus final service answers. Both B31 final answers falsely report an unconfigured generation model and quote unrelated battery/consumable warranty after Judge truncation, despite proven live model connectivity. This is an existing fallback-control-flow defect; no post-blind production fix was made. Both dv06 answers also collapse a mixed-goal response to a shipment-status sentence after Judge failure. Tool/state Goal Oracle PASS therefore cannot establish semantic final-answer completeness. See evidence/r5_semantic_limitations.json. Real4/8vs7/8 remains the unchanged strict tool/state metric, not a certified semantic answer-accuracy rate. Necessary tool events increase10to12 while surplus1to0; reported tokens increase39632to49169 (excluding probe/uncertainty), a correctness/cost tradeoff rather than a total-call or cost reduction claim.
