# P4-B Ubuntu handoff — continue B2/B3 only

Windows completes B0/B1 and stops. PostgreSQL, Redis, Qdrant and real-dependency API acceptance are **NOT_RUN / BLOCKED_WAITING_UBUNTU**. A green local/mock test is not real-service acceptance. Read AGENTS.md, feature-list.json, progress.txt, RECOVERY.md, P4-B_FINAL_REPORT.md and evidence/delivery.json first. Do not repeat Initializer or old paid experiments. Experience Active remains off; DeepSeek calls are prohibited.

## Restore the verified commit

Use a user-owned Ubuntu checkout. Fetch the authorized repository and compare the branch with the final verified SHA in evidence/delivery.json / the Windows final response. Inspect existing work before switching; never reset/stash/overwrite a user's modifications automatically.

```bash
git status --short
git remote -v
git fetch origin codex/p4-dependency-integration
git ls-remote --heads origin refs/heads/codex/p4-dependency-integration
git log -3 --oneline origin/codex/p4-dependency-integration
# After preserving any existing work, use the local branch that tracks the verified remote.
git switch codex/p4-dependency-integration
git rev-parse HEAD
```

For a fresh checkout, clone `https://github.com/leizz334/Adaptive-rag.git` with `--branch codex/p4-dependency-integration` into a new user-selected directory. No temporary Windows SQLite files, .env, generated credentials or private Docker manifests are transferred. The edited human CSV stays untouched on Windows; validated historical review artifacts already in Git are the portable record. Do not replace them with an empty template.

Check Conda `adaptive-rag` if available (`conda env list`, `conda run -n adaptive-rag python --version`). Create/install the documented Python dependencies only if absent; Python 3.11+ and project dev extras are needed. A standard virtual environment with `python -m pip install -e '.[dev]'` is an alternative on Ubuntu; record the actual interpreter and package versions, do not relabel it Conda. Run commands below from the repository root using the selected environment's Python.

## Docker prerequisites — do not clean existing Docker state

```bash
uname -a
python --version
python -m pip check
docker --host unix:///var/run/docker.sock version
docker --host unix:///var/run/docker.sock compose version
docker --host unix:///var/run/docker.sock ps -a
docker --host unix:///var/run/docker.sock volume ls
```

If Engine or Compose is missing, follow the official [Docker Engine Ubuntu installation](https://docs.docker.com/engine/install/ubuntu/) and [Compose plugin Linux installation](https://docs.docker.com/compose/install/linux/) instructions. These involve host package/privilege changes and are not executed by the Windows preparation. Inspect installed packages and user workloads first; do not blindly uninstall packages, prune, remove volumes or stop unrelated services. Docker socket access is a host privilege; the sandbox wrapper is not protection against a hostile local administrator.

The scripts deliberately use the **local rootful Unix socket** and ignore ambient Docker contexts/interpolation variables. Rootless/nonstandard sockets are not silently supported: mark BLOCKED and review the endpoint guard before adapting it. Do not replace the socket with a remote production Engine.

## Create a new private owned test project

```bash
export EXPERIENCE_MEMORY_MODE=off
export LANGCHAIN_TRACING_V2=false
export LANGSMITH_TRACING=false
export P4B_RUN_LIVE=1
P4B_PROJECT="p4b_$(date -u +%Y%m%d_%H%M%S)"
python -m research.docs.agent_engineering_upgrade.p4_dependency_integration.sandbox prepare --project "$P4B_PROJECT"
export P4B_MANIFEST="$PWD/research/docs/agent_engineering_upgrade/p4_dependency_integration/.private/$P4B_PROJECT/manifest.json"
python -m research.docs.agent_engineering_upgrade.p4_dependency_integration.sandbox up
python -m research.docs.agent_engineering_upgrade.p4_dependency_integration.sandbox ps
```

`prepare` refuses overwrite; it creates a local ignored manifest/env file with newly generated test-only PostgreSQL password, owner nonce and free loopback ports. Do not print/copy/commit its contents. No fixed container names are used. Images reuse existing multi-service choices: PostgreSQL16alpine, Redis7alpine, Qdrant1.12.5. Record resolved image IDs/digests on Ubuntu; these tags alone are not an immutable image lock. Free-port selection can race another process; if startup fails preserve logs and select a fresh project instead of changing an existing user's service.

Before mutation the wrapper checks project/owner labels, exact named volumes, service roles, loopback bindings and configuration hash. `ps` requires all three owned endpoints running on the expected actual published ports, so an unrelated local Redis/Qdrant cannot stand in for a partially started sandbox. `up` waits on PostgreSQL/Redis health; Qdrant must additionally pass the actual client ping. No global prune, down-v, volume deletion or arbitrary DSN interface exists. User-owned preexisting volumes must not be adopted.

## B2: real dependencies and first-failure evidence

Use new evidence filenames/run IDs. Do not overwrite Windows or older Ubuntu results. Store raw private logs locally; export sanitized failures and synthetic state only. Before the suite, preserve `docker ... ps`, image IDs, Python/package versions and public.json (not private manifest/env).

```bash
python -m pytest research/docs/agent_engineering_upgrade/p4_dependency_integration/test_real_dependencies.py \
  -q --tb=short --junitxml=research/docs/agent_engineering_upgrade/p4_dependency_integration/evidence/ubuntu_B2_FIRST.xml
```

Twelve prepared tests exercise real migration metadata, independent-connection persistence, rollback, simultaneous idempotency writes, Redis cache/TTL/rate limit/recovery, Qdrant upsert/filter/index/dimension errors and restart persistence. They are not already passed. The fixture uses the explicit owned DSN, never the ambient Alembic/production URL. Async Alembic handling follows the official [Alembic asyncio cookbook](https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic).

The first migration roundtrip is allowed only on a **fresh empty owned database**; a successful private marker prevents subsequent downgrade/replay. An unmarked nonempty database is refused and preserved. If interrupted before the marker, save evidence and use a new disposable project rather than force-dropping the schema. Never run a roundtrip while an API is using the database. Historical migrations 0001/0002 are unchanged. Business app startup create_all is not counted as migration verification.

The current repository's read-then-insert idempotency behavior is a known concurrency risk; its test remains an ordinary acceptance assertion (not xfail, not loosened). Redis limiter fail-open during an outage is the existing documented availability policy, not authentication success or strict concurrent rate-limit proof. Native Qdrant filters/indexes are tested separately from the public-corpus application's unfiltered adapter; do not claim tenant vector isolation. Capture first failures before minimal authorized B2 fixes, add RED/GREEN checks and checkpoint each verified change. Stop/restart tests target owned services only and restore in finally. On interruption inspect actual service state before resuming.

## B3: actual dependency HTTP/SSE

Proceed after B2 failures are understood and prerequisite fixes verified. No production backend or paid model is involved. The worker requires PostgreSQL + Redis + Qdrant types/pings and refuses in-memory degradation; it replaces only model output with the same controlled scripted fixture. It uses the production required-auth dependency with deliberately public synthetic tokens, M2, Graph/tools and local traces. It is not a test of production user provisioning or DeepSeek semantics.

```bash
export P4B_API_RUN_ID="ubuntu_api_$(date -u +%Y%m%d_%H%M%S)"
python -m pytest research/docs/agent_engineering_upgrade/p4_dependency_integration/test_live_api.py \
  -q --tb=short --junitxml=research/docs/agent_engineering_upgrade/p4_dependency_integration/evidence/ubuntu_B3_FIRST.xml
```

Fifteen prepared scenarios start two owned Uvicorn processes and issue actual HTTPX TCP requests. They cover health, credentials/Owner/Session, shared SQL-backed M2, RAG, compound tools, SSE, bounded model faults, confirmation, sequential and concurrent idempotency. Each run ID is exclusive. HTTP records include final answer, local trace/tool observations and SQL snapshots. Owned Popen children are stopped by private in-memory control token, then exact-child termination only if needed; unrelated services remain untouched.

The process-local pending confirmation map is a **known unverified multi-process readiness risk**. The concurrent confirmation probe can expose it; do not mark HITL_CONCURRENCY PASS from the single-worker B0 or P4-A results. Correct Owner/HITL/real-time checks may not be removed to make it pass. Preserve any failed HTTP/DB/trace evidence before fixing the real defect. Initial prepared harness itself is unexecuted against Docker; infrastructure/harness errors must be separated from application failures and repaired transparently.

## Final verification and checkpoint

Run full `pytest tests research/docs/agent_engineering_upgrade`, Ruff check/format--check and Mypy, using new P4_E2E_RUN_ID/P4B_AUTH_RUN_ID/P4B_API_RUN_ID values so no old run is replaced. Run the frozen legacy214service checks under a new run directory; historical Gold remains untouched. P4-A's old legacy authentication probe remains a historical BLOCKED record; B0's required-auth suite is separate evidence.

Update B2/B3 task states with actual results, complete hashes and failure evidence. Commit verified task changes separately. Inspect Git status/staged content for CSV, credentials, manifests, logs, DBs and unrelated changes. Normal push only to the authorized repository/branch, then `git ls-remote` exact HEAD verification. Never redo finished experiments merely because push failed.

```bash
# After capturing/reviewing results, stop only the owned project; retain volumes for recovery.
python -m research.docs.agent_engineering_upgrade.p4_dependency_integration.sandbox stop
git push origin HEAD:codex/p4-dependency-integration
git ls-remote --heads origin refs/heads/codex/p4-dependency-integration
```

Do not automatically delete volumes; a user-approved cleanup must first verify exact project/owner/resources and confirm the test evidence is portable. Final stage stops after B3 and delivery. **No Experience Active; no paid DeepSeek; no P4-C/D/E.**
