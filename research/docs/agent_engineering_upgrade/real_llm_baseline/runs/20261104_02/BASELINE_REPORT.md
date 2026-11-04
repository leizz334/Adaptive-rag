# Real DeepSeek retry before P2 — PARTIAL (request budget reached)

Date: 2026-11-04, Asia/Taipei. Run ID: `20261104_02`.

**The corrected configuration works through the project's actual DeepSeekProvider.** One isolated read-only connectivity request to `https://api.deepseek.com/chat/completions` returned HTTP 200, the expected text, response model `deepseek-flash`, and 61 measured tokens. The prior third-party gateway failure remains unchanged in the parent directory.

**The 15-case evaluation is partial:** 9 valid cases completed (2 PASS, 7 FAIL); 1 case was blocked by the frozen request budget before sending any HTTP request; 5 were NOT_RUN. All seven historical reference cases were evaluated and failed. No production logic, frozen dataset, Gold or P0/P1 evidence changed; no P2 work started.

## Identity, source and control

- Baseline HEAD: `3908634fa71bc2d40343962116768d75e75fe92c`. P1 application/eval/knowledge hashes match the original frozen baseline; the intervening changes were diagnostic scripts and records.
- Connectivity checkpoint: `a19dfc1acc99b43bf07c12b07e524d3915ea56fd`.
- Execution checkpoint: `141a0ad1102d6519e19017c47857440bd24154ab`.
- Branch: `codex/p1-tracing-evaluation-v2`; Conda `adaptive-rag`.
- Configured and every response-reported model: `deepseek-flash`; configured endpoint is DeepSeek's official HTTPS endpoint. The model alias is server-managed; no immutable backend model snapshot is available from these responses.
- Dataset `eval/dataset/agent_v2_extended.json`, schema `agent-scenarios-v2.1`, SHA256 `89005ffbcd721760e851f5b7f47eaabd13153adb7ee037e75cb65eb082535eb7`.
- Same fixed 15 IDs and ordering as the first attempt: seven reference cases first, then the eight controls. Their Gold was not passed to the provider or edited after results.
- Concurrency 1, retries disabled, 80 HTTP attempts total including connectivity, 100000 accounted-token ceiling. **The request limit, not the token limit, stopped the run.** No retry or extra paid call followed the stop.
- Experiment temperature fixed to 0.0. The wrapper records original requested temperatures and overrides production generation's 0.2; production source is unchanged. Production per-stage output caps remain 256/500/512/700 (probe 32), all <=1024. No output cap was increased to improve scores.
- Source/knowledge/prompt/scorer hashes, run-harness hash and Python/package versions are frozen in experiment_config.json. Synthetic order seed timestamps use that run's fixed created_at through an experiment-local clock patch. Session IDs and some runtime/audit timestamps remain generated; input protocol reproducibility is not byte-for-byte or backend determinism.
- Each case creates fresh synthetic SQLite `:memory:` infrastructure via unchanged BusinessEnvironment. No production order, Redis/Qdrant/MCP or remote embedding connection is used. External application/LangChain/LangSmith tracing is disabled. No key, authorization headers or raw upstream error bodies are recorded; request/response hashes and token metadata remain local experiment artifacts.

## Observed metrics and denominators

| Metric | Result | Denominator / definition |
|---|---:|---|
| Agent Task Success | **2/9 = 22.22%** | Valid completed cases; unchanged P1 task criterion |
| End-to-end success including budget interruption | 2/10 = 20.00% | All attempted driver cases; budget error is not a model failure |
| Historical reference correctness | **0/7 = 0%** | Last reference turn: valid trajectory, argument accuracy 1, no turn error |
| Tool Selection Accuracy | **64.71%** | Mean unchanged score_tools selection across 17 valid turns |
| Tool Argument Accuracy | **58.82%** | Mean unchanged argument score across 17 labelled valid turns |
| Environment State Success | **6/9 = 66.67%** | P1 committed-state + required read-observation oracle |
| Observed hard safety violations | **0 / 9 valid cases** | Forbidden mutation/ownership output/unconfirmed-write constraints; limited coverage below |
| Mean / P95 valid-case latency | **19.565 s / 26.298 s** | 9 cases, fixture/service/teardown included; P95 nearest rank |
| Mean / P95 HTTP latency | 2.174 s / 3.152 s | 80 actual HTTP observations, connectivity included |
| Total measured tokens | **58,342** | 44,841 prompt + 13,501 completion |
| Scenario tokens / connectivity tokens | 58,281 / 61 | All reported usage objects present and validated |
| HTTP requests | **80** | 1 connectivity + 79 scenario requests |
| API failures / timeouts | **0 / 0** | HTTP/protocol/transport failures separate from model output errors |
| Model JSON output format errors | **4** | Each had finish_reason=length, completion_tokens=256 |
| Tool failures | **3 invalid_arguments** | In context_loss; missing order arguments rejected by existing tool validation |
| Infrastructure errors | **0** | The local budget stop is separately counted |
| Observed refused responses | 6 / 17 valid turns | Response.refused flags; not a semantic or security-refusal correctness score |
| Budget-interrupted / NOT_RUN | **1 / 5** | No HTTP was sent for the interrupted greeting |
| Scenario wall time | **176.354 s** | Entire bounded evaluation, including interrupted greeting and checkpoint overhead |
| Probe + scenario wall time | **179.403 s** | Excludes offline tests, editing, review and Git/reporting time |

The original summary's 17.631 s mean includes all 10 attempted driver runs, including the 0.230 s budget-interrupted greeting, and remains in results.json for audit. Primary latency above uses only the 9 valid completed cases; both use the same 26.298 s nearest-rank P95. Formula inputs and extra analysis are stored separately from original P1 scores.

The greeting's original P1 driver status was PASS after existing fallback logic, but its experiment status is ERROR because the budget prevented a real model invocation. This is an **experiment validity gate**, not a relabelled Gold/model failure. The unmodified driver status is retained. API/infrastructure/budget ERROR cases are excluded from model quality denominators and exposed in attempted/error counts.

## Failures, safety coverage and interpretation

- `order_lookup` and `explicit_target_change` passed. All seven frozen reference cases failed; common reasons are missing fresh get_order observations and incorrect/missing order arguments. `context_loss` also produced three invalid-argument tool failures and redundant trajectories.
- In the three changed-state reference variants, the required fresh observation was missing. Their environment oracle failure does not indicate that the Agent changed an order incorrectly.
- Four model outputs were truncated at the unchanged 256-token limit and failed JSON-object decoding. Existing production fallback behavior remains in the task result, including the successful explicit-target case; valid HTTP must not be confused with valid structured model output. No independent semantic judge was run and schema-level fallbacks beyond JSON syntax are not comprehensively instrumented.
- **Argument binding, pending approval, foreign-order ownership, cross-user session and injection controls were NOT_RUN.** Zero observed violations on the nine completed query cases is not evidence that these security/HITL cases passed. No cancellation, refund or return business write was executed by this run.
- The deliberately reference-heavy partial sample is biased: 7/9 completed cases are known historical reference failures, and matrix variants are correlated. Do not interpret 22.22% as a broad production-quality estimate or compare it directly with the full 80-case offline P1 percentage.
- The completed subset gives an authentic pre-P2 reference baseline, but the full planned 15-case baseline is **not complete**. Inputs/protocol are frozen and auditable; repeated model calls could vary and require new explicit authorization. No P2 improvement or Memory V2 implementation is claimed.

## Verification and reproduction

31 focused offline tests passed (adapter, previous probe harness, original multiturn and tool scoring), with one existing LangChain deprecation warning. Ruff check/format passed. Independent review reproduced/fixed two experiment-only issues before scenario calls (error denominators and invalid-usage accounting), then independently passed all 10 adapter tests with no material residual findings. Initial temporary-directory fixture errors are recorded in validation.json and progress.txt; they did not consume model calls.

181 frozen P1 file hashes, original P0/P1 task state and the earlier failed-baseline artifacts were verified unchanged. Secret-value scanning of experiment artifacts passed. Raw model execution is not repeated by the offline summary command:

```powershell
conda run --no-capture-output -n adaptive-rag python -B -m research.docs.agent_engineering_upgrade.real_llm_baseline.evaluate_real summary --run-dir research/docs/agent_engineering_upgrade/real_llm_baseline/runs/20261104_02
```

The run command refuses replay once evaluation_started_at exists. A future authorized experiment must create a **new** run directory/config/connectivity result, retaining this run. The new experiment may deliberately reconsider the request budget or subset, but this run's frozen budget, samples, Gold and scores must remain unchanged. See PLAN.md and experiment_config.json for exact controls, results.json and requests.json for execution evidence, failed_cases.md for per-case reasons, and validation.json/validation-pytest.xml for checks.

Run the offline integrity check with `conda run --no-capture-output -n adaptive-rag python -B research/docs/agent_engineering_upgrade/real_llm_baseline/runs/20261104_02/verify_results.py`. It makes no network calls.

Only experiment/state changes are committed. Delivery hashes and actual push result are recorded in git_delivery.json and parent persistent state. **STOP for user review; do not automatically start P2 or issue more model requests.**
