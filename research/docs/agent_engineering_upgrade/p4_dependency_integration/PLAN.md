# P4-B two-stage implementation plan

> Coding Agent continuation; Initializer is not rerun. Execute B0/B1on Windows in the fixed existing worktree, commit/push/verify, then PAUSE until the user explicitly restores this branch on Ubuntu for B2/B3. User continuous-execution and no-new-worktree instructions override extra skill approval/worktree gates.

**Baseline:** verified local/remote7ee14234299b640e733c7099816f3a7ed7e4dc0a. Existing path D:/Code/Adaptive-rag/.worktrees/p3-experience-validation; new branch codex/p4-dependency-integration. Edited review CSV remains byte-preserved/unstaged. No paid model or Experience Active.

## B0 trusted server credentials

**Decision:** provision high-entropy opaque Bearer credentials out of band; keep only SHA256digests with server-controlled subject/roles/UTCexpiry/revocation metadata. This uses standard-library randomness/hash/constant-time checks and no OAuthplatform or unreviewed custom JWTprotocol. Registry is bounded, strict and fail-closed. Possession authenticates the operator-provisioned account, not a federated/human identity provider. TLS and secure provisioning are deployment requirements. Hash registry reload/revocation takes effect on process restart; per-request expiry always applies.

**Alternatives:** client user_idor proxy headers alone do not establish trust and are rejected. A new full OAuthplatform is outside scope. The selected registry fits small controlled deployments; it is not a large account-management service.

- [ ] Append B0–B3task state and preservation inventory, without overwriting old namespaces/evidence.
- [ ] REDtests for missing/forged/expired/revoked/duplicate credentials, role bypass, body-ID spoofing and strict parsing; implement app/core/auth.py plus explicit Settings/auth-mode guards.
- [ ] Bind both chat and SSEpayload identity through a FastAPIdependency before service/Graph; reject conflicting user_id, preserve body/response shape and all Owner/HITL/idempotency. Public health probes stay public. Admin requires verified admin role in required mode; legacy x-admin-token is only for explicit legacy test configuration.
- [ ] Production/development default auth required. Explicit legacy_test is legal only with app_env=testing. Update old API fixture helpers explicitly; never silently exempt every testing environment. No experience identity sharing or new Memory layer.
- [ ] Actual Uvicorn/HTTPrequired-auth matrix with synthetic server-provisioned credentials proves forgery/Session/Owner/expiry/SSE/admin behavior using the production verifier. It must not inject a fake principal or count legacy tests as trusted authentication.
- [ ] Independent security review/counterexamples; targeted verification, state and task commit.

## B1 dependency preparation on Windows

- [ ] Inspect/reuse existing Compose images and DB/Redis/Qdrant adapters. Add isolated Compose profile with unique project/volumes, loopback ports, labels and local private config; no existing container/volume names or destructive prune/down-v defaults.
- [ ] Prepare real PostgreSQLmigration/persistence/rollback/concurrent-idempotency tests, Rediscache/TTL/rate-limit/outage/recovery tests, Qdrantupsert/filter/index/dimension/error tests. Real service fixtures fail or skip explicitly when not authorized/available; mock/local results do not replace them.
- [ ] Fix only demonstrable preparation defects with RED/GREEN (e.g. async Alembic support), preserving migration history. Do not preemptively rewrite distributed HITL/idempotency before actual Ubuntu failure evidence.
- [ ] Prepare required-auth real-dependency UvicornHTTP/SSE/multi-worker test path with controlled LLM and explicit backend assertions; configured Redis/Qdrant failure must not silently count as successful integration fallback.
- [ ] Windowsunit/mock/SQLite/local-contract checks + full pytest/helpers/Ruff/Mypy/legacy regression. Docker-backed tests stay BLOCKED/NOT_RUNfor Ubuntu. No services/paid DeepSeek in this stage.
- [ ] UBUNTU_RUNBOOK.mdwith exact commit recovery, environment/Docker official setup references, safe isolated service ownership/restart/cleanup, request-level evidence and execution order B2→B3. Never synchronize private config/temp DB/user files.
- [ ] Task checkpoint/commit, normalpush/lsremote, PAUSE WAITING_UBUNTU. Do not start B2/B3or P4-C/D/Eon Windows.

## Deferred Ubuntu B2/B3

Verify pushed HEAD, Python/Docker/Compose and private test config; start only isolated owned services. Run real dependency suites, restart/persistence/failure scenarios and actual API/SSEauth/Memory/RAG/tools/HITL/concurrency. Save first failures before minimal fixes and fresh-run regressions. Mark missing services BLOCKED, not mocked PASS. Final full checks, task commits and safe push/remote verification, then STOP. A known design risk is in-process pending confirmations across workers; prepared tests must expose it rather than claim distributed confirmation readiness.

**Review focus:** credential parsing/duplicate headers and role boundaries; default fail-closed modes; no token exposure in traces or DB; real backend versus silent fallback; isolated DSN/project ownership before mutations/restarts; replay/idempotency under actual concurrent transactions; Windowspass evidence must not imply Ubuntu service validation.
