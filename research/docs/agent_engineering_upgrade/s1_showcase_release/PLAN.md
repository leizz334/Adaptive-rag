# S1-Release Implementation Plan

Goal: Package verified Adaptive-RAG into a reproducible, honest Agent interview showcase without new research features.
Architecture: Keep React/FastAPI/LangGraph/PG/Redis/Qdrant and original security paths. Reuse guarded Compose + S1-Web offline demo through one per-run launcher; optional SQL-backed Owner-only history read, no migration or production login. Evidence-led README and 5–10 minute script.
Tech Stack: Current .venv, Node existing React/TS/Vite, existing Docker Compose and authenticated APIs, Vitest/Playwright/pytest/Ruff/Mypy.
Spec: User S1-Release request; AGENTS.md. Continuous execution authorized; prior opt-out of repeated approval questions retained.

## Architecture decisions (preserve verbatim)
- Fixed Ubuntu worktree and .venv are reused; no git worktree is created. Clean-source install verification may extract git archive into an ignored scratch directory with a separate disposable venv/node_modules; this is installation verification, not a development checkout or history rewrite.
- One explicit run-id owns a fresh Compose project, private manifest, synthetic database, API config and process records. Reuse sandbox ownership checks; do not reset existing DBs, prune, down-v, overwrite .env or old demo API credentials. Init refuses existing run; start resumes same run without destructive migration roundtrip.
- Showcase defaults to controlled OfflineLLMProvider with zero paid configuration and loopback socket guard. Production Bearer/Owner/private ACL/Redis fail-closed/HITL/idempotency remain enforced; credentials generated once into mode0600 ignored files and never public stdout/log/README.
- Source-of-truth for quality is historical reports/raw results. Controlled browser demos prove engineering flows, not DeepSeek quality; full semantic truth remains NOT_ASSESSED and Experience benefit NOT_ESTABLISHED. Experience UI is synthetic historical read-only, Active off.
- R4 may add bounded subject-filtered SQL session list and own user/assistant history only, no system/tool/summary data, no migration, no automatic replay of pending writes or fabricated historical citations/traces. Missing/foreign session reads are opaque404. Identity changes abort outstanding reads.
- README presents one tested Ubuntu path, actual screenshots, actual architecture, engineering tradeoffs and limitations. Legacy Docker production topology is not claimed verified if only the host API + owned dependency Compose path is tested.
- Every task checkpoint records tests and real commit; final full backend/frontend/browser/legacy214, preservation and credential scan; normalpush/exactremoteHEAD and STOP no S2/S3/P5.

## S1-R1 startup
- [x] Audit scripts/Compose/env examples; add scripts.showcase init/serve/status/start/stop/info with per-run ownership and no-paid profile; RED/GREEN launcher safety tests.
- [x] Real owned Compose dependencies + actual built frontend/FastAPI startup/health/stop/restart. Record task state and scoped commit.
- [x] From committed source, isolated git-archive pip/npm install verification, preserve results under release evidence (can accompany R2 checkpoint).
## S1-R2 demonstrations
- [x] Parameterize existing real browser E2E config for per-run private config; preserve old defaults/old artifacts.
- [x] Run3required scenarios + Experience, exact business write audit and crossuser failures; document steps/expectations/evidence, checkpoint.
## S1-R3 docs
- [ ] Rewrite rootREADME for interview audience; architecture/workflow/modulemap, screenshots, safe tested commands, metrics and production boundaries.
- [ ] 5–10minute DEMO_SCRIPT + ARCHITECTURE_OVERVIEW + ENGINEERING_HIGHLIGHTS; link/command validation, checkpoint.
## S1-R4 UX
- [ ] Small Owner-only history/list restore if feasible, RED/GREEN/isolation/error/concurrency; otherwise explicit limitation without blocking release.
- [ ] Update current docs for actual behavior, type/build/targeted tests and browser refresh evidence, checkpoint.
## S1-R5 verification/delivery
- [ ] Full frontend/type/build/browser + real backend/pytest/Ruff/Mypy/pip/legacy214; source/credential/history preservation review.
- [ ] Finalreport/recovery/ownedstop/scopedcommit/normalpush/lsremote; metadata normalpush/finalHEAD; STOP.

## Review focus
Run-id/manifest tampering or stale PID cannot stop other processes/resources; resumed init never resets data. Creds must stay ignored0600, history endpoints never create/access foreign sessions. Read restoration must not race new messages or identity changes; old citations/ActionIDs must not be invented. README commands must choose fresh owned resources and actual auth; controlled engineering results and real quality metrics must remain distinct.
