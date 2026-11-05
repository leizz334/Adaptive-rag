# P2-S6 real source pairs

Preparation and mock tests send no real HTTP. This runner is a new experiment;
it never opens an earlier P2-Q/P2-R run directory. In particular, the old pending
194/109 requests must remain untouched and must never be replayed here.

The runner reuses the unchanged P2-Q durable public-response transport and P2-R
timing/source-binding helpers through absolute imports. Their hashes, current
answer scorer, frozen instrumentation, candidate freeze, and this runner are
bound into the immutable configuration. Importing the runner or running
`_imports` does not read a developer env file. Explicit `prepare` may read the
supplied env file to fingerprint configuration; it performs no network calls.

Hard limits include the probe: 350 HTTP attempts, 300,000 accounted tokens,
estimated US$3, concurrency one, and at most 24 HTTP attempts per scenario arm.
Every generation gets one HTTP attempt with temperature zero and at most 1024
output tokens. The single probe has a 32-token cap. Under the supplied published
peak prices, even 300,000 all-output tokens would estimate US$0.36; the separate
US$3 guard remains enforced. Estimates are not invoices. Missing or inconsistent
usage charges the complete UTF-8 request byte count plus safety allowance and
the reserved output cap. Reasoning/hidden content, credentials, and error bodies
are excluded from persisted provider responses.

The parent verified [official pricing](https://api-docs.deepseek.com/quick_start/pricing/)
on 2026-11-05: input cache miss US$0.30/M, output US$1.20/M, without cache
discounts. The configured model is preserved; no model, thinking, endpoint, or
application setting is changed to fit the experiment. Published alias details
do not independently verify backend weights. Thinking may consume the small
output budget and cause truncation; that outcome is retained.

The candidate app must exactly match `evidence/candidate_freeze.json` (app source
commit `37a7e47d241175c0af9a110686ef6bf90c621c62`); R0 must be clean at
`e74f01db65fb9f3df929cdf5932919e1f10e453e`. Current metadata HEADs are recorded at
preparation. Metadata-only checkpoint commits afterward are allowed only while
all frozen runtime source/helper/scorer/data bytes remain identical. Shared
evaluator, knowledge, seed, settings, and call-site caps must match. Actual
signature defaults are recorded separately, including intentional Judge changes.

Only PSD03, PSD05, PSD08, and PSD10 are predeclared development cases. Six holdout
IDs are selected using SHA256(`P2S-20261105` + ID); no query, Gold, or outcome is
used for selection. Source order alternates by case, one repetition each. The
first development source pair completes before any later case. Partial stopping
at a hard budget is valid and must be reported with its real denominator.

Every arm runs in a fresh source-bound process. `BusinessEnvironment` supplies
isolated in-memory SQLite and M2; no production DSN is passed to it. External
tracing is disabled. The shared seed clock freezes imported business-clock
aliases and captured SQLAlchemy timestamp defaults. Initial seed tables are
captured, hashed, and compared across the pair; a mismatch stops continuation.

Frozen `instrumented.py` remains byte-for-byte unchanged. The explicit paid
worker scopes its offline-network context to `nullcontext` so the configured
provider can run, and extends only the captured extra-field allowlist with
Judge/error/completeness metadata. The same scope is tested with MockTransport.
No product graph, policy, tool permission, ownership, or Gold input changes occur.

Before running, commit the reviewed harness and complete the parent's S5
checkpoint. Use a fresh run directory. These PowerShell commands are examples
for the authorized future run, not a record that a paid run occurred:

```powershell
$taskPython = 'D:/MiniAnaconda3/envs/adaptive-rag/python.exe'
$taskRoot = 'D:/Code/Adaptive-rag/.worktrees/p2-answer-reliability'
$taskPhase = "$taskRoot/research/docs/agent_engineering_upgrade/p2_answer_reliability"
$taskHarness = "$taskPhase/real_pairs.py"
$taskRun = "$taskPhase/runs/real-source-pairs-20261105"
& $taskPython $taskHarness prepare --run-dir $taskRun --env-file 'D:/Code/Adaptive-rag/.env' --r0-root 'D:/Code/Adaptive-rag/.worktrees/p2-agent-quality' --r1-root $taskRoot --dev-dataset "$taskPhase/datasets/development.json" --dev-answers "$taskPhase/datasets/development_answers.json" --blind-dataset "$taskPhase/datasets/holdout.json" --blind-answers "$taskPhase/datasets/holdout_answers.json" --input-price 0.30 --output-price 1.20 --pricing-url 'https://api-docs.deepseek.com/quick_start/pricing/' --pricing-verified-date '2026-11-05'
& $taskPython $taskHarness probe --run-dir $taskRun --source-root 'D:/Code/Adaptive-rag/.worktrees/p2-agent-quality' --variant R0
& $taskPython $taskHarness pilot --run-dir $taskRun
& $taskPython $taskHarness summary --run-dir $taskRun
```

Review pilot evidence/accounting before issuing `run` for the remaining frozen
groups. `resume` is the same bounded coordinator; neither command changes the
selection or budgets. Never rerun `prepare` against an existing run. A completed
group returns `ALREADY_COMPLETED`. After a crash, only matching durable completed
responses can be replayed; this incurs no new HTTP attempts. Any PENDING row
stops all execution for manual reconciliation. Connect/timeout/cancellation,
including BaseException during response-body reading, records elapsed time and
leaves the reservation pending. No automatic resend or retry is allowed.

`requests.json` reserves before dispatch and checkpoints whitelisted public
responses before provider parsing. `captures/*.json` preserves actual final
answers, node states, tool observations, and initial/final/per-turn DB snapshots
before answer Gold is loaded for scoring. A scoring/results-write crash therefore
does not lose the paid responses. Source/config/request hash drift stops replay.

Scoring uses the frozen current `eval/answer_scoring.py` via an absolute module
loader after the Agent finishes. Raw old tool/environment driver output remains
available with its original `NOT_RUN` default. New evidence metadata explicitly
records the configured real provider; actual tool/environment results and answer
scores remain separate. Unsupported extra clauses stay `NOT_ASSESSED` and
`semantic_human_calibration` remains `NOT_RUN`; there is no same-model semantic
self-judge or claim of general natural-language accuracy.

Mock validation (use a fresh basetemp path if the system temp ACL is unavailable):

```powershell
& $taskPython -m pytest "$taskPhase/test_p2s_real_pairs.py" -q --tb=short --basetemp "$taskRoot/.pytest_cache/p2s-real-fresh"
```
