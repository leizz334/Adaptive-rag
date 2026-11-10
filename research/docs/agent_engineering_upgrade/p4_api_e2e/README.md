# P4-A isolated real HTTP testing

Run from the fixed existing worktree, using Conda adaptive-rag. These commands start a real Uvicorn child on a reserved127.0.0.1port, issue actual HTTPX TCP requests and gracefully stop only that owned child. The controller never uses TestClient/ASGITransport. No new worktree or paid model call is created.

```powershell
conda run --no-capture-output -n adaptive-rag python -B -m research.docs.agent_engineering_upgrade.p4_api_e2e.runner --probe UNIQUE_STARTUP_RUN_ID
$env:P4_E2E_RUN_ID = 'UNIQUE_HTTP_RUN_ID'
conda run --no-capture-output -n adaptive-rag python -B -m pytest research/docs/agent_engineering_upgrade/p4_api_e2e/test_real_http.py -q --basetemp scratch/UNIQUE_TMP --junitxml=research/docs/agent_engineering_upgrade/p4_api_e2e/evidence/UNIQUE_RESULT.xml
Remove-Item Env:P4_E2E_RUN_ID
```

Each Run ID is exclusive and cannot overwrite a previous directory/database. The42scenarios contain55recorded API requests in the final matrix; startup readiness polling and owned shutdown are lifecycle traffic, not additional scenario passes. The trusted-identity scenario deliberately appears as pytest skip and matrix BLOCKED. It must never be counted as PASS.

worker.py creates explicit `_env_file=None` testing Settings, a private file SQLite DB and standard synthetic seed via the real container, then explicitly installs ControlledLLM. The business Graph, Session/M2, retrieval and tools remain real application implementations. The controlled provider consumes actual prompts/tool results/documents; it has no test-ID or Gold lookup. Generic fault types are supplied only by the test worker's local request middleware. No test-only route/header is installed in app/main.py or production routers.

Runtime manifest declares actual provider, engine URL, PID, interpreter, M2, in-memory/hash/lexical retrieval configuration and deliberate degradation. Keys/remote DSNs are absent, MCP and external tracing are disabled, and only loopback connections are allowed by the socket guard. The guard is not a universal network sandbox; explicit settings and sanitized child env are essential protections. Experience mode stays off. No real dense/reranker, Redis, Qdrant, PostgreSQL or DeepSeek validation is claimed.

Artifacts: process.json/source hashes; startup.json; request_NNN_CASE.jsonwith HTTP/SSE payload, headers, tool events, local spans and before/after SQL snapshots; events.jsonl; matrix_results.json; owned_cleanup.jsonand shutdown.json. The live SQLite file is Git-ignored; portable SQL snapshots preserve state evidence. stdout/stderr logs remain local diagnostic files. All records use known synthetic fixtures, not real user or production business data. No hidden model reasoning is captured.

The deliberate trace_error scene proves capture errors do not replace business results. Its local trace is explicitly unavailable, capture-status header is ERROR and shutdown counters confirm the failure; it is not presented as a complete trace. For normal scenarios require source/trace/tool evidence. SSEheaders arrive before the full body, so per-case shutdown counters are authoritative for any late capture loss.

If interrupted, read RECOVERY.md, actual Git/status/state and process/cleanup files first. Do not blindly start a second worker against an existing DB/Run ID. Only stop a still-owned task process after checking its recorded command/start ownership; never enumerate/kill all Python/Uvicorn services. Failed startup and initial41scenario results remain under A0_01and A1_01; repaired final evidence is A2_final_01. No non-idempotent action or historical paid request is automatically repeated.

Test contract corrections are versioned by Git: initial A1expected cancellation refusal before confirmation and prohibited legitimate read fallback; final contract actually confirms the ineligible write, requires business rejection/no mutation, and verifies failed primary read plus only legitimate policy fallback without invented order facts. Historical P0–P3Gold and initial failed results are unchanged. Corrected fixture policy delivery is not an improvement in a real model.
