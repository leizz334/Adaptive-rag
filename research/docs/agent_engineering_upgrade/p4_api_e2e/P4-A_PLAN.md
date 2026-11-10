# P4-A real HTTP E2E execution plan

> Execute A0→A1→A2 continuously with task-scoped validation/state/commits. User's fixed-worktree and continuous-execution instructions override extra skill approval/worktree gates. Initializer is not rerun.

**Goal:** Validate actual Uvicorn/FastAPI HTTP and SSE through the business graph with isolated SQLite, synthetic orders and a controlled model; fix only evidenced defects.

**Architecture:** Remain in D:/Code/Adaptive-rag/.worktrees/p3-experience-validation on new branch codex/p4-api-e2e from verified local/remote586d0e01381d69bdc1653e5563e3ce48e9b82219. Preserve the edited human CSV byte-for-byte and unstaged. A research-only worker starts the real app/container, explicitly replaces only the LLM fixture, seeds a run-private SQLite file, captures local spans/tools/state, and rejects outbound sockets. A separate process HTTP client tests actual TCP loopback traffic. No new worktree, paid call, production connection, Experience Active or later P4phase.

**Approaches:** Existing TestClient/ASGI tests remain regression only. Replacing the Graph/service with mocks would not exercise E2E and is rejected. Use Uvicorn child + real HTTP client and actual Graph/retrieval/business tools; controlled model outputs and test-only fault controls are explicit. No new middleware framework or auth subsystem.

**Files:** worker.py for controlled isolated runtime; runner.py for process ownership/client/evidence; test_real_http.py for actual socket assertions; manage.py for append-only phase state; tests/unit for runner/real defects; reports/evidence/runs for immutable artifacts.

## A0 environment and startup

- [x] Read actual AGENTS/registry/progress/history; verify baseline remote and preserve all old tracked/user files; branch in place without stash/reset/new worktree.
- [x] Append P4-A0/A1/A2tasks. Record actual Conda Python/FastAPI/Uvicorn, routes, settings, SQLite schema/seed and real runtime provider/retrieval backends.
- [x] Build child startup/owned-PID cleanup + real HTTP probes. Explicit test env, no.env consumption or inherited provider keys/remote DSNs. Readiness must not bill. Fail on unexpected database/provider/backend.
- [x] Run startup validation, save evidence/state and commit A0. Capture separately any actual config/lifespan defect for A2.

## A1 real HTTP matrix

- [x] Health/ready/capabilities/admin/input error paths; headers and error contract.
- [x] Single/multi-turn M2 reference binding, same-session changed target, cross-session no-history and claimed-user isolation. Trusted authentication/anti-impersonation is BLOCKED if absent, never infer it from request.user_id.
- [x] Actual RAG passage/citation and graph retrieval; order/items/product/shipment/refund and policy/compound evidence; response facts/tools/database/local trace per scenario.
- [x] HITLproposal/invalid confirmation/correct confirmation/duplicate idempotency/state/audit consistency. Only synthetic writes in private DB.
- [x] SSEevent order/tokens/final/parity; actual client disconnect and task/transaction cleanup; model truncation/API/timeout/runtime faults and tool execution failures. No fake TestClient E2E claim.
- [x] Preserve all failures with first node/root evidence; validate cases/harness, commit A1 evidence without relaxing expected behavior or historical Gold.

## A2 defects, regression and delivery

- [x] Establish RED tests for evidenced bugs; minimal GREEN fixes; preserve initial raw HTTP/trace/state and exact source hashes. No case-ID branches or test Gold in runtime prompts.
- [x] Rerun relevant full HTTP/SSE matrix and all pytest/helpers, Ruff check/format, Mypy. Record BLOCKED/NOT_RUN separately; source compatibility/safety regressions must be explicit.
- [x] Fresh independent code review before final verdict; add counterexamples for important findings. Recheck user CSV/root user files and unchanged P0–P3evidence; stage only phase/fix/tests/state.
- [ ] Final report, environment/run instructions, recovery checkpoints; task commit, ordinary push authorized origin/branch, ls-remote, metadata checkpoint and STOP. Stop only this run's child PID/service; no broad process kill or cleanup of user files.

**Review focus:** settings supplied to create_app versus lifespan settings; SSEerror after HTTP headers; disconnect rollback versus completed write; runtime faults classified distinctly; client identity not authentication; trace capture failure must not alter business execution; no outbound socket or root.env leak.

**Acceptance semantics:** Matrix counts complete scenarios (each may contain several HTTP requests), with immutable request-level records. BLOCKED is not PASS. Scripted final answers verify deterministic evidence delivery only, not DeepSeek semantics. Cross-user trusted authentication is BLOCKED absent a real trust boundary. Partial quality is acceptable; safety is not relaxed to chase counts.
