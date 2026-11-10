# P3-B2/B3 continuation plan

> Execute inline with test-first checks and a fresh final reviewer. The user supplied human CSV and explicitly continued B2 on 2026-11-10; the original authorization then continues B3 automatically. No reinitialization or rerun of completed B0/B1/paid calls.

**Goal:** Import real user review faithfully, validate bounded experience retrieval/injection in a sandbox, report benefit conservatively, and plan P4 without running it.

**Architecture:** Production app, M2, Graph, prompt/catalog/settings remain unchanged. New research-only modules import human labels and select original canonical lessons from an isolated ExperienceRepository. Experimental injection requires both unchanged restrictive applicability and independently evidenced offline qualification. The broader B0 MATCH_FOR_REVIEW is never an injection permit. Unknown/untrusted/ambiguous/pending-write contexts remain denied. The wrapper inserts only canonical principles into selected model calls in E2. E0/E1 never alter prompts. Gold remains scorer-only.

**Approaches:** Direct production recall is excluded by the user's Active-off requirement. Broad relevance-driven injection would weaken preserved exclusions and is rejected. A sandbox-only provider wrapper plus unchanged business graph is the minimal controllable experiment selected here.

**Stack:** Existing SQLAlchemy SQLite repository, EvidenceResolver, scripted provider, instrumented Evaluation V2, pytest. No new framework or dependencies.

**Review focus:** Forged case/query/answer IDs and inconsistent verdicts; UNCERTAIN/metadata omissions falsely becoming approval; stale/deleted/cross-scope records; mutation of input messages or injection of private provenance; experimental faults changing E0/E1 business outputs.

## B2

- [x] Preserve user's edited CSV byte-for-byte; validate exactly seven identities, enum and aggregate rules; snapshot under a new immutable submission path. Record blank reviewer/time/notes as unknown, user attestation separately. Do not claim completed multi-rater calibration or experience approval.
- [x] RED tests for importer and sandbox selection/injection gates; then implement research-only human_import.py and sandbox.py. Restore frozen B1 material from Git only in memory, never overwrite the edited CSV. Original packet tests continue to use their historical blank contract.
- [x] Resolve all candidate provenance, canonical text and B0 frozen independent relevance evidence. Create new isolated offline-only repository copies and model-review records; never human-approve or alter P3-A database/export. Freeze permits and implementation before independent counterexamples.
- [x] E0=no experience; E1=post-completion Shadow observation; E2=selective sandbox prompt injection using the same scripted responses/policy, M2, seed, Gold and scorer. Record actual prompt changes, selections, full traces/state and unknown answer semantics. Do not program the scripted provider to reward a lesson.
- [x] Use newly authored varied tasks plus scope/lifecycle/error counterexamples and prior saved-review results. This is engineering validation, not new human Gold or blind NLU measurement. Compare strict tasks, annotated answer facts, wrong matches, negative transitions and E0/E1 divergence. No gain is acceptable; report NOT_ESTABLISHED when not proven. New live pairs are optional only after useful safe offline evidence; otherwise NOT_RUN.
- [x] Validate, save evidence/state and task commit; continue B3.

## B3

- [x] Full pytest with historical helper suites, Ruff check/format, Mypy; fresh legacy M2 strict groups; review import/experience, safety and isolation tests. Preserve failures and do not rewrite historical evidence.
- [x] Independently review changes; fix important findings with RED/GREEN before final freeze. Record reviewer scope and any dataset exposure honestly.
- [x] Generate P4_E2E_TEST_PLAN.md covering API E2E, real dependencies and bounded real LLM E2E, acceptance/security/budget/failure recovery. Do not execute P4.
- [ ] Audit user CSV and other root user files, previous source/Gold, staged paths and credentials. Exclude the edited original CSV from commits; commit the explicit submission copy/report only. Ordinary push authorized branch, ls-remote, record recovery and STOP. Production Active stays off.

**Ruling:** Missing reviewer identity/time/notes do not erase the user's explicit submission statement. They remain unknown metadata and reduce calibration to PARTIAL; import may proceed. The human answer verdicts never imply lesson approval or resolve UNCERTAIN. The user authorized continuous execution, so no extra design/step approval is inserted.
