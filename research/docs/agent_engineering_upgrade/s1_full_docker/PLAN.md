# S1-Docker Implementation Plan

Goal: Ubuntu one-command full stack Compose with safe idempotent initialization and actual browser/business persistence verification.
Architecture: Existing multi-stage frontend/Python image, API serves React and LangGraph. New independent compose.showcase.yml uses internal service DNS, separate bootstrap/initialize/runtime, scoped named volumes. Reuse shared synthetic seed extracted from S1-Web; keep host scripts.showcase compatible. No Agent/RAG/M2 redesign.
Tech: Docker Engine/Compose, Node24 build/Python3.12 runtime, existing PG16/Redis7/Qdrant1.12.5, Alembic, original authentication/ACL/HITL/Redis limiter.
Spec: S1-Docker user request + AGENTS.md; native continuous execution authorized; no design approval loop/new Worktree.

## Architecture decisions (preserve verbatim)
- All deployment code lives in new compose.showcase.yml and app/demo helpers plus existing Dockerfile improvements. Host S1-Release continues through its original function signatures; its .env and private state are never overwritten.
- Shared seed_session helper derives the existing synthetic ORD951xx/95201 fixture. Existing matching records are verified and retained, including cancelled status; collisions fail rather than reset. PostgreSQL advisory lock and transactional Alembic+seed protect initialization; no seed business writes on restart.
- Bootstrap creates random DB password in a separate secret volume and random user-only Bearer registry/dev-token file in a private API-state volume. Credential creation is file-locked, exclusive/atomic and idempotent; malformed/expired existing records are never silently replaced. No credentials in image, Compose env values, Git or public logs.
- API state directory is nonroot UID1000 mode0700/token0600. DB password file is internal read-only to Postgres; other dependency ports are not published. Only loopback Web port is mapped. Per-project named volumes have no fixed external names.
- Compose depends_on uses actual dependency health and successful one-shot initialization. API runs OfflineLLMProvider, required Bearer/private knowledge/Redis fail-closed/M2; model/trace-cloud/MCP keys disabled explicitly and dotenv excluded from image. Runtime egress permits only loopback and resolved PG/Redis/Qdrant endpoints; internal network further denies external egress.
- One command up -d --build needs only Docker on host; development test runners may use current .venv/Node separately. User-facing credential retrieval is an explicit local operator exec/copy, never automatic startup logs. Windows Docker Desktop is NOT_RUN.
- Acceptance uses a fresh checked project and source-only Git archive build context, real containers/Chromium/DB; test before/after restart and stop/start without deleting volumes, verify same tokens/Owner data/idempotent write counts. Old experiments/Gold/ledgers and unrelated MySQL remain unchanged.
- Full frontend/backend/static/legacy214, preservation and known-secret scans; per-task checkpoints, normalpush/exactremoteHEAD, STOP no otherphase/ExperienceActive.

## D1 containerization
- [x] Audit existing Dockerfile/Compose/host launcher; guarded design and config tests RED/GREEN.
- [x] Multi-stage runtime image with frontend/alembic/shared app assets, independent new Compose and no host keys/secrets context; config/build validation and checkpoint.
## D2 one-command initialization
- [x] Shared fixture extraction + bootstrap/initialize/serve/health safe CLI with tests RED/GREEN; credential modes/expiry/collision/idempotence/network restrictions.
- [x] Real initial deployment one command/health/migration/seed/auth/log checks; state/commit.
## D3 real deployment
- [x] Clean source archive new owned project build/up with exact requested command semantics.
- [x] Real browser7scenarios incl3business/Memory/RAG/HITL/history/Experience; realDB/crossuser proof.
- [x] Restart API/all deps and stop/start/up again; preserve credentials/schema/row counts/business state/knowledge/ACL; no reset; checkpoint.
## D4 regression
- [ ] Frontend tests/type/build + actual Playwright; fullhostpytest realdependency sandbox/Ruff/Mypy/pip/legacy214.
- [ ] Host S1-Release smoke remains usable; failures/evidence kept; review/minimalfix if needed; checkpoint.
## D5 delivery
- [ ] README/Docker deployment/finalreport/recovery, precise UbuntuPASS/WindowsNOT_RUN/controlled-vs-real limits.
- [ ] Source/secret/volume preservation audit, ownedstop(retainvolumes), scopedcommit/normalpush/exactHEAD/metaPush/STOP.

## Review focus
Bootstrap partial-state/cross-volume mismatch must fail safely; PG password must be readable to official Postgres entrypoint without exposing dev-token file. Internal-DNS egress guard cannot accidentally allow paid endpoints. Health must check actual dependencies, not just API200. Restarts cannot rotate tokens/reset cancelled data, overwrite private KB or duplicate SQL writes. Docker build context must exclude all nested .env/.private/node_modules; no mutable user data copied into image.

## Runtime corrections after D1 (supersede affected network assumptions above)
- Current Docker Snap denies exec when no-new-privileges is enabled, even in untouched official Python image. Omit this optional flag; keep UID1000 API/read-only/cap-drop/default AppArmor/seccomp and all application security. NNP hardening NOT_AVAILABLE on this tested deployment.
- An API attached solely to the internal network did not receive an actual published endpoint. Attach only API to a separate web bridge; PG/Redis/Qdrant/initialize remain internal. Loopback-only Web publishing remains; API external egress is prevented by the socket allowlist and disabled provider/cloud configuration, not claimed as a Docker network-level guarantee.
