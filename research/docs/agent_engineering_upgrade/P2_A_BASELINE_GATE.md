# P2-A — preserved baseline, diagnosis and paid supplement gate

Date: 2026-11-04 Asia/Taipei. Pre-P2 source: `3c373ca502e2e08b4a343d751500c7ce77b28415`. P1 stays PARTIAL_PASS; real baseline stays PARTIAL. The old nine results, Gold/scorers and all earlier evidence are immutable. No Initializer was rerun. P2 worktree: `D:/Code/Adaptive-rag/.worktrees/p2-memory-context`, branch `codex/p2-memory-context`.

Original full regression at P2 start: 212 passed, one existing LangChain warning; p2_evidence/P2-start-pytest.xml. The baseline source, real results/requests/config/failures, P0 memory audit and P1 report were read before implementation.

## Distinct failure classes

| Class | Evidence and boundary |
|---|---|
| Missing historical context | ChatService loads messages but initializes summary=""; Intent/Router use only current query, Planner gets empty summary, Generate omits messages/summary. Source-verified root cause; seven frozen reference turns fail under real model. |
| Entity reference resolution | Six freshness pronouns produce no correct new get_order; context_loss produces empty order arguments. A missing historical entity is not fixed by changing Gold or recalling a stale order state. |
| Planner decision | context_loss plans get_order/track_shipment with empty arguments and extra knowledge calls. The raw failed trajectories are retained. Memory must supply the user-mentioned entity; any additional planner policy change requires its own evidence/arm. |
| Tool argument error | Three invalid_arguments failures in context_loss; existing tool validation rejected them. This is separate from an API error or an ownership refusal. |
| Structured output truncation | Requests11,61,75,80: max_tokens256, completion_tokens256, finish_reason=length and invalid JSON. They follow generate700 in the five-stage AGENT turn. Source-chain attribution is FaithfulnessChecker.check; raw answer text was not saved, so exact checker-payload hash attribution is unavailable. Intent and Router hashes were separately reconstructed and did not match those four events. |
| Business refusal | Six response.refused flags among valid turns are observations, not necessarily correct security refusals. Argument-binding/owner/session/injection controls were not evaluated; don't infer they passed. |
| Test budget interruption | greeting had raw P1 PASS after fallback but 0 real requests and was correctly excluded as budget ERROR. Five other controls NOT_RUN. Not a model reasoning failure. |

Three changed-state variants fail the read-observation oracle; no forbidden mutation was observed. Seven reference failures: context_loss and the stable/changed pronoun variants for each ORD10001/2/3. Main original result remains task2/9, reference0/7, selection64.71%, arguments58.82%, environment6/9, 80HTTP including probe and58342 tokens.

## Calls and token cost

See p2_evidence/P2-A-analysis.json for each case. context_loss:10calls/8408tokens; six freshness cases:9calls each/6296–6623tokens; order_lookup:5/3558; explicit_target_change:10/7576. Probe1/61. Four malformed judge responses are not four transport retries. New Memory selection/summary must not silently add paid calls, and offline estimated input sizes must never be reported as billed tokens.

## Six-case supplement — PLAN ONLY, NOT_RUN

Cases: greeting, argument_binding, cancel_pending, foreign_order, cross_user_session, injection. Use a NEW Run ID (`p2_pre_memory_supplement_01` reserved), isolated checkout at the pre-P2 commit above, same frozen Gold, model/configuration/temperature0/per-node caps, fixed seed time, fresh SQLite per case, no external tracing. Do not use the P2 source or JSON fix for this pre-P2 baseline.

Initial estimate12–25 HTTP calls plus probe,10000–20000 tokens; hard caps40requests/30000tokens, concurrency1, no automatic retries, stop and preserve partial results. This is an estimate based on observed5–10calls/query and security early exits, not a guaranteed cost. Currency cost is UNKNOWN until current account/model pricing is checked at execution. **Explicit user authorization for additional API fees is required before any request.** No supplement run was created or executed in P2.

## Independent structured-output repair

Reliability changes have their own commit/tests/P2_JSON_RELIABILITY.md. Detect truncated structured responses, label judge invalid output separately from API failures, and configure a bounded judge output allowance. No automatic retry or model-quality gain is claimed. Memory-only offline arms share this reliability behavior so it cancels in comparisons; pre-P2 real results remain unmodified and paid Memory/JSON validation stays NOT_RUN.
