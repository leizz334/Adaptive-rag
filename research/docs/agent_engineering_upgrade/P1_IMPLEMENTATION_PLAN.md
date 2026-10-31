# P1 Agent Tracing + Evaluation V2 Implementation Plan

> Execution: superpowers:executing-plans, inline and continuous as explicitly authorized by the user. One atomic task at a time; validate, persist, commit, then continue. Do not repeat Initializer.

**Goal:** trustworthy execution evidence and offline, task-level Agent evaluation without changing Memory or learning experiences.

**Architecture:** retain ChatService/LangGraph and existing metrics. Use bounded, context-local, metadata-only spans with optional LangSmith export and an independent local tool event recorder for deterministic evaluation. Execute multi-turn fixtures through the production service in an in-memory SQL environment; gold expectations never enter model prompts.

**Tech Stack:** existing Python 3.11, Conda adaptive-rag, Pydantic, pytest, SQLAlchemy/SQLite, LangGraph; optional explicit LangSmith adapter using the existing installed SDK.

**Spec:** user P1-A through P1-F request and P0 reports in this directory.

## Constraints and decisions

- Only P1 is authorized; no Memory V2, Experience Memory, training, production DB or paid model calls.
- Keep P0 tasks/reports/evidence and original historical decisions intact. Append P1 decisions and tasks.
- Work on `codex/p1-tracing-evaluation-v2`; preserve user's modified AGENTS.md and unrelated untracked files. No worktree is needed for the requested branch-based workflow; no dependency installation is needed for the baseline.
- LangSmith is chosen over introducing a second observability platform, following P0-D. Explicit enablement and credentials are required for export; disabled tracing is a no-op. Local tests must not contact SaaS.
- Use manual metadata-only node/provider/retrieval/tool spans, avoiding automatic capture of entire LangGraph State. Keep task/tool evidence local, separate from exportable span payloads.
- Production authentication is outside this tracing/evaluation change. Do enforce existing session ownership at the repository boundary when evaluating isolation, and report the remaining client-user_id trust issue rather than claim production security readiness.
- Scope is a small hand-labelled multi-turn set first; do not manufacture 80 repeated scenarios or improve scores by passing gold to the provider. Context-loss cases may correctly fail until P2.
- New temp/cache files for tests live under ignored audit evidence/.tmp, never touch real orders. No remote credentials are printed.

## Alternatives

Native framework auto-tracing is convenient but may serialize private State. Manual spans with a LangSmith exporter allow explicit privacy and async lifetimes. Phoenix/Langfuse would add platform/dependency/operations cost at this stage. Self-written deterministic evaluation is retained because DB final-state assertions and HITL cannot be delegated to semantic judges. These are implementation choices made under the user's continuous-execution authorization, not additional user preferences.

## Review focus

1. Wrong tool/arguments and extra calls must fail even if answer sounds correct (C).
2. Denied or uncommitted writes cannot satisfy business goals (D).
3. Concurrent tasks, cancelled SSE and exporter failures must not change business results or leak spans (B/F).
4. Private inputs, exceptions and arbitrary metadata must never reach the export payload (B/F).
5. Judge outage/invalid JSON/no evidence must not be counted as hallucination (E).

## P1-A: Baseline & contract

Files: `eval/contracts.py`, `eval/baseline.py`, `tests/unit/test_eval_contracts.py`, P1 evidence/state/controller and this plan.

Interfaces: ToolCall/ToolExpectation/TrajectorySpec, EnvironmentExpectation and EvaluationResult Pydantic contracts; `baseline_snapshot()` returns versioned hashes/counts and known legacy scoring limitations. Gold and local event data do not leave evaluation.

- [ ] Run original pytest with JUnit and record pre-existing failures; safe environment-only temp-path issues can be resolved and recorded.
- [ ] Write failing contract tests: invalid event/result states rejected, typed roundtrip, source dataset snapshot has 65/100/16 unique cases.
- [ ] Implement contracts and offline snapshot; run focused tests and original suite.
- [ ] Save baseline immutable JSON/JUnit, append tasks and persist checkpoint; commit only A files.

## P1-B: Tracing

Files: `app/observability/tracing.py`, `app/observability/langsmith_exporter.py`, config/container/service/graph/provider/retriever/tool boundaries, `tests/unit/test_tracing.py`, trace integration tests and guide.

Interfaces: `TraceRecorder`, `span(name, kind, **safe_metadata)`, `traced(...)`, root turn scope and async generator wrapper. Span carries IDs, parent, times, status, enum error and numeric usage; raw inputs/outputs are not accepted. Export uses a bounded queue and has explicit close/flush limits.

- [ ] RED: disabled no collection; nested async/concurrent parents; no raw identifier/secret serialization; exporter exceptions isolated; async generator cancellation finalizes root; mock HTTP Provider retry spans and tokens.
- [ ] Implement no-op/local recorder and optional LangSmith payload adapter. Instrument production call boundaries and retain existing trace IDs/metrics.
- [ ] GREEN focused integration, SSE and existing business tests; record cloud NOT_RUN.
- [ ] Persist evidence/state and commit B.

## P1-C: Tool/trajectory scoring

Files: `eval/tool_scoring.py`, local tool recording in production executor/base boundaries, legacy runner result integration and deterministic unit tests.

Interface: `score_tools(calls: list[ToolCall], spec: TrajectorySpec) -> dict`; record actual tool execution/denial/replay, not answer keywords.

- [ ] RED table cases: correct/wrong argument, wrong/missing/unnecessary tool, execution failure, equivalent valid paths, order violation, fallback/replay.
- [ ] Implement versioned code scoring and local recorder. Preserve clearly labelled historical heuristic, remove it as success criterion.
- [ ] GREEN tests and checkpoint C.

## P1-D: Environment/goal evaluation

Files: `eval/environment.py`, `eval/goal_scoring.py`, integration tests and fixtures; narrowly repair session-owner enforcement if required by isolation tests.

Interfaces: isolated in-memory `BusinessEnvironment`, independent initial/final snapshots, `score_goal(initial, actual, expected, events)`; no supplied DSN/production settings allowed.

- [ ] RED: query owner, cancellation, pending/no write, confirmation, repeated confirmation, foreign owner, forbidden mutation, lying answer and commit failure.
- [ ] Run production tools/service against temporary SQL and trusted fixture identity; verify all orders plus refund/return/audit counts and no forbidden effects.
- [ ] GREEN unit/integration and checkpoint D; production authentication remains documented.

## P1-E: Judge/multi-turn

Files: checker/prompt/faithfulness node, generation runner accounting, `eval/multiturn.py`, labelled JSON dataset and tests.

Interfaces: five-state faithfulness verdict with compatible `supported` access; `run_scenarios()` over independent environment per case, dynamic confirmation references only, no gold injection.

- [ ] RED: five judge statuses, provider/parse errors, legacy output compatibility, outage not a hallucination; multi-turn HITL/replay, context loss, recovery and cross-user cases.
- [ ] Implement driver and honest accounting, keep retrieval metrics unchanged. Freeze small hand-labelled fixture dataset, include failing contextual examples.
- [ ] GREEN offline run and checkpoint E; real LLM quality NOT_RUN.

## P1-F: regression and acceptance

Files: final P1 report, trace guide, metric/dataset definitions, reproducible offline result artifacts, any review fixes and state.

- [ ] Run full pytest, lint/type checks appropriate to changed code, offline driver twice, compare deterministic outcomes/dataset hashes, trace off/on and privacy/security tests.
- [ ] Review complete branch, fix important findings with RED/GREEN tests; separate engineering acceptance from real model task quality and SaaS connectivity.
- [ ] Persist actual metrics/failures/limitations and recovery state, task-scoped commit.
- [ ] Verify configured remote and new branch; safe normal push if available/authorized. No force, no unrelated files. Record failure and exact pending command otherwise. STOP awaiting P1 review.
