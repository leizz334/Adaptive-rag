# P4 E2E test plan — PLANNED / NOT_RUN

This document is the authorized P3-B3 planning output. **P4_STARTED=NO.** No new P4 process, dependency deployment, production migration or live model experiment is executed here. Existing regression tests do not imply real-dependency E2E coverage. P4 requires a separate user instruction.

## Entry gates and frozen inputs

- Verify delivered Git HEAD/remote, clean isolated worktree, Python/Conda lock and test artifacts. Preserve unrelated user edits and human review files. Freeze application/Prompt/tool/scorer/data SHA256 before runs.
- Use separate synthetic tenant/user identities and disposable databases. Client-supplied ChatRequest.user_id is not authenticated identity. Document or supply trusted test authentication before making cross-user authorization claims; no production M3 or experience Active.
- Record known limits: new sandbox E0/E1/E2strict10/12, unestablished experience benefit, partial7answer human calibration, broader answer semantics unknown, Owner refusal wording annotation issue. Treat B2independent12and all former holdouts as consumed regression data.
- Review/freeze new answer and multi-goal Gold independently. Accept multiple legitimate privacy-preserving refusal phrasings. Resolve scoring disputes in a new version while retaining all old scores. Human labels, time, identity, reasons and disagreements must be explicit; never copy AI labels into human cells.
- Explicit settings and test DSNs only; fail if a target resolves to production. Production keys, user records, traces and business endpoints are excluded. External raw tracing disabled; local redacted spans only. Use system credentials through environment/secret store, never committed files.

## Test layers

| Layer | Execution to plan | Primary evidence and acceptance |
| --- | --- | --- |
| API E2E | Start actual FastAPI/Uvicorn process on loopback with isolated fixture DB; make real HTTP requests, not only ASGI mocks | readiness/liveness, schemas, request IDs/errors, complete response/SSE, state snapshots; no unexpected network/dependency fallback |
| Dependency integration | Disposable project-supported PostgreSQL, Redis and Qdrant services; local retrieval/embedding path with explicitly pinned dependencies | actual session transactions, TTL/rate limiting, vector indexing/filtering, restart/failure and cleanup; report unavailable services NOT_RUN |
| Real LLM E2E | Configured DeepSeekProvider against synthetic HTTP API requests, same source/seed/scorer per controlled arm | request-level durable ledger, public final answers, per-turn tools/state, factual assertions, coverage, unknown semantics and independent human review |

Run layers sequentially. An offline/mock pass cannot substitute for a real socket, actual service, real embedding/reranking or paid-provider pass. Local embedding cold start and warm latency must be reported separately. MCP remains disabled unless an explicit read-only synthetic endpoint is provisioned and authorized.

## API matrix

Use the actual configured API prefix and routes from app/api/routes; /metrics is outside the API prefix. Validate behavior against current contracts rather than inventing undocumented HTTP statuses.

| Surface / sequence | Coverage |
| --- | --- |
| GET /health, /ready, /capabilities | DB outage/recovery; correct dependency statuses; readiness currently requires DB, so do not equate it with all optional dependencies being ready. LLM ping must not bill a completion. |
| POST /chat | valid single/multi-turn M2, fresh state after external fixture changes, goal combinations, no-tool greeting, policy-only retrieval, entity ambiguity/clarification |
| POST /chat/stream | valid SSE event order, final response parity with ordinary path, split UTF-8/chunks, disconnect/cancellation cleanup, partial/length error, timeout, no write retry after uncertainty |
| Confirm / replay sequence | proposed action → exact human confirmation → at most one synthetic mutation; wrong/expired/cross-user confirmation denied; duplicate idempotency key replays original result without a second write; conflicting payload rejected |
| Owner / Session | another user's order, guessed session, changed user, simultaneous sessions, malicious history/doc instructions, no stored business facts replacing fresh checks |
| GET /tools, /skills | authorized admin success, absent/incorrect admin credentials denied; no secrets in catalog/response |
| Validation / middleware | empty/oversized input, malformed JSON, resource limits, request IDs, API exception taxonomy, request cancellation, trace on/off parity |
| /metrics / local spans | bounded label cardinality, no key/personal/order-content leakage, no external raw export |

Assertions check final public answer, tools, trajectory, business invariants, audit log, pending confirmation and idempotency rows. Distinguish necessary rereads from redundancy. Fresh act_UUID/session/trace handles may differ only at typed proven paths; preserve raw comparisons and never normalize order IDs, authorization, amounts, execution outcomes or answer claims.

## Dependency failure and recovery matrix

PostgreSQL: schema migration on a disposable instance, rollback/restart, committed session consistency, transaction rollback on exceptions, duplicate/concurrent confirmation/idempotency races. Experience storage currently initializes only explicit isolated SQLite; compile-only PostgreSQL evidence is not live compatibility. Any future storage migration must be separately designed/tested before deployment.

Redis: actual ping/reconnect, quota increments and TTL, outage behavior, no experience-primary-store assumption. Qdrant: deterministic synthetic corpus indexing, collection/dimension mismatch, tenant filters, empty recall, stale collection and network errors. Embedding/reranker: pin model/revision, offline versus real/local model paths separately, bound cold starts and cache state. Use a known corpus with independently labeled required passages; record query rewrite→retrieval→rerank→Generate provenance to identify first failure rather than blame memory.

Inject latency, socket disconnect, 429/5xx and malformed/truncated model output with bounded controls in the dependency test layer. For real-provider uncertain dispatch, checkpoint and stop; do not replay a potentially billed request automatically. For writes, reconcile database/audit/idempotency state rather than resending an uncertain action.

## Real DeepSeek protocol and provisional budget

No calls are authorized by this plan itself. On explicit P4 authorization, first verify endpoint/model and current primary-source prices, never expose the API key. Suggested conservative hard caps:80HTTP requests,80,000accounted tokens,US$1estimated, concurrency1, at most12model requests per scene, zero automatic uncertain resend. Apply request reservation before dispatch and stop before any request/group could exceed any cap. Missing usage reserves a conservative bound and blocks further live dispatch. If prices cannot be verified, state that exact cost control is unavailable and use request/token caps; do not claim an invoice price.

Begin with two development tasks to validate capture and scoring, then hash-select up to six independent task pairs within remaining budget. At least one compound policy/live goal, one ambiguous refusal and one Judge/error-limitation scenario. Business operations remain in disposable synthetic DBs behind existing Owner/HITL/idempotency. Experience Active remains disabled; any sandbox injection comparison requires separately qualified experience content and fixed controls. If no qualified lesson or useful safe evidence exists, E2real=NOT_RUN rather than forcing injection.

Freeze code and scoring before new holdout. Do not fix a consumed holdout and call it unseen again. Alternate source-arm order per scene, reset state and M2 per pair, record intentional prompt/config differences. API nondeterminism is explicit; repeat a small subset only if budget permits. Separate model/provider/infrastructure failures from task failures. A failed pilot remains an immutable run; repaired measurement uses a new version/run ID.

## Metrics and exit rules

Report tool/trajectory success, environment invariants, required fresh observations, factual correctness, goal completeness, faithfulness, abstention, overall task success, JSON/Judge/API categories, request/token/cost ledger, mean/P95 task and model latency, cancellation leakage and safe retry counts. Full semantic claims need evidence and calibrated independent human review; unsupported extra clauses remain UNKNOWN/NOT_ASSESSED. Same-model Judge verdict is not external truth.

All required original security tests must pass; unauthorized writes, cross-user leaks, missing HITL or duplicate writes block admission and require rollback. Record every old PASS→FAIL transition, runtime/dependency limitations and scoring disputes. No fixed success-rate target overrides safety or evidence quality. A partial run stays PARTIAL with the real valid denominator. No stage is PASS solely because tools executed correctly.

Produce versioned config, schema/environment manifests, raw request metadata/public responses only, redacted local traces, final answers and snapshots, hashes, scores, failures, human review packet, cost accounting and recovery instructions. Each atomic task receives verified checkpoint/commit. Ordinary push and ls-remote after user authorization; never force-push. Restore disposable services safely within resolved test paths; preserve failed runs and user data. **STOP after P4's separately authorized scope; this P3-B document starts nothing.**
