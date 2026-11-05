# P2-R5 source-paired experiment

This tooling makes no provider calls during `prepare`, `_snapshot`, `_imports`,
or `summary`. Run paid commands only after the parent freezes the final candidate,
releases the blind set, and finishes the full 33-case blind offline evaluation.
The author does not select cases from queries, Gold, or outcomes.

R0 is commit `09819352cc6df98b9f8cb42ffb56e9c8365b5793`, in
`D:/Code/Adaptive-rag/.worktrees/p2r-c0`. R1 is the explicitly recorded final
candidate commit in `D:/Code/Adaptive-rag/.worktrees/p2-agent-quality`.
Both use M2, unchanged datasets/Gold/evaluator/knowledge/seed fixtures, a shared
fixed seed clock, temperature zero, matching source call-site output caps, and
an overall output maximum of 1,024. Each group creates a fresh in-memory SQLite
environment. Public cross-session M3 stays off.

One new run directory owns the entire ledger, including probe, pilot, and any
repeat. Hard limits are 420 HTTP attempts, 420,000 accounted tokens, USD 3,
24 HTTP attempts per group, one process at a time, and one HTTP attempt per
generation (`llm_max_retries=1`; no automatic retries). Group namespaces are
`case_id:R0:0` / `case_id:R1:0`; repetition 1 is optional and allowed only after
the initial whole pair exists and a forecast for both repeated arms fits.
The parent controls interleaving and continuation after inspecting the pilot.

The official pricing page was reverified by the parent on 2026-11-05:
<https://api-docs.deepseek.com/quick_start/pricing/>. Use peak cache-miss input
USD 0.30/M and output USD 1.20/M without cache discounts. The published service
alias was `DeepSeek-V4.1-Flash-1017`; backend weights are not independently verified. The experiment
records the configured model/endpoint and actual public response model. Price
estimates are not invoices. The 420k-token cap implies at most USD 0.504 at the
maximum of these two rates, conditional on usage accounting/reservation bounds.

The selected development IDs are dv01, dv06, dv08, dv16, dv18 (an unambiguous
dataset prefix is accepted). The six blind IDs are chosen after candidate freeze
by ascending `sha256('P2R-20261105' + case_id)`. Only IDs enter selection.

## Preparation and pilot

Use a fresh absolute output path; preparation refuses an existing directory.
Replace the candidate commit only after the parent records its actual freeze.
The explicit root `.env` is read, never printed or copied. Credentials are not
serialized; settings fingerprints include one-way hashes of credential identity.

```powershell
$p2rPython = 'D:/MiniAnaconda3/envs/adaptive-rag/python.exe'
$p2rProject = 'D:/Code/Adaptive-rag/.worktrees/p2-agent-quality'
$p2rHarness = "$p2rProject/research/docs/agent_engineering_upgrade/p2_agent_quality/real_pairs.py"
$p2rBaseline = 'D:/Code/Adaptive-rag/.worktrees/p2r-c0'
$p2rCandidate = $p2rProject
$p2rCandidateCommit = '<ACTUAL_FINAL_FROZEN_COMMIT>'
$p2rDatasets = "$p2rProject/research/docs/agent_engineering_upgrade/p2_agent_quality/datasets"
$p2rRun = "$p2rProject/research/docs/agent_engineering_upgrade/p2_agent_quality/runs/20261105_R5_pairs_01"
$p2rEnv = 'D:/Code/Adaptive-rag/.env'

& $p2rPython $p2rHarness prepare --source-root $p2rCandidate --project-root $p2rProject --run-dir $p2rRun --r0-root $p2rBaseline --r1-root $p2rCandidate --candidate-commit $p2rCandidateCommit --dev-dataset "$p2rDatasets/development.json" --blind-dataset "$p2rDatasets/blind_holdout.json" --env-file $p2rEnv --input-price 0.30 --output-price 1.20 --pricing-url 'https://api-docs.deepseek.com/quick_start/pricing/' --pricing-verified-date '2026-11-05'
```

The baseline/candidate worker fingerprints include raw app/eval/knowledge file
hashes, commit, prompt differences as path/hash pairs, source import paths,
provider and ambient settings hashes, and output-cap expressions. Clean app,
eval, and knowledge snapshots are required. The run freezes the harness and
the unchanged P2-Q helper file too. No previous P2-Q ledger is opened: in
particular, its historical pending request 194 is never loaded or replayed.

```powershell
& $p2rPython $p2rHarness probe --source-root $p2rBaseline --project-root $p2rProject --run-dir $p2rRun --variant R0 --env-file $p2rEnv
$p2rConfig = Get-Content -LiteralPath "$p2rRun/experiment_config.json" -Raw | ConvertFrom-Json
$p2rPilot = $p2rConfig.selected[0].id
& $p2rPython $p2rHarness run-group --source-root $p2rBaseline --project-root $p2rProject --run-dir $p2rRun --variant R0 --case-id $p2rPilot --rep 0 --env-file $p2rEnv
& $p2rPython $p2rHarness run-group --source-root $p2rCandidate --project-root $p2rProject --run-dir $p2rRun --variant R1 --case-id $p2rPilot --rep 0 --env-file $p2rEnv
& $p2rPython $p2rHarness summary --source-root $p2rCandidate --run-dir $p2rRun
```

Inspect both pilot groups, errors, and ledger usage before calling another
`run-group`. Use the same command shape for each predeclared ID and its two
variants, with the correct source root. The parent alternates variant ordering
across pairs. Do not create a second ledger to evade a limit or uncertain request.
The source root is applied before any app/eval imports; use the absolute harness
file in a new process for every worker, never an already-imported interpreter.

## Recovery and interpretation

Reservations are atomically written and fsynced before HTTP. Only public
completion content, selected metadata, usage, and safe error types are persisted;
authorization headers, raw error bodies, and `reasoning_content` are excluded.
Responses are checkpointed before provider parsing or downstream graph work.
Timeouts, body-read failures, and interrupted dispatches retain latency and a
PENDING reservation. Any PENDING/uncertain row stops the entire ledger and is
never replayed automatically. Unknown response usage retains the full UTF-8
input/output reservation rather than zero tokens.

A completed response may replay only with the same source fingerprint,
experiment config, group sequence, and complete request hash. If a process dies
after responses but before the group result, rerunning that same `run-group`
reconstructs its fresh fixture and replays the completed HTTP responses. Hash
conflicts stop. Already completed groups return without calling the provider.

Results retain the untouched driver's result under `raw_driver_result`, including
its default `model_evaluation=NOT_RUN`. The group explicitly records real-provider
or completed-response-replay provenance and new versus historical HTTP attempts.
A group with no HTTP is marked `NO_HTTP_FOR_GROUP` rather than claiming a model
completion. Task results, HTTP failures, lexical JSON errors, schema diagnostics,
truncation, usage, and transport latency remain distinguishable. Schema diagnostics
cover the listed classifier/planner/answer/judge contracts, not every arbitrary
completion or semantic answer quality. Valid-output rates are reported alongside
rates that retain errors in the denominator. Incomplete source pairs remain in
arm denominators and are not counted as complete pairs.

Offline validation command (HTTP MockTransport plus socket guards):

```powershell
& $p2rPython -m pytest research/docs/agent_engineering_upgrade/p2_agent_quality/test_p2r_real_pairs.py -q --basetemp scratch/p2r-r5-testtemp/NEW_UNIQUE_TEST_PATH
```

Tests use synthetic fixtures and never read the real blind inputs. The Windows
asyncio internal socketpair is created before the guard; all test-body outbound
socket connections and DNS are blocked. No provider key is needed for real HTTP
because every test HTTP transport is replaced with a mock.
