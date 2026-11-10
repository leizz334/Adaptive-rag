# P4-A FastAPI real HTTP E2E

**PHASE_STATUS=PARTIAL_PASS.** Real Uvicorn/TCP API and SSE paths are validated with a controlled model and private SQLite. Final42scenarios:41PASS,0FAIL,1BLOCKED. Trusted authenticated anti-impersonation is not implemented and cannot be claimed PASS. Three application defects and three harness defects are repaired; historical evidence and the user's edited review are preserved. No new worktree, paid DeepSeek request, Experience Active or later P4phase is started.

## Runtime and scope

Local/remote P3-Bbaseline586d0e01381d69bdc1653e5563e3ce48e9b82219was verified before branching in place. Existing worktree remains D:/Code/Adaptive-rag/.worktrees/p3-experience-validation, branch codex/p4-api-e2e. No stash/reset/worktree creation. Original human CSV SHA2569ae24fe60c2d75498a4429cf79e03f5a0f3955380cd51d6064fec0fa51ad5aa7remains the only expected uncommitted user change.

Conda adaptive-rag, Python D:/MiniAnaconda3/envs/adaptive-rag/python.exe; installed FastAPI0.115.14/Uvicorn0.32.1. A separate HTTPX process makes actual TCP requests to the owned loopback Uvicorn process. Final run20261110_A2_final_01uses PID20660and55recorded API requests over42scenarios; startup/stop traffic is lifecycle overhead, not extra passes. The child exits0through owned graceful shutdown. Across the phase, only the six recorded task-owned children are stopped/observed finished, including the initial failed startup. No other service is terminated.

The application routes, SessionRepository/M2, LangGraph, actual hybrid retrieval, Planner, SQLbusiness tools, permissions, Generate/Judge and response serialization execute in the child. Only LLMoutputs/faults are explicitly controlled. Runtime manifests identify ControlledLLM, its underlying scripted policy, actual SQLite engine URL, standard synthetic seed, in-memory vector store and intentional hash/lexical retrieval backends. No real dense/reranker model, Redis, Qdrant or PostgreSQLintegration is claimed. /capabilities reports offline/degraded configuration; the additional manifest declares the fixture instead of implying a real DeepSeek provider.

Explicit Settings(_env_file=None), sanitized child env, empty paid-provider keys/remote DSNs, MCPoff and local-only tracing prevent ambient production configuration. Worker denies non-loopback connect/connect_excalls; Windows asyncio loopback is allowed. This is not an OSnetwork sandbox; explicit settings remain essential. Final evidence records0non-loopback outbound attempts and0paid model calls. All business writes concern seeded synthetic orders in a new run-private SQLite file.

## API matrix and evidence

| Area | Final result | Evidence boundary |
| --- | --- | --- |
| /health, /ready, /capabilities | PASS | Real HTTPstatus/headers/backend/DBconsistency; optional degradation declared |
| /admin/tools and invalid admin token | PASS | Existing synthetic admin-token boundary; not a general user login test |
| Input validation | PASS | Empty/oversized/type-invalid payloads return422stable envelope; no DB/tool mutation |
| /chat reads | PASS | Order state/amount/items, shipment, refund state, product detail/inventory/warranty; response facts, actual tools/args, state and local spans |
| M2multi-turn/summary | PASS | Pronoun, explicit target change, persisted summary recovery and fresh lookup; independent session does not inherit history |
| RAG and compound queries | PASS bounded fixture | Actual passage retrieval/citations and order+shipment/amount/policy evidence delivery; not a real model semantic or complete policy eligibility claim |
| HITL/idempotency | PASS single process | Proposal does not write; invalid confirmation denied; confirmed eligible cancellation commits once; duplicate key leaves business/audit/idempotency state unchanged; confirmed shipped cancellation is rejected |
| Claimed Owner/Session isolation | PASS bounded | Different declared user cannot reuse session/read protected order; no trusted principal inference |
| Trusted identity authentication | BLOCKED | Public user_idis client-controlled; no login/principal binding or anti-impersonation proof |
| Generate/Judge/tool faults | PASS fault controls | Provider API/timeout/truncation and primary-tool failure handled without invented model configuration or order facts; legitimate policy fallback allowed |
| HTTPunexpected error | PASS |500INTERNAL_ERROR, transaction rollback, no unsupported success |
| SSEnormal/guardrail/error | PASS | Real event order, tokens equal final answer, refusal, typed late error→done with no answer/success; status200after headers is transport status, not task success |
| SSEclient disconnect | PASS tested read interruption | Real socket closure cancels graph/model, closes spans/iterator and rolls back incomplete turn; does not imply rollback of an already committed write |
| Trace sink failure | PASS isolation control | Injected sink error leaves HTTPanswer and DBresult intact; trace is explicitly unavailable/ERROR, not silently declared complete |

Each request artifact records HTTP/SSE body, headers, transport errors/latency, before/after SQL tables and local tool/span events. The deliberate capture-failure case is the explicit exception: it proves fail-open instrumentation, and its14dropped capture attempts are reported through ERRORheader/shutdown counters. All normal final-run capture counters are zero. Source hashes for149application files, worker and matrix match the final runtime; no source changes occurred during that run. No hidden reasoning or real user/business data is captured/exported.

Full pytest includes existing TestClient/ASGImocks as regression, while the separate phase directory is **real TCP HTTP**. Those evidence types are never relabeled. The controlled fixture's scripted SUPPORTEDis not an independent semantic judge. Real DeepSeek/real-language quality and real external-dependency tests remain NOT_RUNby scope.

## Failures and fixes

Initial startup A0_01failed before APIinitialization because an overbroad test socket guard blocked Windows asyncio's loopback self-pipe; its original worker snapshot/log/cleanup remain. A0_02passes four real HTTPstartup probes and closes only its owned process.

Initial A1_01has35PASS/5FAIL/1BLOCKEDover41scenarios. Its raw files and source commit56cca47596db5c9679a99abde4be8cb4ca98a509remain immutable. The repaired42scenario matrix adds one trace-failure control. Five original failures are not falsely counted as five production fixes: two are application failures, one is a model-fixture omission, and two are new-test contract mistakes. An additional actual settings-lifecycle bug and an instrumentation-failure bug were independently reproduced before correction.

Application changes are limited to3files:

- app/main.py: use the app's resolved Settings object in its lifespan rather than resolving global settings again. Explicit app configuration now reaches its container/DBand avoids unintended dotenv parsing in the worker.
- app/agents/goals.py: recognize the generic refund-status read expression; fresh refund observations are no longer omitted for that expression. No order/test-ID rules or writes are added.
- app/api/routes/chat.py: after SSEheaders, report bounded typed error/done events instead of silently terminating. Preserve AppErrorcategory, hide unexpected exception detail, propagate cancellation and never emit an answer/success for an error.

Harness fixes are Windows loopback handling, grounded policy excerpt delivery and fail-open bounded event capture. Test contract corrections require actual confirmed business denial and allow legitimate fallback while forbidding unsupported facts. See P4-A2_FIXES.md and independent reviews for exact causality/RED→GREENevidence. No P0–P3Gold, scoring thresholds or original result is modified.

The final reviewed matrix further requires a failed cancel_order/business_rejected event, no pending action or false '已取消' answer, and unchanged business/audit/idempotency tables; failed primary get_order plus only allowed successful policy fallback cannot masquerade as current order data. These stronger assertions pass real HTTPin the final run.

## Regression and preservation

Full application/helper+real HTTPsuite: **670pytest passed,0failed/errors,1skipped**. The skip is the explicit trusted-authentication BLOCKEDscenario, not a PASS. Final strengthened real HTTPmatrix separately **41passed/1BLOCKED**. Ruff check/format and Mypy149source files pass. One existing LangGraph pending-deprecation warning remains. The final checks script's initial unused-variable Ruff failure is retained and corrected in separate style evidence; it was not a model/APIfailure.

Fresh214legacy strict cases preserve original80=80/80, old16=13/16, formerDevelopment30=30/30, formerBlind33=33/33, P2-SDevelopment24=23/24, P2-SHoldout30=22/30and longwindow1/1. **REGRESSION_COUNT=0**for old strict PASS→FAIL. Safety suites cover Owner/Session/HITL/idempotency, stale-evidence and Judge/fallback/SSEcleanup paths. Seven independent counterexample tests and two additional settings/cancellation probes support review; their bounded scope is disclosed.

Audit checks1,937baseline tracked files: exactly the3authorized application sources change; historical report/experiment/Gold changes0. All20original root user files, the edited human CSV, old task namespaces and progress prefix are preserved. No actual credentials are found in phase outputs. SQLite/log runtime files remain local/Git-ignored; portable JSONstate evidence is committed. No production migration or original business file is overwritten.

## Limits, delivery and recovery

**PARTIAL_PASS**reflects missing trusted user authentication. No general production isolation/authentication certification, multi-worker/restart confirmation guarantee, arbitrary semantic answer correctness or post-commit write rollback claim is made. Cancellation proposal wording still optimistically says '确认后将取消' before eligibility is known; actual confirmed business refusal is safe, and that wording is not claimed fixed. Broad real dependency/LLM/performance evaluation belongs to separately authorized later work.

A0checkpointd12575c; initial A1evidence56cca475; A2source repair9abc63c8a157811ea964b5a4bfdb8f08b71622f3; A1revalidation6401419dcacb7c69feeae16dcbd7af288a6a644a. Full hashes/state/report delivery are recorded in feature-list.json, progress.txtand evidence/delivery.json. README.mdcontains repeatable commands and evidence interpretation. RECOVERY.mdis authoritative for checkpoints; never rerun old Run IDs or historical paid calls.

Ordinary push targets authorized https://github.com/leizz334/Adaptive-rag.git branch codex/p4-api-e2e, followed by git ls-remoteverification. The user's edited review CSV stays uncommitted. After verified final metadata delivery, **STOP**. **EXPERIENCE_ACTIVE_ENABLED=NO; P4_B_STARTED=NO; P4_C/D/Eare not started.**

```ini
PHASE = P4-A
FASTAPI_STARTUP = PASS
HTTP_E2E = PASS_AVAILABLE_SCOPE
SSE_E2E = PASS
MEMORY_E2E = PASS_M2
RAG_E2E = PASS_DECLARED_SYNTHETIC_BACKENDS
TOOL_WORKFLOW_E2E = PASS
HITL_IDEMPOTENCY = PASS_SINGLE_PROCESS
OWNER_SESSION_SECURITY = PARTIAL; CLAIMED_SCOPE_PASS; AUTHENTICATION_BLOCKED
E2E_TOTAL = 42
E2E_PASS = 41
E2E_FAIL = 0
E2E_BLOCKED = 1
BUGS_FOUND = 3_APPLICATION + 3_HARNESS
BUGS_FIXED = 3_APPLICATION + 3_HARNESS; 2_TEST_CONTRACT_CORRECTIONS_SEPARATE
REGRESSION_COUNT = 0
PYTEST = 670_PASS; 1_AUTH_BLOCKED_SKIP
RUFF = PASS_CHECK_AND_FORMAT
MYPY = PASS_149_SOURCE_FILES
PHASE_STATUS = PARTIAL_PASS
UNRESOLVED_ISSUES = TRUSTED_AUTH; BOUNDED_MOCK_SEMANTICS; PROPOSAL_WORDING
LAST_COMMIT = SEE_VERIFIED_DELIVERY_AND_GIT
GITHUB_PUSH_STATUS = SEE_DELIVERY_JSON_AND_FINAL_OUTPUT
RECOVERY_READY = YES
EXPERIENCE_ACTIVE_ENABLED = NO
P4_B_STARTED = NO
```

Delivery validation c8a7e3e1864f0c00bd604d8f1486e8568b133c92was normally pushed to codex/p4-api-e2e and matched by ls-remote. Actual task hashes are in state/Git; the final metadata commit follows this verified validation checkpoint. **STOP / PARTIAL_PASS; authentication remains BLOCKED.**
