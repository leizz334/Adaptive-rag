# Paired real-provider QA

Only the parent operator executes paid commands. The runner has made **zero real API calls during implementation**. Existing `real_llm_baseline` artifacts and historical scores stay untouched.

Run from the P2-Q worktree using Conda `adaptive-rag`. All commands use this module and the **same global run directory**:

```powershell
conda run -n adaptive-rag python -m research.docs.agent_engineering_upgrade.p2_quality.real prepare --run-dir research/docs/agent_engineering_upgrade/p2_quality/qa_real --env-file D:/Code/Adaptive-rag/.env
conda run -n adaptive-rag python -m research.docs.agent_engineering_upgrade.p2_quality.real probe --run-dir research/docs/agent_engineering_upgrade/p2_quality/qa_real --env-file D:/Code/Adaptive-rag/.env
conda run -n adaptive-rag python -m research.docs.agent_engineering_upgrade.p2_quality.real pilot --run-dir research/docs/agent_engineering_upgrade/p2_quality/qa_real --env-file D:/Code/Adaptive-rag/.env
conda run -n adaptive-rag python -m research.docs.agent_engineering_upgrade.p2_quality.real run --run-dir research/docs/agent_engineering_upgrade/p2_quality/qa_real --env-file D:/Code/Adaptive-rag/.env
```

`prepare` is read-only toward credentials/application state and creates the experiment artifacts once. It verifies app/eval/knowledge bytes against `c45f509f5e4260c34818df9bf48f2807dd1338b4`; config freezes those hashes, dataset, prompts, endpoint, requested model, timestamp, harness, prices and limits. It does not serialize Settings or the env file. `probe` is one short connectivity request. `pilot` evaluates `context_loss` with M0/M1/M2. `run` requires that completed pilot and continues the remaining nine cases, interleaving M0/M1/M2 per case. `resume` continues with the same gates and semantics. `summary` prints locally saved statistics.

Each group uses a new isolated in-memory SQLite business environment. The production provider and scorers remain intact. Only Memory differs; temperature is overridden identically to zero, provider retry count is one attempt, and production node output limits remain unchanged. Framework tracing and application external tracing are disabled. Synthetic order seed timestamps are frozen for deterministic crash replay. There is no M3 or heldout/new-unseen input in this QA experiment.

The global limits include the probe: 350 HTTP attempts, 300,000 accounted tokens, estimated US$3, concurrency one. Reserve each actual UTF-8 HTTP request length + 1024 input framing tokens + its output limit before dispatch. Missing, invalid, or inconsistent usage charges the full reservation. Valid usage is charged at peak cache-miss $0.30/M input and $1.20/M output without discounts. Provider-reported usage can exceed a reservation; any resulting hard-cap excess is recorded and stops further requests. These are conservative local estimates, not invoice guarantees.

Before each fresh group, forecast from the maximum observed request count and summed reservations of any prior group (initial bound 12 requests / 24,000 tokens). Every actual request also requires an independent reservation. A forecast stop preserves the partial experiment. It never increases a limit or silently selects extra cases.

`requests.json` is the write-ahead global ledger. Each request records group, zero-based sequence and hashes before transport. The public completion, finish reason, reported model, usage and HTTP status are atomically flushed before downstream parsing. It never saves Authorization, keys, raw error bodies, hidden `reasoning_content`, or entire Settings. A later replay must match the same group and sequence request hash exactly. Completed response checkpoints are returned locally with no new HTTP. A request with `PENDING` status has an uncertain outcome and **blocks every further paid dispatch**; inspect/reconcile externally, never clear it or retry automatically. OS locking prevents simultaneous commands against the same directory and releases on crash.

Do not create a new directory to evade the shared budget; every later authorized real retest must explicitly share/account for this ledger. This first runner intentionally freezes original P2 application source: later source variants need a separate reviewed experiment registration that preserves the same global ledger, rather than editing this QA config.

Statistics distinguish task success including errors, task success with valid outputs, model-invalid groups, HTTP-error groups, reported tokens and conservative accounted tokens. A fallback may recover task success after invalid model output; retain both observations. Raw task scores and reasons are never rewritten to claim model reliability.

Offline guardrail tests:

```powershell
conda run -n adaptive-rag python -m pytest research/docs/agent_engineering_upgrade/p2_quality/test_p2q_real.py -q --basetemp=.test-temp-p2q-guardrails
```

The temporary-directory option avoids this machine's inaccessible default pytest Temp root. The tests replace only HTTP transport, and exercise hard caps, exact replay, pending crash safety, hash conflicts, absent usage, HTTP errors, truncation accounting, forecasts, statistics, and full actual-service pilot recovery.
