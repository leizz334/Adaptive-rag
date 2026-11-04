# Real configured DeepSeek baseline execution plan

Date: 2026-11-04 Asia/Taipei. Spec: user's “Real DeepSeek Baseline Before P2”.
Only experimental validation and records are authorized; no P2 and no production changes.
User explicitly approved the configured third-party gateway with model provenance limitations.

Architecture decisions (preserve verbatim):
- Use the current P1 production service with the existing llm_factory injection and per-case BusinessEnvironment SQLite in-memory fixtures. Do not modify production logic, frozen datasets, Gold, or success criteria.
- Endpoint https://api.llm.pm is a third-party gateway. Record configured and response-reported models separately; successful HTTP is not independent verification of the underlying model or official DeepSeek API.
- Never load production business infrastructure. Only Settings reads local credentials; explicitly isolate all database, Redis, vector, MCP, retrieval and tracing settings.
- Concurrency 1; at most 80 HTTP attempts including connectivity; no automatic retries; 100000 accounted tokens including conservative reservations for missing usage; each request max_tokens <= 1024; preserve production per-call max_tokens and temperature 0.
- Before each request reserve serialized input UTF-8 bytes + 1024 overhead tokens + requested max_tokens. This deliberately conservative guard is a local estimate, not an upstream tokenizer guarantee. Record actual reported usage and stop on missing/over-budget usage.
- Only synthetic fixtures may reach the approved gateway. Disable external tracing; do not save keys, authorization headers or raw upstream error bodies.
- Checkpoint results after each HTTP attempt and each completed case. Do not automatically replay paid calls after interruption; preserve partial results and stop on upstream/budget failure.
- Reproducible means frozen inputs/code/scorers/config and a rerunnable protocol, not guaranteed identical outputs from a mutable gateway alias.

Tasks:
- [ ] REAL-B1: Recover P1 and freeze inputs/config; verify application selection of DeepSeekProvider in an isolated container; perform one read-only connectivity request and save actual HTTP status, returned model, usage, latency and redacted diagnostics. On failure record blocked baseline and stop evaluation.
- [ ] REAL-B2 (requires REAL-B1 connectivity): Run exactly 15 preselected P1 scenarios sequentially using unchanged run_scenarios and score_tools/score_goal. Seven known reference failures plus eight controls. Add only experiment-local metering/provider adapter if needed, tested with mock HTTP (no paid calls in tests). Record original task/trajectory/argument/state/safety evidence and separate upstream/infrastructure errors.
- [ ] REAL-B3: Verify immutable P1 hashes, calculate metrics/limitations and required outputs, update persistent state without changing P0/P1 task records, task-scoped local commits, verify destination/branch/status then ordinary push. Save actual push status and stop for review.

Validation: experiment-local offline tests for budgets, actual response model/usage and failures; existing multiturn/scoring/environment tests if adapter is needed; immutable source/dataset hashes; no secret values in staged artifacts; local artifact consistency. Do not rerun full P1 or call a judge API.
