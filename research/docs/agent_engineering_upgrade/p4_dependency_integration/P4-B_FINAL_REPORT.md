# P4-B Windows checkpoint: trusted authentication and dependency preparation

**PHASE_STATUS = PARTIAL_PASS; execution state = WAITING_UBUNTU.** Windows B0/B1 are verified and delivered. B2/B3 have not run. This is the user-requested handoff boundary, not full dependency acceptance.

## Identity and compatibility

The API now defaults to server-provisioned opaque Bearer credentials, stored as bounded SHA256 digest records with subject, roles, UTC validity and revocation. Both chat paths bind the verified subject before Graph/business dispatch; a conflicting client user_id is rejected. Admin metadata requires a verified admin role. Old x-admin-token cannot bypass required mode. Invalid/missing/expired/revoked credentials fail closed. Existing request/response body shapes and Owner/Session/HITL/idempotency checks remain.

Twenty real Uvicorn/TCP required-auth scenarios pass, including spoofing, cross-user orders/Sessions, admin and SSE. The production dependency is used; no fake principal injection occurs in that matrix. Thirty-three independent route/verifier counterexamples plus19auth unit and5legacy API checks pass together. Test credentials are intentionally public synthetic fixtures; deployment credentials must be privately provisioned by a trusted operator over TLS. This is a small real API-credential scheme, not a user registration/OAuth/human-identity platform. Client credential delivery, TLS and operator subject ownership remain deployment responsibilities; no authentication UI was built.

The historical P4-A fixture explicitly uses legacy_test only with app_env=testing. Startup forbids that mode in development/production. Its old authentication probe remains an unchanged historical BLOCKED/skip; it is not relabeled. Existing fixture compatibility does not count as trusted authentication.

## Real dependencies prepared, not executed

The isolated Compose configuration reuses the existing PostgreSQL16alpine/Redis7alpine/Qdrant1.12.5 image choices, unique project-scoped containers/volumes, private generated credentials and loopback ports. Docker mutations use only the local Unix socket with sanitized interpolation environment. Guard checks reject foreign exact-name volumes, partial/misbound service endpoints and unowned resources. No Docker services were started or stopped on Windows; Docker is absent from the current PATH.

Twelve B2 tests are prepared for real migrations, persistence, transactions, concurrent idempotency, cache/TTL/limiting, Qdrant retrieval/filter/index/errors and owned restart recovery. Fifteen B3 actual-dependency HTTP/SSE scenarios use two Uvicorn processes, required authentication, shared SQL-backed M2, RAG/tools and controlled model output. They require actual PostgreSQL/Redis/Qdrant backends and refuse startup memory degradation. Cold RAG additionally requires successful vector spans and Redis key/TTL proof. HTTP backend-outage API acceptance is explicitly deferred for B3 implementation/execution.

The existing sync-only Alembic environment failed on async URLs. Its minimal async/run_sync/supplied-connection adaptation passes a real isolated SQLite upgrade→base→head cycle and PostgreSQL DDL compilation. Historical migration bodies remain unchanged. A destructive initial roundtrip now requires a fresh empty owned DB; a successful marker makes resume upgrade-only. PostgreSQL runtime compatibility is still NOT_RUN, never inferred from SQLite.

Redis AsyncMock and Qdrant local :memory: roundtrips verify only local driver contracts. Twelve independent ownership/migration counterexamples pass. Eight local HTTP-evidence/concurrency false-pass controls pass; independent review closes all identified preparation findings. Source review and doubles do not validate actual Docker behavior or process cleanup on Ubuntu.

## Verification and evidence

- Full application + historical helper + real TCP suites: **794passed,0failed/errors,28skipped**.27are pending Ubuntu service/API cases;1is the historical P4-A legacy auth probe. No skipped test is counted as PASS.
- Final required-auth TCP matrix:20/20. Final legacy matrix:41PASS/0FAIL/1historicalBLOCKED. Providers are controlled/mock, database SQLite; these are not real-dependency or DeepSeek results.
- Fresh214scripted legacy service cases: original80=80/80, old16=13/16, formerDevelopment30=30/30, formerBlind33=33/33, P2-SDevelopment24=23/24, P2-SHoldout30=22/30,long1/1. **Zero previous strict PASS→FAIL regressions.**
- Ruff check and format--check pass; Mypy150source files pass. One existing LangGraph pending-deprecation warning remains.
- Inventory checks2240prior tracked files,20root user files and edited human CSV. Only10explicitly authorized prior source/test files change; original reports/Gold/raw evidence and old task namespaces/progress prefix are preserved. New auth code/tests/artifacts are separate. Root user modifications and .env remain untouched. Export secret scan passes without recording secret values.

Initial failures remain in evidence/ and FAILURE_RECORD.md. The first expanded run785PASS1FAIL28SKIP exposed an old mocked P2-Q fixture that assumed Settings was unchanged. It now freezes the actually unchanged provider base interface; the original paid harness's source guard, old Gold and experiment results are unchanged. A subsequent792PASS run preceded two additional corrupt-event counterexamples; the final fresh suite above includes them. No test ID/Gold rule, Owner check or HITL budget was weakened.

Exact source hashes/configuration and dataset group results are in validation.json, startup manifests, JUnit, independent review and immutable runs. Compatibility rerun artifacts use new IDs under p4_api_e2e/runs/20261110_B1_legacy_http_*; original P4-A records are unchanged. Required-auth and214service runs are in this phase. Repeated diagnostic executions are not independent quality samples. Private DB/log/config files are not synchronized or committed.

## Outstanding and Ubuntu recovery

Real PostgreSQL/Redis/Qdrant/API E2E, actual service restart recovery and distributed HITL/idempotency are **BLOCKED_WAITING_UBUNTU / NOT_RUN**. Repository read-then-insert idempotency and process-local pending confirmation remain known risks with ordinary failing acceptance probes prepared; no Windows result certifies them. Redis outage fail-open is the existing documented availability policy, not strict throttling/authentication. Qdrant native filter checks do not claim application tenant vector isolation. Resolved image digests and actual Docker/package versions must be captured on Ubuntu.

Follow UBUNTU_RUNBOOK.md after verifying the pushed branch/commit. Generate new private credentials/DSNs locally, never copy .env or temporary DBs. Keep first failed evidence, repair only confirmed defects, checkpoint B2 then B3 and perform full final regression. No completed paid operation exists to repeat: **new paid model HTTP=0; billed tokens=0; cost=US$0**. External tracing and Experience Active remain off.

Windows B0 commits fdef173/146311c; B1/delivery exact hashes are recorded in state/Git/evidence/delivery.json and the final response. Ordinary push only to the authorized repository and codex/p4-dependency-integration. On network failure keep commits and use `git push origin HEAD:codex/p4-dependency-integration`; never redo tests merely to push. **PAUSE WAITING_UBUNTU; no P4-C/D/E.**

Windows B1 checkpoint `6924c5dfc37c945eb55b870c13a83b2d46929cd4` was normally pushed and verified by exact `git ls-remote` equality. Final delivery metadata follows this checkpoint; the final response records its actual remote-verified HEAD. The user's edited CSV is the only remaining dirty file, byte-preserved and excluded from commits. Both final owned TCP workers exited gracefully with code0. **WAITING_UBUNTU.**

## Ubuntu continuation completed (2026-11-11)

The Windows handoff above is preserved as historical evidence. Authorized Ubuntu B2/B3 now pass:13real dependency tests and20real API/recovery scenarios;final full829PASS0FAIL1historicalSKIP,Ruff/Mypy/pip PASS,legacy2140regressions. Actual idempotency race and process-local confirmation repaired. See [UBUNTU_FINAL_REPORT.md](UBUNTU_FINAL_REPORT.md) for first failures,minimum fixes,coverage limits,ownership and final delivery. No paid/Active/P4-C.

## Delivery blocker (actual final verification)

Local B2 `36ecfe1eaa133014b7d90af4835b4e26a6eafa53` and B3 `b5a5b6f0cbbeb476265a604a28edcb39c6486c7e` are committed. Normal push failed because this Ubuntu host has no GitHub credentials, credential helper/store, gh login, token environment or SSH identity. Read-only ls-remote still reports `11c81934e83b6a8930e82794000d6a99f27dc966`; remote equality is **NOT achieved**. B2 is complete; B3 validation passed but its full task retains passes:false because delivery is required. Final local metadata checkpoint follows. Authenticate locally through a trusted Git/SSH flow, then push and verify HEAD; never send credentials in reports or repeat completed experiments. All owned test services are stopped and volumes retained. No P4-C.
