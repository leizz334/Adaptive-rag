# Answer reliability implementation plan

> For agentic workers: execute inline with superpowers:executing-plans. User explicitly authorizes continuous S0-S7, evidence and commit per task, no repeated approval gates.

Goal: preserve real business execution while making final answers grounded, complete and independently measurable.

Architecture: retain existing graph and five Judge categories. A compact, strictly validated verdict separates infrastructure/output errors from unsupported facts. A common pure renderer exposes only allowlisted successful tool facts and unresolved limitations, never model-configuration speculation or arbitrary RAG excerpts. A small goal/evidence contract supports current tools and independent answer scoring. Gold is used only by eval, never Agent. Source snapshots isolate answer reliability from task-capability changes.

Tech stack: existing Python/Pydantic/LangGraph/SQLAlchemy/pytest/EvalV2; no new dependency or product agent.

Spec: user-authorized P2-S0-S7. Budget350HTTP/300000accountedtokens/estimatedUS$3, concurrency1, max24calls/scenario, no uncertain retry. Preserve all historical artifacts and root user edits. M2 fixed. No P3/P4, new Memory or training.

## Decisions and review focus

- Judge unknown must remain unknown; fallback fact rendering must not mark the original answer supported.
- Only actual successful, validated business-tool outputs may authorize factual templates; write claims must require affirmative execution result, never model intent.
- Multi-goal answers need all goals or explicit limitations; inventory/policy distinction and scoped negation cannot broaden writes.
- Gold cannot enter prompts/tools; semantic claims outside deterministic coverage remain NOT_ASSESSED without human/independent calibration.
- Holdout isolation is procedural and must be disclosed; freeze code+scorer before reading/evaluating holdout details. No tuning on its final failures.

## Atomic tasks

### S0 baseline
- [ ] Read current protocols, old reports/raw traces/config and delivered Git tree, not root's stale source.
- [ ] Register namespace only; save raw SHA256 preservation/source maps and fresh full344test XML.
- [ ] Verify metrics against R4/R5 JSON, six Judge+onePlanner truncation and source44f1031 equivalence; write baseline report and commit.

### S1 Judge/fallback
Files: app/guardrails/hallucination.py, app/agents/nodes/{generate,faithfulness}.py, app/prompts/faithfulness.py, app/agents/answer_evidence.py (pure renderer), tests/unit/test_p2s_answer_reliability.py; provider/SSE only for demonstrated error handling.
- [ ] RED tests: compact valid verdict; length; JSON/schema types; API errors; Judge failure with multiple facts; unconfirmed writes; no-evidence/no unrelated excerpt; streaming interruption.
- [ ] Implement compact schema/output constraints, retain backwards-compatible stored result shape and exact error type; no auto Judge retry. Pure safe fallback renders all known facts and explicit unknowns.
- [ ] GREEN plus original Judge/provider/stream tests; capture separate old and fixed behavior; save source boundaryS1 then commit.

### S2 independent answer evaluation
Files: eval/answer_scoring.py, tests/unit/test_answer_scoring.py, phase report.
- [ ] RED tests distinguish correct, omitted, false, unsupported, operation-not-executed, knowledge, clarification and unknown judgment; alternate legal phrasings accepted.
- [ ] Strict Pydantic Gold contract; score facts/subgoals against local final answer and actual observed evidence, independently requiring tool/state success for overall. Deterministic subset and unknown semantics separate. No external judge presumed accurate.
- [ ] GREEN tests and isolated scorer/Agent-input test; document independent review limits then commit.

### S3 goal completeness
Files: existing planner/intent/router/answer prompt plus small goal module only where trace proves necessary; focused independent unit/integration tests.
- [ ] Trace B03/06/26/28/30/31/32,dv01/05/07 and real dv06/B31; locate first boundary.
- [ ] RED unrelated paraphrase tests for needed evidence, conjunction, negation, SKU capabilities; preserve conditional write conservatism.
- [ ] GREEN minimal shared capability/goal contract, structured parameter checks, final known/unknown coverage; existing security/full tests; freeze S2-only and combined candidates; commit.

### S4 datasets
- [ ] Create >=20 development answer-annotated independent scenarios (including tool errors/Judge failure as explicitly labeled injection tests).
- [ ] Author >=20 holdout independently of implementation if available; otherwise disclose process limitation, no fake blind claim. Test quality/freeze schemas, UTF8, rules/evidence, overlap and SHA before final candidate evaluation.
- [ ] Commit frozen data without tuning from holdout outcomes. New scorer tests are distinct from Agent model semantics.

### S5 offline controls
- [ ] Run actual source rootsS0baseline/S1answer/S2capability/S3combined, fixedM2/scorer/Gold/fixtures/provider; no fictional identical arms.
- [ ] Retain old80/16/dev30/formerblind33/long-window plus new development/holdout and known real failures; capture actual final answers locally without external tracing.
- [ ] Report old stricttool/state scores separately from new deterministic/NOT_ASSESSED answer metrics. Preserve every regression; commit.

### S6 real pairs
- [ ] Verify current public model/pricing/config without printing key. New bounded ledger only; never replay old uncertain194/109.
- [ ] Pilot development pairs; check evaluator validity and accounting. Freeze implementation+scorer before new holdout source-pairs. Alternate source order, same service/temp/data/fixture; document intentional Judge/Prompt/output changes.
- [ ] Save public responses+request hashes+reservation before dispatch; partial stop on uncertain network result; deterministic final facts/coverage distinct from unconstrained semantics/human validation NOT_ASSESSED. Commit even if partial.

### S7 delivery
- [ ] Fullpytest/Ruffformatcheck/Mypy; all safety/provider/SSE/eval/tracing compatibility. Check frozen hashes, old evidence and root users unchanged; audit staged files/secrets.
- [ ] Honest final report and namespace state; task-scoped commit. Ordinarypush authorizedorigin/branch; verify lsremote; persist delivery checkpoint; STOP.
