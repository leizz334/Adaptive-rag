# P2-QA real paired DeepSeek validation

Run `20261104_QA_real_01`; status **PARTIAL_TRANSPORT_UNCERTAIN**. Official endpoint `https://api.deepseek.com`, requested and observed model `deepseek-flash`. Source `c45f509f5e4260c34818df9bf48f2807dd1338b4`. Same application, Prompt, structured-output repair, Planner, tools, Gold, scorer, initial fixture and temperature zero across modes; only Memory changes. Modes rotate by case; each group has a fresh isolated SQLite database and no external tracing.

Historical baseline (9/15 valid, task2/9, reference0/7, 58,342tokens) is retained as historical reference only. It differs in source/reliability repair/caps/sample validity and is not a causal before/after control. This experiment compares three arms of the same P2 implementation, before QC changes.

| Mode | Task success (all attempted) | Reference binding | Tool selection | Arguments | Environment | HTTP | Tokens | Truncations |
|---|---|---|---|---|---|---|---|---|
|M0|1/7|0/6|0.769|0.538|0.714|62|49511|2|
|M1|7/7|6/6|1.000|1.000|1.000|66|51470|1|
|M2|7/7|6/6|1.000|1.000|1.000|65|50897|0|

Task success follows the original strict oracle, including required tool trajectory and environment checks. Reference binding separately requires a fresh final-turn get_order of the initial target and no other target read; this does not replace strict task success. Model-invalid outputs recovered by application fallback remain in the all-attempted denominator. `analysis.json` also reports valid-output subset counts; excluding invalid outputs can bias comparisons, so it is secondary.

| Case | M0 | M1 | M2 |
|---|---|---|---|
|order_lookup|PASS|PASS|PASS|
|context_loss|FAIL|PASS|PASS|
|freshness_ORD10001_pronoun_stable|FAIL|PASS|PASS|
|freshness_ORD10001_pronoun_changed|FAIL|PASS|PASS|
|freshness_ORD10002_pronoun_stable|FAIL|PASS|PASS|
|freshness_ORD10002_pronoun_changed|FAIL|PASS|PASS|
|freshness_ORD10003_pronoun_stable|FAIL|PASS|PASS|
|freshness_ORD10003_pronoun_changed|NOT_RUN|NOT_RUN|NOT_RUN|
|explicit_target_change|NOT_RUN|NOT_RUN|NOT_RUN|
|greeting|NOT_RUN|NOT_RUN|NOT_RUN|

## Usage, latency and reliability

Total including probe: 194 HTTP attempts; 151,933 reported tokens; 155,899 conservatively accounted tokens; peak-price estimate US$0.078517. Unknown usage requests: 1. All calls share the same350HTTP/300,000token/US$3 ledger; no retry loops. HTTP failures: 0; uncertain pending: 1. Total HTTP latency 331.454s.

| Mode | Prompt tokens | Completion tokens | Mean task ms | P95 task ms | Mean HTTP ms | P95 HTTP ms | Invalid groups |
|---|---|---|---|---|---|---|---|
|M0|38077|11434|16247.2|24584.5|1776.6|3244.9|1|
|M1|39674|11796|16588.4|19329.3|1729.3|2637.3|1|
|M2|39126|11771|15824.5|19266.9|1658.3|2737.9|0|

Errors by request stage (raw public completions retained in local request ledger, hidden reasoning excluded):

```json
[
  {
    "group": "freshness_ORD10002_pronoun_stable:M1",
    "stage": "planner",
    "error": "truncated",
    "finish": [
      "length"
    ]
  },
  {
    "group": "freshness_ORD10003_pronoun_stable:M0",
    "stage": "planner",
    "error": "truncated",
    "finish": [
      "length"
    ]
  },
  {
    "group": "freshness_ORD10003_pronoun_stable:M0",
    "stage": "judge",
    "error": "truncated",
    "finish": [
      "length"
    ]
  }
]
```

No output-cap or JSON-repair change is introduced between arms. Truncation differences are stochastic observations, not a separately measured repair gain. Missing-tool and argument errors are retained in the original scores and executor events; failed task reasons remain in results.json. A correct entity does not guarantee Planner selection or task success.

## Reproduction and limits

Run configuration contains application/Prompt/data/harness hashes, effective settings fingerprints, endpoint, model, clock, limits and pricing source. Completed HTTP responses replay from the checkpoint, never by sending another request; PENDING uncertainty stops execution. Reproduction against the live API requires a fresh run directory and new budget authorization, and cannot guarantee identical outputs. The source must match the frozen P2 commit; QC source cannot resume this original-source run.

Original seven are known development checks, not an independent generalization set. M3 and real QC C0/C1 are NOT_RUN. No simulated results substitute for real arms. This small experiment does not establish universal accuracy, causal JSON-repair gains, production authentication or long-window M2 superiority (the selected seven fit recent history).

Cost uses published peak cache-miss input$0.30/M and output$1.20/M without discounts: https://api-docs.deepseek.com/quick_start/pricing/ . This is an estimate, not an invoice. API alias/backend and response randomness can change.

## Interrupted scope

Only seven complete case triples were obtained: one normal control plus six of the original seven references. The third-order changed-state triple and both remaining controls are NOT_RUN (the M1 first request was attempted but has no durable response). Thus the planned ten triples / three normal controls are not complete; QA quality remains PARTIAL. The per-mode task denominators above contain completed groups, including model-invalid outputs recovered by fallback; the uncertain additional M1 group is excluded from paired scoring and retained separately as infrastructure ERROR/UNSCORABLE.

The uncertain attempt is a ConnectError, not a model timeout or task failure. Conservatively reserved unknown usage: 3966 tokens. Provider-reported usage is not proof of the unsettled request's bill. No request replay, replacement run or extra real QC requests was issued after this stop. Measured HTTP latency excludes the uncertain attempt because its failure path did not persist elapsed time; that latency is NOT_RECORDED. Three truncations remain (Planner M0/M1 and Judge M0), independently of strict task outcomes. No generalized JSON repair benefit or M2-over-M1 gain is established.

## Legacy driver metadata correction

The unchanged eval.multiturn driver unconditionally labels model_evaluation=NOT_RUN, even with an injected real provider. Raw scoring payloads retain that inherited field. model_provenance.json corrects the provenance without overwriting raw evidence: all21 completed groups have durable real HTTP responses from the injected DeepSeekProvider. This is a test-driver metadata defect, separate from real truncations and the ConnectError. analysis.json removes offline-only summary defaults (paid_tokens=0/real_model_tokens=NOT_RUN). Use the request journal and provenance sidecar for real execution status.
