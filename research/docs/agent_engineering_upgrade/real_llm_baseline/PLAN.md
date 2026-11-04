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
- [x] REAL-B1 attempted, BLOCKED (passes=false): P1 restored and inputs frozen; DeepSeekProvider selected. Initial sandbox permission failure followed by one explicitly elevated probe: HTTP 200 / JSONDecodeError, no valid completion/model/usage. Diagnostic checkpoint 32b85301a1195cfa50ee6cf0754475327e9c0701. Further paid calls stopped.
- [ ] REAL-B2 NOT_RUN (requires REAL-B1 connectivity; passes=false): All 15 preselected cases, including seven reference failures, retained unchanged as NOT_RUN. No scenario adapter implemented after the failed gate; no offline substitution.
- [x] REAL-B3 completed: 181 immutable P1 hashes verified; eight offline tests and lint/format passed; review clean. Failure report and 15 NOT_RUN records committed at 13d8ee7303ef280ef777c177d3b8f91b44efdf87 and ordinary push succeeded. Exact outcome in git_delivery.json; registration synchronized separately. STOP for user review; no P2.

Validation: experiment-local offline tests for budgets, actual response model/usage and failures; existing multiturn/scoring/environment tests if adapter is needed; immutable source/dataset hashes; no secret values in staged artifacts; local artifact consistency. Do not rerun full P1 or call a judge API.
