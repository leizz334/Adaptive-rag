# P3-A2 failure evidence taxonomy

This is a provisional, offline evidence review of preserved traces. It produces no approved lessons, changes no application behavior, and reruns no provider requests. The machine-readable record is [evidence/a2_trace_diagnoses.json](evidence/a2_trace_diagnoses.json). Its source registry binds every cited JSON artifact to its SHA256; each evidence reference identifies an exact JSON pointer. Source-level mechanism review and classifier implementation are coordinated separately.

The primary cohort contains 14 saved P2-S completions: seven pairs, including the two PSD03 development-pilot captures. Six traces fail the required tool/state contract, and eight are scoped negative controls. The controls verify successful required tool calls and corresponding annotated goal coverage; they do not certify every free-form answer. Open semantic human calibration remains NOT_RUN.

## Evidence and certainty

`VERIFIED_FAILURE` requires a visible divergence between a required goal and the actual node chain, arguments, outputs or delivered answer. `LIKELY_FAILURE` describes a supported causal hypothesis whose unique mechanism is unresolved. `UNDETERMINED` preserves unassessed semantic outcomes, including the broader semantic outcome of tool/state controls. `EVALUATION_ARTIFACT` identifies a measurement defect instead of an agent defect. A verified failure may have only a likely root cause.

Confidence is an ordinal evidence rubric, not a calibrated probability or the provider's self-reported confidence. HIGH means that the required contract, actual node outputs and relevant completed request records agree. MEDIUM means that a plausible mechanism has competing explanations. No hidden model thoughts are inferred. Partial provider rationale strings are not treated as valid plans or valid judge judgments.

The first error node is the earliest *observable* contract divergence in the available chain. It does not locate an invisible internal cause. For example, a required capability missing from the planner's advertised tool set can explain an omitted plan step without proving that the planner ignored a capability it could use. `wrong_arguments` in an aggregate score does not establish `PLANNER_ARGUMENT_ERROR` when the required call never happened.

## P2-S real14 trace review

Each table ID maps to `diagnosis_id` in the JSON. The JSON includes full node order, required tool contracts, actual arguments and success, request-stage parse observations, before/after answer evidence, alternatives and source pointers.

| Case | Arm | Observable first divergence | Primary finding | Actual downstream evidence |
|---|---|---|---|---|
| PSD03 | R0 | None within tool/state scope | Negative control | Correct order header and purchased items; delivered status and one mug. Old V2.0 score is separately recorded as an artifact. |
| PSD03 | R1 | None within tool/state scope | Negative control | Same required reads and one-mug answer; V2.1 annotated coverage is complete. |
| PSV03 | R0 | `plan_tasks` | PLANNER_MISSING_TOOL | Required product-detail capability is absent from advertised tools. Substitute search misses the custom mug but finds T-shirt price; final answer leaves mug price unresolved. |
| PSV03 | R1 | None within tool/state scope | Negative control | Product detail reads for both requested SKUs return 3900 and 7900 cents; final answer conveys both prices. |
| PSV04 | R0 | `plan_tasks` | PLANNER_MISSING_TOOL | Purchased-items capability is absent from advertised tools; escalation executes successfully and final answer says quantity cannot be verified. |
| PSV04 | R1 | None within tool/state scope | Negative control | Purchased-items read returns one headset; delivered answer conveys one item. |
| PSV13 | R0 | `route_complexity` | ROUTING_ERROR | Multi-hop RAG bypasses planner/executor and has no current-price observation. Invalid generation JSON triggers an excerpt fallback; invalid judge output triggers a false unconfigured-model replacement. |
| PSV13 | R1 | `route_complexity` | ROUTING_ERROR | Multi-hop RAG bypasses planner/executor. Retrieval supplies neither SKU-specific description nor current price; the final answer faithfully abstains on both requested facts. |
| PSV14 | R0 | None within tool/state scope | Negative control | Coupon and order reads provide independent thresholds and order amount; no business mutation. |
| PSV14 | R1 | None within tool/state scope | Negative control | Both required reads and annotated facts present; no business mutation. |
| PSV16 | R0 | `plan_tasks` | PLANNER_MISSING_TOOL | Warranty capability is absent from advertised tools; truncated planner JSON is followed by empty product-search/recommendation outputs and abstention on warranty months. |
| PSV16 | R1 | None within tool/state scope | Negative control | Warranty read for each SKU returns 12 months; final answer states both values. |
| PSV22 | R0 | `plan_tasks` | PLANNER_MISSING_TOOL | Refund capability is absent from advertised tools; only order header is read. Generated answer admits missing refund evidence; invalid judge fallback reduces final answer to order status and drops the refund goal. |
| PSV22 | R1 | None within tool/state scope | Negative control | Order and refund-status reads execute; empty refund list is distinct from delivered order state and conveyed separately. |

The primary failure counts are ROUTING_ERROR=2 and PLANNER_MISSING_TOOL=4. Secondary finding occurrences are INSUFFICIENT_CONTEXT=2, JUDGE_INVALID_OUTPUT=2, FALLBACK_ERROR=3, ANSWER_FACTUAL_ERROR=1 and GOAL_OMISSION=1. These overlap within cases and must not be added to a failure denominator. One FALLBACK_ERROR finding, PSV16 R0, is marked LIKELY rather than verified at the source-mechanism level.

For four R0 planner omissions, the actual request's `available_tool_names` excludes the required tool: product detail, purchased items, warranty and refund status respectively. Upstream capability exposure is a likely explanation. A model-reasoning-only explanation is not established. For PSV03, exact-name scoring alone is insufficient: the empty custom-mug result and missing mug-price answer independently demonstrate lost task evidence. Successful substitute-tool execution is not a retrieval or execution exception.

### PSV13: mixed policy and current-price request

Both arms classify the question as `product_consult` and route to `multi`; their actual chain is guardrail → intent → router → retrieve → generate → faithfulness → memory compaction. No planner or executor node runs. The saved router HTTP responses are empty with `finish_reason=length`, so an explicit successful router model decision cannot be inferred from the node output. Source review must distinguish fallback/rule routing from prompting effects.

R1's rewrite requests also truncate; the final retrieval node records the original query. Its retrieved chunks do not contain the requested SKU's catalog description or live price. This establishes an insufficient observation context downstream of routing, but does not uniquely establish a query-rewrite, retrieval-corpus or reranker root cause. The final answer says that both facts are unavailable, and the faithfulness node reports SUPPORTED. That is compatible with a verified task failure: faithful abstention does not supply the requested facts. Do not classify it as a planner-selection failure, because no planner ran.

R0 retrieves a general custom-return-policy chunk alongside unrelated material, so claiming that all policy evidence is absent would be wrong. Its generate HTTP response ends with `stop` but contains an unescaped literal newline inside the answer string, making the structured JSON invalid. The generation node falls back to an excerpt. Its judge response is empty with `length`; the faithfulness node records INVALID_OUTPUT, then replaces the answer with “当前未配置生成模型” and an exchange-policy excerpt. Completed generate/judge HTTP records contradict that user-facing configuration claim. The verified defect is the fallback's false claim and information loss, not an observed missing API key or provider outage.

### Structured-output failures

Malformed or length-terminated structured responses are retained by stage and exact request pointer. An HTTP 200 containing invalid JSON is JUDGE_INVALID_OUTPUT when the judge output is unusable; it is not JUDGE_API_ERROR. Truncated planner responses for PSV16 R0 and PSV22 R0 must be distinguished from malformed generation for PSV13 R0. Router and rewrite failures are separate observable input-quality signals. Their presence alone does not prove that every later task failure was caused by that stage.

## Supplementary P2-R evidence

P2R-B31 and dv06 are a separate cohort. The JSON contains four records, two arms per case. Node chains come from `r5_replay_R0_v2` and `r5_replay_R1_v2`, explicitly labeled LOCAL_REPLAY_OF_COMPLETED_PAID_RESPONSES, and are corroborated by original paid `requests.json` stage records and `results.json` tool evidence. These records are not new real-provider runs and are excluded from the real14 denominator.

For P2R-B31 turn 1, the user explicitly changes topic from an order to an identified SKU's warranty. `classify_intent` labels it faq_policy; `route_complexity` selects single-hop retrieval, and no warranty tool runs. The trace supports an intent/routing divergence, followed by invalid judge output and an unrelated consumables-policy excerpt with the same false unconfigured-model message. It does not establish that prior order memory caused the failure. No incorrect warranty argument is visible because no warranty call exists.

For dv06, both required order and shipment reads execute successfully for the correct entity. Generation contains order status and two logistics events, but `check_faithfulness` replaces that answer with only “物流状态：运输中”. The independent order-status goal and trajectory detail disappear. This is verified replay evidence of GOAL_OMISSION and FALLBACK_ERROR following a length-terminated invalid judge output, despite original tool/state PASS. It is a useful negative control against treating successful execution as successful delivery of all goals.

## Known V2.0 measurement artifact

Both PSD03 pilot captures contain correct order and purchased-quantity observations and an answer giving one custom mug. Preserved V2.0 scores call the quantity goal missing; separately stored V2.1 scores recognize it. The historical scorer revision records a quantity-before-SKU association restriction. These two records are EVALUATION_ARTIFACT / EVALUATION_CONTRACT_ISSUE, and are excluded from agent-failure counts. The same preserved completion rescored by a revised evaluator is not a model improvement. Historical scores, requests and captures remain unchanged.

## Full category boundary

| Category | Treatment in this evidence set |
|---|---|
| ROUTING_ERROR | Verified primary real14 failures for both PSV13 arms; supplementary B31 intent/routing divergence. |
| QUERY_REWRITE_ERROR | Invalid/truncated rewrite responses observed, but no uniquely attributable primary cause established. |
| RETRIEVAL_MISS | Absence of required retrieved facts observed; corpus coverage versus ranking versus missing structured-tool route remains unresolved. |
| RERANK_ERROR | Not established by final retrieved ranking or missing facts alone. |
| INSUFFICIENT_CONTEXT | Verified downstream absence of required live-price/catalog observation for PSV13. |
| MEMORY_RESOLUTION_ERROR | Not established; history presence is not a memory defect. |
| ENTITY_BINDING_ERROR | Not established for agent behavior; V2.0 association failure belongs to the evaluator. |
| PLANNER_TOOL_SELECTION_ERROR | Wrong/missing business capabilities observable, but capability exposure confounds free planner choice. |
| PLANNER_ARGUMENT_ERROR | Not established merely by aggregate wrong_arguments scores when required calls are absent. |
| PLANNER_EXTRA_TOOL | Extra substitute/escalation calls observable; not assumed to be the first causal failure. |
| PLANNER_MISSING_TOOL | Four primary real14 failures; contracts and actual plans agree that required reads are missing. |
| TOOL_EXECUTION_ERROR | Not established for cited real14 tool calls, which succeed. |
| STALE_BUSINESS_STATE | Not established; no demonstrated stale live-state answer. |
| GOAL_OMISSION | Verified final refund-goal loss for PSV22 R0; supplementary dv06 loses independently requested goals after generation. Admitted unknown goals are not automatically omission. |
| ANSWER_FACTUAL_ERROR | False unconfigured-model fallback claim verified against same-group completed provider records. |
| ANSWER_FAITHFULNESS_ERROR | Invalid/partial judge text is not valid evidence of semantic unfaithfulness. No general claim assigned from it. |
| JUDGE_INVALID_OUTPUT | Verified unusable structured judge completions; separate from business-fact error. |
| JUDGE_API_ERROR | Not assigned to HTTP-success invalid completions. |
| FALLBACK_ERROR | Verified false or lossy fallback answers; one planner-fallback hypothesis remains likely. |
| ENVIRONMENT_FAILURE | No real14 environment failure; saved before/after order states and environment oracle pass. |
| EVALUATION_CONTRACT_ISSUE | Two preserved V2.0 PSD03 association artifacts, separately counted. |
| UNKNOWN | Retained category for evidence that cannot support a narrower explanation; no forced cause assignment here. |

Candidate principles are hypotheses for later verification: preserve each independent live-fact goal through routing; check advertised capabilities before blaming planner reasoning; retain verified facts and explicit uncertainty when the judge is unavailable; score the delivered answer after fallback; isolate evaluator artifacts and replay evidence. None is an approved lesson or an instruction to production prompts.


## Implemented structural classifier
app/experience/contracts.py defines all22categories, typed bounded provenance and proof classes; taxonomy.classify_failure prioritizes earliest confirmed structural evidence, separates model hypothesis, score-only unknown and scorer artifact. Root remains HYPOTHESIS even when failure is verified. classify_saved.py validates27historicalsource hashes and155pointers, then normalizes independently reviewed labels into20assessments. Its label reproduction is contract consistency, not blind failure-classification accuracy. A first adapter invocation encountered dict-versus-string first_error_node; normalized the existing node field without changing raw diagnoses or schema. RED14missing-feature failures then GREEN14tests; Mypy143PASS. No runtimeAgent import or historical score changes.
