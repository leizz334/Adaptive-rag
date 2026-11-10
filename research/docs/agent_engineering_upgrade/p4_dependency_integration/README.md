# P4-B Windows preparation and Ubuntu acceptance

Use the fixed worktree and Conda adaptive-rag. No new worktree, production backend, paid DeepSeek or Experience Active is used. B0 implements production credential verification; B1 prepares real dependencies. **Windows stops after B1; B2/B3 wait for Ubuntu.**

- Authentication design/provisioning: [AUTH_SCHEME.md](AUTH_SCHEME.md).
- Actual Windows results and limits: [P4-B_FINAL_REPORT.md](P4-B_FINAL_REPORT.md).
- Ubuntu prerequisites, safe Docker ownership and exact recovery commands: [UBUNTU_RUNBOOK.md](UBUNTU_RUNBOOK.md).
- Task recovery: [RECOVERY.md](RECOVERY.md), parent feature-list.json/progress.txt and actual Git history.

Windows checks are reproducible with fresh names; never overwrite an existing run or evidence file:

```powershell
conda run --no-capture-output -n adaptive-rag python -B -m pytest tests -q
$env:P4_E2E_RUN_ID = 'NEW_LEGACY_HTTP_RUN_ID'
$env:P4B_AUTH_RUN_ID = 'NEW_REQUIRED_AUTH_RUN_ID'
conda run --no-capture-output -n adaptive-rag python -B -m pytest tests research/docs/agent_engineering_upgrade -q
Remove-Item Env:P4_E2E_RUN_ID
Remove-Item Env:P4B_AUTH_RUN_ID
conda run --no-capture-output -n adaptive-rag python -B -m ruff check .
conda run --no-capture-output -n adaptive-rag python -B -m ruff format --check .
conda run --no-capture-output -n adaptive-rag python -B -m mypy
conda run --no-capture-output -n adaptive-rag python -B -m research.docs.agent_engineering_upgrade.p4_dependency_integration.regress NEW_LEGACY_SERVICE_RUN_ID
```

The existing P4-A test matrix keeps its own historical explicit legacy_test configuration; its missing-auth probe remains skipped and is never rewritten as PASS. New required-auth TCP cases are in test_auth_http.py and use the actual production dependency, not a fake principal override. Both suites use controlled model outputs and SQLite. Compatibility rerun raw HTTP evidence remains in p4_api_e2e/runs/20261110_B1_legacy_http_*, with B1 summaries/JUnit in this phase; original P4-A records are unchanged.

PostgreSQL DDL compilation, actual asynchronous SQLite Alembic roundtrip, Redis AsyncMock behavior and Qdrant `:memory:` roundtrip are **local compatibility evidence only**. Twenty-seven service/API tests collect on Windows and skip with an explicit BLOCKED_WAITING_UBUNTU reason. Docker ownership safety tests replace subprocesses entirely; they prove checks/control flow, not an installed Docker Engine. The worker refuses Redis/Qdrant memory degradation on startup; cold RAG additionally requires successful vector spans and Redis cache keys/TTL. HTTP dependency-outage cases still need B3 implementation/execution against actual services; adapter-level outage/restart tests are prepared now.

Private manifests/passwords/DBs/logs are ignored. All committed business traces contain known synthetic fixture data. Public repeated-character auth tokens are deliberately test-only, while the same verifier enforces server-owned subject/roles/expiry. Raw production credentials are never copied. The standalone provisioning CLI must be run privately by a trusted operator, with TLS and credential delivery handled by deployment. No login/OAuth UI or automatic cross-user Experience sharing is introduced.
