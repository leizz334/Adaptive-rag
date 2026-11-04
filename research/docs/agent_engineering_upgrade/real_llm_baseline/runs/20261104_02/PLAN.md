# Authorized real baseline retry 20261104_02

User authorized retry after correcting model configuration. Retain the prior failed run and all P0/P1 evidence; do not implement P2.

Architecture decisions (preserve verbatim):
- Reuse unchanged eval.multiturn.run_scenarios, score_tools and score_goal with llm_factory. Fresh SQLite in-memory synthetic BusinessEnvironment per case; no production orders or external tracing.
- Use the configured official HTTPS endpoint and record the actual response model. Concurrency 1, no retries, at most 80 HTTP requests and 100000 accounted tokens inclusive of the successful 61-token connectivity probe.
- Force temperature 0.0 in the experiment wrapper; retain production per-stage max_tokens (<=1024). Record each original requested temperature. Production generation requests 0.2; this is an explicitly documented experimental override, not a production code change.
- Freeze the same 15 selected cases and seven reference IDs as the first attempt, immutable source/knowledge/prompt/dataset/scorer hashes, harness version, settings and scoring definitions before scenario execution. Gold never reaches the provider.
- Before a request reserve serialized input UTF-8 bytes + 1024 overhead + max_tokens against remaining budget; actual usage replaces that reservation. Stop on invalid/missing/over-budget usage or upstream failure, preserve incomplete/unrun cases. This conservative local estimate is not an upstream tokenizer guarantee.
- Preserve raw original P1 driver status/scores and separately identify model/API errors or harness errors; never count a fallback after failed API as a valid real-model success. Save request metadata and synthetic input/response hashes locally, no API keys/headers/raw upstream bodies.
- Checkpoint each HTTP attempt and completed case. Refuse automatic replay after interruption; reports/verification commands never call the model. Reproducibility means fixed inputs and protocol, not guaranteed identical server outputs.

Tasks:
- [x] RETRY-1: Restore P1 state; freeze new-run config; perform isolated application-provider connectivity check. Actual DeepSeekProvider request returned deepseek-flash, expected text, usage 46+15=61.
- [ ] RETRY-2: Add minimal experiment-only metering adapter, validate offline budgets/error paths, run 15 frozen cases sequentially within limits, checkpoint actual evidence.
- [ ] RETRY-3: Calculate original criteria, reference/selection/argument/environment/safety/latency/token/error metrics; preserve failures, verify immutable inputs, commit/push authorized records, STOP for review. No P2.

Validation: mock transport budget/usage/API error guards; original multiturn/scoring regressions; immutable hash checks; secret scan; independent review before completion. No model judge calls or repeated paid runs.
