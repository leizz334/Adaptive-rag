# Real DeepSeek baseline before P2 — BLOCKED

Date: 2026-11-04 (Asia/Taipei). No P2 implementation or production logic changes.

The application recognizes the configured key and selects `DeepSeekProvider`, but a valid real-model completion was **not obtained**. Following the user's stop condition, all 15 frozen scenarios are **NOT_RUN**. No offline results substitute for real-model results.

## Provenance and actual connectivity

- Baseline Git HEAD: `f454fb08e58a00f7701816ac09b500273b4b2fa0`.
- Branch: `codex/p1-tracing-evaluation-v2`; Conda: `adaptive-rag`.
- Configured endpoint: `https://api.llm.pm`; requested route: `POST /chat/completions`.
- Configured model: `deepseek-v4.1-flash-次`. Actual response-reported model: **unknown**.
- The user explicitly approved using this third-party gateway. Its underlying model and official DeepSeek provenance are **not independently verified**. A configured model string is not proof of model identity.
- The first probe was blocked by local sandbox networking: `PermissionError`, errno 13 / WinError 5. This is an infrastructure failure, not a model error.
- A single explicitly escalated probe then reached the gateway and received **HTTP 200**, followed by `JSONDecodeError`. HTTP success did not yield a usable chat-completions JSON result. Authentication acceptance, model availability, reasoning quality and billing cannot be inferred from that response.
- No upstream error body, key, authorization headers or raw customer data were saved. The original failed probe did not retain content type or body fingerprint; response format diagnostics are consequently limited. Later offline harness hardening captures those metadata for future experiments; it was not rerun against the gateway.
- Plausible configuration issue for follow-up: verify the gateway's OpenAI-compatible API base path (including whether `/v1` is required), exact model ID and JSON API routing. This is a hypothesis; no endpoint/model change or additional paid attempt was made to test it.

## Controls and selected cases

`experiment_config.json` fixes source/knowledge/skill/prompt/scorer hashes, dataset version/hash, selected IDs, model alias, endpoint, temperature and budgets. The original P1 source, frozen Gold, expected states and success criteria are unchanged. See `validation.json` for immutable-input and P0/P1 task-state checks.

Concurrency is 1; at most 80 HTTP attempts / 100,000 accounted tokens; retries disabled. Probe output cap is 32; planned scenario calls retain production temperature 0 and per-call caps up to 1,024. These are upper bounds, not a record of consumed tokens. Unknown usage is reserved conservatively for budget control, never reported as measured consumption.

The seven historical reference failures are `context_loss` and the six `freshness_ORD1000{1,2,3}_pronoun_{stable,changed}` cases. The eight controls are `order_lookup`, `explicit_target_change`, `greeting`, `argument_binding`, `cancel_pending`, `foreign_order`, `cross_user_session`, and `injection`. They cover normal queries, multiple turns, argument binding, pending approval, ownership/session checks and injection refusal. Several are correlated scenario variants; this is not a statistically independent sample.

The available driver already accepts `llm_factory`. Each scenario would use a fresh `BusinessEnvironment` SQLite in-memory database, synthetic seed, unchanged ChatService/Graph/tools, and unchanged `score_tools`/`score_goal`. No real orders are accessible. Because connectivity failed, a real scenario metering adapter was **not implemented** and no scenario or confirmed write was executed.

External tracing is disabled, including LangChain/LangSmith environment flags. The connectivity container explicitly disables remote DB, Redis, Qdrant, MCP, remote embeddings, local model downloads and document processing. It uses no production business connection.

## Results and metric definitions

| Measure | Observed result |
|---|---|
| Selected / completed scenarios | 15 / 0; 15 NOT_RUN |
| Agent Task Success | N/A (0 evaluated; not 0% or 100%) |
| Historical reference correctness | N/A (0/7 evaluated) |
| Tool Selection / Argument Accuracy | N/A (no executed scenario turns) |
| Environment State Success | N/A (no evaluated scenario snapshots) |
| Safety violations | N/A (not evaluated; no claim of verified safety) |
| Valid model completions | 0 |
| Local HTTP attempts / gateway responses | 2 / 1 |
| Gateway/API protocol failures | 1: HTTP 200 non-JSON, JSONDecodeError |
| Local infrastructure failures | 1: sandbox permission denial |
| Observed timeouts | 0; scenario timeout rate N/A |
| Real-model errors / refusals / tool exceptions | Not assessable; no valid model completion or business turn |
| Token usage | Unknown; no usage object, not zero |
| Agent mean / P95 latency | N/A |
| Gateway response latency | 1,947.079 ms, n=1; mean/P95 of this single HTTP observation equal that value and are not model/Agent latency estimates |
| Total request-attempt latency | 3,145.238 ms, including locally blocked attempt |
| Total probe wall latency | 4,428.880 ms, two invocations including isolated container initialization/cleanup; excludes human/tooling/reporting time |

The intended unchanged task criterion is no driver reasons: trajectory, required arguments, expected pending/refused/error behavior, allowed tool failures, independent committed state/observations and hard safety constraints all hold. Reference correctness requires the final reference turn to have valid trajectory and argument accuracy 1, over the seven fixed cases. This is tool-grounded reference resolution, not an independent semantic judge of answer text. Tool selection/argument averages are over labelled turns (argument N/A excluded). State success includes required fresh observations, as in P1. Report denominators explicitly if a later authorized run is partial.

No comparison with P1 offline percentages or P2 memory ablations is supported. The blocked experiment cannot establish a successful real-model baseline.

## Reproduction, validation and next action

Files: `results.json`, `requests.json`, `experiment_config.json`, `failed_cases.md`, `validation.json`, `validation-pytest.xml`; experiment-only code: `baseline.py`, `test_baseline.py`.

Offline verification (no paid calls):

```powershell
conda run --no-capture-output -n adaptive-rag python -B -m pytest -q -p no:cacheprovider research/docs/agent_engineering_upgrade/real_llm_baseline/test_baseline.py
conda run --no-capture-output -n adaptive-rag python -B -m ruff check research/docs/agent_engineering_upgrade/real_llm_baseline/baseline.py research/docs/agent_engineering_upgrade/real_llm_baseline/test_baseline.py
```

Eight mock tests passed; Ruff check/format passed. One existing LangChain deprecation warning remains. Budget guarding was demonstrated RED (one test failed) then GREEN, offline only. Independent review identified a missing/over-budget usage gate: three additional MockTransport cases were observed RED, then the full eight tests GREEN after adding raw usage validation and the accounting stop condition. The final harness differs from the exact probe-time harness by budget guard, diagnostic metadata and formatting hardening; the P1 production inputs are unchanged and no probe was replayed after that hardening.

`baseline.py prepare` freezes a new experiment only if no config exists; `probe` refuses replay when a probe is recorded. `probe-network` is restricted to one retry after a recorded sandbox permission failure. The saved gateway protocol error cannot be retried with either command. Reproduction of paid calls requires a **new, explicitly authorized experiment directory/run**, retaining these artifacts. Configuration/input reproducibility does not imply gateway model determinism. There is no completed real-model baseline to reproduce.

Local checkpoint hashes and actual GitHub push result are recorded in `feature-list.json`, `progress.txt` and `git_delivery.json`. User modifications to AGENTS.md and unrelated untracked files remain excluded. P0/P1 records are preserved; the independent real_llm_baseline task section records the blocker.

**Stop here.** Next action is user review and verification/correction of the gateway API base path/model settings before authorizing a fresh connectivity test and baseline. Do not automatically start P2 or repeat paid calls.
