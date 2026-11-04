# P2 retained offline failures

Real-model arms: NOT_RUN. New paid calls/tokens0. Frozen Gold and original scores remain unchanged. Initial and reviewed snapshots retained.

## M0 (OFFLINE_SCRIPTED)

| Case | Status | Reasons |
|---|---|---|
| foreign_order | FAIL | turn:0:trajectory_invalid |
| context_loss | FAIL | turn:1:missing_tool; turn:1:trajectory_invalid; turn:1:wrong_arguments |
| owner_ORD10001_other | FAIL | turn:0:trajectory_invalid |
| owner_ORD10001_anonymous | FAIL | turn:0:trajectory_invalid |
| owner_ORD10002_other | FAIL | turn:0:trajectory_invalid |
| owner_ORD10002_anonymous | FAIL | turn:0:trajectory_invalid |
| owner_ORD10003_other | FAIL | turn:0:trajectory_invalid |
| owner_ORD10003_anonymous | FAIL | turn:0:trajectory_invalid |
| freshness_ORD10001_pronoun_stable | FAIL | turn:1:missing_tool; turn:1:trajectory_invalid; turn:1:wrong_arguments |
| freshness_ORD10001_pronoun_changed | FAIL | missing_observation:get_order; turn:1:missing_tool; turn:1:trajectory_invalid; turn:1:wrong_arguments |
| freshness_ORD10002_pronoun_stable | FAIL | turn:1:missing_tool; turn:1:trajectory_invalid; turn:1:wrong_arguments |
| freshness_ORD10002_pronoun_changed | FAIL | missing_observation:get_order; turn:1:missing_tool; turn:1:trajectory_invalid; turn:1:wrong_arguments |
| freshness_ORD10003_pronoun_stable | FAIL | turn:1:missing_tool; turn:1:trajectory_invalid; turn:1:wrong_arguments |
| freshness_ORD10003_pronoun_changed | FAIL | missing_observation:get_order; turn:1:missing_tool; turn:1:trajectory_invalid; turn:1:wrong_arguments |
| hr01 | FAIL | turn:1:missing_tool; turn:1:trajectory_invalid; turn:1:wrong_arguments |
| hr02 | FAIL | turn:1:missing_tool; turn:1:trajectory_invalid; turn:1:wrong_arguments |
| hr03 | FAIL | turn:1:missing_tool; turn:1:trajectory_invalid; turn:1:wrong_arguments |
| hr04 | FAIL | turn:7:missing_tool; turn:7:trajectory_invalid; turn:7:wrong_arguments |
| hr05 | FAIL | turn:2:missing_tool; turn:2:trajectory_invalid; turn:2:wrong_arguments |
| hr06 | FAIL | turn:2:missing_tool; turn:2:trajectory_invalid; turn:2:wrong_arguments |
| hr07 | FAIL | missing_observation:get_order; turn:1:missing_tool; turn:1:trajectory_invalid; turn:1:wrong_arguments |
| hr08 | FAIL | missing_observation:get_order; turn:1:missing_tool; turn:1:trajectory_invalid; turn:1:wrong_arguments |
| hr09 | FAIL | missing_observation:get_order; turn:1:missing_tool; turn:1:trajectory_invalid; turn:1:wrong_arguments |
| hr10 | FAIL | turn:0:trajectory_invalid |
| p2_long_window | FAIL | missing_observation:get_order; turn:0:trajectory_invalid; turn:7:missing_tool; turn:7:trajectory_invalid; turn:7:wrong_arguments |

## M1 (OFFLINE_SCRIPTED)

| Case | Status | Reasons |
|---|---|---|
| foreign_order | FAIL | turn:0:trajectory_invalid |
| owner_ORD10001_other | FAIL | turn:0:trajectory_invalid |
| owner_ORD10001_anonymous | FAIL | turn:0:trajectory_invalid |
| owner_ORD10002_other | FAIL | turn:0:trajectory_invalid |
| owner_ORD10002_anonymous | FAIL | turn:0:trajectory_invalid |
| owner_ORD10003_other | FAIL | turn:0:trajectory_invalid |
| owner_ORD10003_anonymous | FAIL | turn:0:trajectory_invalid |
| hr01 | FAIL | turn:1:missing_tool; turn:1:trajectory_invalid; turn:1:wrong_arguments |
| hr02 | FAIL | turn:1:missing_tool; turn:1:trajectory_invalid; turn:1:wrong_arguments |
| hr03 | FAIL | turn:1:missing_tool; turn:1:trajectory_invalid; turn:1:wrong_arguments |
| hr04 | FAIL | turn:7:missing_tool; turn:7:trajectory_invalid; turn:7:wrong_arguments |
| hr05 | FAIL | turn:2:missing_tool; turn:2:trajectory_invalid; turn:2:wrong_arguments |
| hr06 | FAIL | turn:2:missing_tool; turn:2:trajectory_invalid; turn:2:wrong_arguments |
| hr07 | FAIL | missing_observation:get_order; turn:1:missing_tool; turn:1:trajectory_invalid; turn:1:wrong_arguments |
| hr08 | FAIL | missing_observation:get_order; turn:1:missing_tool; turn:1:trajectory_invalid; turn:1:wrong_arguments |
| hr09 | FAIL | missing_observation:get_order; turn:1:missing_tool; turn:1:trajectory_invalid; turn:1:wrong_arguments |
| p2_long_window | FAIL | missing_observation:get_order; turn:0:trajectory_invalid; turn:7:missing_tool; turn:7:trajectory_invalid; turn:7:wrong_arguments |

## M2 (OFFLINE_SCRIPTED)

| Case | Status | Reasons |
|---|---|---|
| foreign_order | FAIL | turn:0:trajectory_invalid |
| owner_ORD10001_other | FAIL | turn:0:trajectory_invalid |
| owner_ORD10001_anonymous | FAIL | turn:0:trajectory_invalid |
| owner_ORD10002_other | FAIL | turn:0:trajectory_invalid |
| owner_ORD10002_anonymous | FAIL | turn:0:trajectory_invalid |
| owner_ORD10003_other | FAIL | turn:0:trajectory_invalid |
| owner_ORD10003_anonymous | FAIL | turn:0:trajectory_invalid |
| hr01 | FAIL | turn:1:missing_tool; turn:1:trajectory_invalid; turn:1:wrong_arguments |
| hr02 | FAIL | turn:1:missing_tool; turn:1:trajectory_invalid; turn:1:wrong_arguments |
| hr03 | FAIL | turn:1:missing_tool; turn:1:trajectory_invalid; turn:1:wrong_arguments |
| hr04 | FAIL | turn:7:missing_tool; turn:7:trajectory_invalid; turn:7:wrong_arguments |
| hr05 | FAIL | turn:2:missing_tool; turn:2:trajectory_invalid; turn:2:wrong_arguments |
| hr06 | FAIL | turn:2:missing_tool; turn:2:trajectory_invalid; turn:2:wrong_arguments |
| hr07 | FAIL | missing_observation:get_order; turn:1:missing_tool; turn:1:trajectory_invalid; turn:1:wrong_arguments |
| hr08 | FAIL | missing_observation:get_order; turn:1:missing_tool; turn:1:trajectory_invalid; turn:1:wrong_arguments |
| hr09 | FAIL | missing_observation:get_order; turn:1:missing_tool; turn:1:trajectory_invalid; turn:1:wrong_arguments |
| p2_long_window | FAIL | turn:0:trajectory_invalid; turn:7:trajectory_invalid |

## M3 (OFFLINE_SCRIPTED)

| Case | Status | Reasons |
|---|---|---|
| foreign_order | FAIL | turn:0:trajectory_invalid |
| owner_ORD10001_other | FAIL | turn:0:trajectory_invalid |
| owner_ORD10001_anonymous | FAIL | turn:0:trajectory_invalid |
| owner_ORD10002_other | FAIL | turn:0:trajectory_invalid |
| owner_ORD10002_anonymous | FAIL | turn:0:trajectory_invalid |
| owner_ORD10003_other | FAIL | turn:0:trajectory_invalid |
| owner_ORD10003_anonymous | FAIL | turn:0:trajectory_invalid |
| hr01 | FAIL | turn:1:missing_tool; turn:1:trajectory_invalid; turn:1:wrong_arguments |
| hr02 | FAIL | turn:1:missing_tool; turn:1:trajectory_invalid; turn:1:wrong_arguments |
| hr03 | FAIL | turn:1:missing_tool; turn:1:trajectory_invalid; turn:1:wrong_arguments |
| hr04 | FAIL | turn:7:missing_tool; turn:7:trajectory_invalid; turn:7:wrong_arguments |
| hr05 | FAIL | turn:2:missing_tool; turn:2:trajectory_invalid; turn:2:wrong_arguments |
| hr06 | FAIL | turn:2:missing_tool; turn:2:trajectory_invalid; turn:2:wrong_arguments |
| hr07 | FAIL | missing_observation:get_order; turn:1:missing_tool; turn:1:trajectory_invalid; turn:1:wrong_arguments |
| hr08 | FAIL | missing_observation:get_order; turn:1:missing_tool; turn:1:trajectory_invalid; turn:1:wrong_arguments |
| hr09 | FAIL | missing_observation:get_order; turn:1:missing_tool; turn:1:trajectory_invalid; turn:1:wrong_arguments |
| p2_long_window | FAIL | turn:0:trajectory_invalid; turn:7:trajectory_invalid |

The rule provider produces identical correctness outcomes. M1/M2/M3 still fail9held-out cases; long-window Task staysFAIL even though M2/M3fresh read/state/arguments are correct, because existing Planner adds track_shipment outside the strict allowed trajectory. No Planner policy or Gold was changed to raise scores.

Independent final review policy-routing and M1window regressions are separate development tests, not held-out tuning; both were fixed RED/GREEN with an isolated checkpoint.
