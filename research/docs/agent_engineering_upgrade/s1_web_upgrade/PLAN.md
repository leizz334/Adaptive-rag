# S1-Web Implementation Plan

Goal: Upgrade existing React/TypeScript/Vite into an authentic Agent workbench for interview demos.
Architecture: Reuse current components/API and original Agent/RAG/M2. Minimal authenticated read-only workbench API and tenant document listing; no new UI/state framework. Browser auth stays memory-only, identity from server /me. Synthetic controlled-LLM demo server has hard network/paid denial.
Tech Stack: React19/TypeScript/Vite, FastAPI/LangGraph, existing PostgreSQL/Redis/Qdrant, Vitest and Playwright Chromium.
Spec: User S1-Web requirements and AGENTS.md; continuous native execution already authorized, no design approval loop.

## Architecture decisions (preserve verbatim)
- Reuse the current chat/sidebar/Markdown/SSE decoder. Bearer tokens entered as explicitly local development credentials, held only in memory; server verified /me subject binds local memory-only conversation state. No hardcoded token, fake login, or client tenant identity.
- Session switching aborts in-flight UI requests; timeout/network/SSE errors carry safe error codes and trace IDs. No automatic replay of uncertain mutations or LLM requests. Cancellation is transport cancellation, not rollback of committed work.
- Private document list/read/write/search use the existing authenticated subject and private retriever. Add bounded own-document list only; browser text-file upload maps to existing JSON content endpoint. No new public sharing or trust in user_id/tenant_id.
- Trace data must be actual backend execution, authenticated and session-owned, bounded with TTL. Only allowlisted numeric metadata/node/tool names and safe business summaries, no raw State/prompts/credentials. Missing timings/features say unavailable. Trace cannot be addressed by caller-controlled x-trace-id to overwrite another run.
- HITL uses durable existing confirmation and idempotency. UI cancel must actually revoke the pending proposal, expiry and duplicate results shown. Confirmation never synthesizes a fresh action id to retry uncertain requests.
- Experience is an explicitly historical read-only synthetic S1-EX snapshot, with provenance and NOT_ESTABLISHED/NOT_ASSESSED labels. No Active toggle, no claim of online learning or human approval. Current production mode stays off/shadow.
- Browser demos run real Chromium against real FastAPI and owned real PG/Redis/Qdrant. Controlled LLM only, no external inference; mocks are unit-only. All new evidence uses fresh directories; old raw/Gold/ledgers unchanged.

## Web-0 audit and answer reliability
- [x] Audit frontend/API/auth/SSE and save API matrix.
- [x] RED current requested item fields/refund absence; minimal answer coverage/fallback fix; targeted GREEN.
- [x] Record results/state and commit Web-0.
## Web-1 core workbench
- [x] RED API bearer/error/abort/protocol tests; memory-only identity/session management and robust SSE/HTTP client.
- [x] Credential status, transport mode, timeout/cancel/error UI; markdown preserved; tests/build/state/commit.
## Web-2 private knowledge and HITL
- [ ] RED authenticated own-list/cancel ownership tests; minimal endpoints; KB CRUD/upload/search + citation excerpts + HITL states.
- [ ] Cross-user/auth/replay tests; build/target tests/state/commit.
## Web-3 execution
- [ ] RED bounded authenticated trace ownership/sanitization tests; capture real execution summary without raw trace leakage.
- [ ] Collapsible actual graph/planner/tool/RAG/memory/timing view; no fabricated steps; tests/state/commit.
## Web-4 Experience
- [ ] Read-only committed synthetic snapshot with provenance/version/conditions/review/Shadow and actual E0/E1/E2 comparisons.
- [ ] UI tests/no Active and honest labels; state/commit.
## Web-5 verification and delivery
- [ ] Guarded fresh real services + controlled worker, real browser3scenario E2E incl multiuser negatives; preserve RED before fixes.
- [ ] Full frontend tests/ts/build, backend pytest/Ruff/Mypy/pip/legacy214, preservation/secrets review.
- [ ] Final docs/README/demo/recovery; checkpoint/normalpush/exactHEAD; STOP no S2/S3/P5/Active.

## Review Focus
Credentials never persisted/logged, old local history not exposed to another subject; expired credentials clear views. SSE error/EOF/timeout cannot appear as success. Private CRUD and trace id/session guessed by other users must return opaque refusal. HITL cancel/confirm races preserve server atomicity. Snapshot history and absent telemetry clearly labeled, no fake live steps.
