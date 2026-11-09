# P3-A recovery

Authorized A0–A6 continuously; never reinitialize. Baseline70d65e36687ae31133b08aec065f0a3ca4a6b848 verified local and remote, previous P2-S clean. New worktree D:/Code/Adaptive-rag/.worktrees/p3-experience-shadow, branch codex/p3-experience-shadow. Root user changes preserved. Conda adaptive-rag. Read plan, task registry/progress and Git before resuming.

## Architecture decisions (preserve verbatim)

Experience processing is an isolated offline completed-trace runner. No production hook, experience retrieval, prompt injection or business execution is introduced. Default mode off; shadow explicit; active rejected. Use existing SQLAlchemy async engine/session infrastructure with a separate explicit experience metadata base so application startup/business schema are unchanged. All repository operations require scoped offline identity; no production cross-user or cross-session sharing. VERIFIED_OFFLINE is test evidence, not human approval or ACTIVE readiness. Unknown semantic claims stay NOT_ASSESSED; model-assisted review is never called human annotation.

New budget120HTTP/120000tokens/estimatedUS$2; no new calls yet. Saved P2-S77HTTP/75467tokens are historical and must never be replayed for billing. Old P2-Q/P2-R uncertain journals are untouched. Prefer deterministic candidate templates and independent saved-answer review; zero new calls is valid if sufficient for bounded engineering verification.

Current A0: fresh475baseline running scratch/p3a-baseline-01. Independent child p3_semantic_review owns only A1 semantic_review directory/report, no paid calls. p3_trace_diagnosis owns only A2 evidence/report, no app changes. Parent owns app/tests/state/commits. No product Multi-Agent. Next: verify A0, register phase exactly once, commit baseline, then A1 review evidence.
