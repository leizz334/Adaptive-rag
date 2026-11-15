# Real DeepSeek business acceptance execution plan

Goal: verify existing real8001 Agent within newly authorized20HTTP/50000effectiveTokens/.05USD while preserving original ledger and Offline8000.

Scope: user D1-D4 specification. No new feature, worktree, history replacement, Key disclosure or Experience frontend.

- [ ] D1: snapshot containers/volumes, private Key readability and mode, original ledger rows/fingerprint/hash, official model/price bounds. Test a copy with requested cumulative limits: direct mismatch must fail safely. Record scope clarification for missing topup mechanism.
- [ ] D2: use current verified local image containing settlement, start existing Real dependencies and replace only Real API through Compose with authorizationfalse and original limits; no initialize/seed. Verify readiness/auth/provider/source hashes. Offline containers/DB unchanged.
- [ ] D3: only after all durable new-budget gates proven, execute sequential order, same-session Memory, private synthetic RAG, nonexistent order, synthetic HITL confirmation/idempotency. Capture ledger before/after and Trace per scenario. No blind retries; remaining scenarios BUDGET_BLOCKED/NOT_RUN if admission fails.
- [ ] D4: relevant pytest/HTTP-SSE/browser regressions without incidental paid requests. Disable gate and/or stop Real services; verify original data/Key/Offline untouched. Chinese report, task commits and ordinary Push exact remoteHEAD.

Review focus: immutable old charges; concurrent sends cannot overrun phase limits; restarting retains usage; frontend/browser cannot accidentally create extra paid calls; final server cannot remain paid-enabled.

Operational actions need no extra approval. Any app-code fix requires a minimal failing test first. Budget-extension behavior is currently outside scope pending explicit user answer.


## Approved continuation 2026-11-15

- [ ] BG: additive authorization and attempt mappings preserve original metadata fingerprint and all historical reservations/settlements. `AttemptLedger(..., authorization_id=None)` supports explicit admin `authorize(id,max_requests,max_usd,max_tokens=None)`, exact duplicates idempotent, conflicts/overlaps/uncertain blocked, permanent close; `authorization_snapshot` separate from lifetime counts; `check_capacity(payload)` under the same durable admission rules. Legacy sends cannot bypass any grant. Model/prices original and immutable.
- [ ] Runtime: optional server-only REAL_AGENT_AUTHORIZATION_ID selects existing grant (never creates). Runtime readiness uses check_capacity, not old cumulative caps. Compose passes only ID; Key remains private. TDD config parsing and actual MockTransport no-old-token-cap behavior.
- [ ] Revalidate original ledger/env/Offline and take fresh read-only backup. Build latest API image without touching8000. Apply explicit grant ONLY after mocks/review pass, select ID, enable paid. New20HTTP/.05USD and no cumulativeToken cap; each outbound payload still reserves full conservative worst-case tokens*price.
- [ ] Run one-shot sequential actual order/Memory/RAG/negative/HITL scenario driver, retaining started markers/evidence and never blind replay. State references may cause extra model sends;20 hardcap remains even if some cases NOT_RUN.
- [ ] Close server paid gate and explicit grant; no sustained paid access. Run no-paid browser/regressions; preserve environment/history/volumes; report real results, scoped commits, ordinary Push exactHEAD.

Files: app/providers/paid_budget.py (and optional focusedbudget_authorization module), tests/unit/test_budget_authorization.py; app/demo/real_dev.py and tests/unit/test_real_agent_dev.py; compose.agent-dev.yml; current phase acceptance/environment/regression scripts, state and report. No other feature or frontend changes planned.
