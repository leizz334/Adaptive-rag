# P2-Q final report

Phase status: **PARTIAL_PASS**. Engineering checks pass; real paired scope and quality/generalization remain PARTIAL. Original P1/P2 PARTIAL_PASS and historical real PARTIAL records are unchanged. No P3/P4 started.

QA: official DeepSeekProvider connected, requested/observed deepseek-flash. Seven complete triples (one control and six original reference cases): M0=1/7, M1=7/7, M2=7/7. Reference binding0/6 versus6/6 and6/6. This verifies existing recent-history benefit on completed known cases, not a new Memory-code gain or M2 superiority. The final original reference and two normal controls have no complete real triple and are NOT_RUN/UNSCORABLE. The planned three normal controls were not completed.

There were194HTTP attempts,193durable200responses,151,933provider-reported tokens and3,966tokens reserved for one uncertain ConnectError (155,899accounted). Peak-price estimatedUS$0.0785172 including reservation, not a settled invoice. Limits350/300,000/US$3 were respected. No paid retry or subsequent real QC run occurred. HTTP failures0, transport ConnectError1, timeouts0; uncertain billing/latency unresolved. Successful-request latency331.454s excludes the uncertain attempt. M0 task mean/P95=16.247/24.584s; M1=16.588/19.329s; M2=15.825/19.267s.

Three structured-output truncations remain: Planner M1, Planner M0, Judge M0 (all512tokencaps). Post-hoc production-schema parsing checked192completions and found only these three invalid outputs. Fallback-recovered tasks retain their errors. No reliability caps or JSON repair changed between real modes; differences do not prove Memory improves JSON reliability. Unchanged driver metadata incorrectly defaults model_evaluation toNOT_RUN; model_provenance.json corrects that infrastructure label using actual HTTP records without overwriting raw payloads.

QB: all nine old heldout failures traced to literalASCII? input corruption in the original frozen commit. No missing language or node spans were fabricated. Frozen Gold and FAILs remain. Memory changes justified by those inputs: zero. New generic tests retain no-guessing, proper entity binding, freshness and assistant exclusion. Old12 are diagnostic/regression now, not an independent semantic generalization benchmark.

## Attribution with fixed remaining factors

| Source variant | Memory | Original80 | Original7 | Old diagnostic12 | Long window | New16 final regression |
|---|---|---|---|---|---|---|
|Original P2 / Memory-only (identical source)|M0|66/80|0/7|2/12|0/1|0/16|
|Original P2 / Memory-only (identical source)|M1|73/80|7/7|3/12|0/1|0/16|
|Original P2 / Memory-only (identical source)|M2|73/80|7/7|3/12|0/1|0/16|
|Planner-only / Combined (identical source)|M0|73/80|0/7|2/12|0/1|0/16|
|Planner-only / Combined (identical source)|M1|80/80|7/7|3/12|0/1|0/16|
|Planner-only / Combined (identical source)|M2|80/80|7/7|3/12|1/1|0/16|

The four requested labels represent two distinct implementations because no Memory patch was justified: Memory-only equals original P2; Combined equals Planner-only. Results are reused for identical source, not represented as four independent experiments. All Gold/scorers and Memory settings are fixed per comparison. Prompt change belongs exclusively to QC. QC gains cannot be credited to Memory. Existing M2 summary plus QC removes the long-window strict trajectory failure; enabling Memory alone had already restored fresh entity/state but did not pass the original trajectory.

Memory-only code improvement:0 (no patch); existing real Memory switch improves six completed reference tasks. Planner-only improvement at fixedM2: original80 73→80; owner7 0→7; long-window0→1; old12 unchanged3. Combined equals Planner-only. New16 initial blinded C0=0/16 and initial candidateM2=8/16; after the independent transport-history safety/correctness repair, final regressionM2=0/16. The candidate improvement was withdrawn rather than preserved with an overbroad tool restriction. No generalized success claim is justified. All final16failures and old9failures remain visible. The new16 are now used evaluation/regression data and must not be called unseen for future work.

## Final verification and limitations

274pytest passed. Ruff check and format check passed (216files); Mypy passed137source files. Full original80 passes underM1/M2, and all original safety/Owner/Session/HITL/idempotency/JSON/provider/local-trace/disabled-external-trace regressions pass. Observed hard safety violations0. This does not establish trusted production identity; public cross-sessionM3 remains disabled and realM3=NOT_RUN.

110historical artifacts are byte-preserved; all historical task keys except the separate newp2_quality object are unchanged; original progress is a preserved prefix;20root user files including ignored.env are hash-preserved. Frozen datasets and scorers unchanged. All3,691 recorded tool-turn scores are recomputed by verify_quality.py. P1 agent_v2 driver compatibility was run separately in M0:13/14 task success, with the existing context_loss failure retained and no hard safety violation; see p1_compatibility.json. Reviewed source and new dataset hashes are frozen. No credential or hidden reasoning is present in phase artifacts. No external raw tracing was enabled.

Known infrastructure defects are explicitly retained: old dataset language corruption; inherited real-driver NOT_RUN metadata corrected by sidecar; initial C0 tool-count aggregator used the wrong nesting (recomputed_metrics/attribution are authoritative); uncertain transport-attempt latency not recorded. Offline latency is descriptive and confounded by concurrent checks, not a controlled performance benchmark. API alias/randomness, small sample and stopped scope limit reproducibility.

Remaining gates: reconcile request194 with provider billing before any paid resume; complete the remaining real pairs in an authorized new frozen-source run without repeating existing requests; improve generic Context/Planner coverage using a separate development set and future independently frozen evaluation; retain all failed checks and current narrow safety constraints. No extra calls are implied or authorized beyond this phase's stopped ledger.

## Recovery / Git

Each authorized task has its own checkpoint in feature-list.json/progress.txt. See those files and git log for exact hashes. Work is isolated oncodex/p2-quality from pushedP2c45f509; ordinary push only after final remote/branch/user-file verification. The final delivery checkpoint records actual push outcome. Never resume the paid runner merely because budget remains: its PENDING row is deliberately fail-closed. STOP after P2-Q; noP3/P4.


Delivery: root handed to codex/p2-quality;20user files including.env and110historical root artifact raw bytes preserved. Source and3691scores reverified in root. See handoff.json, feature-list.json, progress.txt and git upstream for delivery checkpoints. Initial normal push verified at58bb2c8; final metadata receives an ordinary push with remote HEAD verification.
