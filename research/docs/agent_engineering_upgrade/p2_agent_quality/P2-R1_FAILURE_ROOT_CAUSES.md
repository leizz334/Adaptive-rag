# P2-R1 first-node failure diagnosis

All16are reexecuted baseline-source offline cases, not real-model conclusions. Full user/history/context/entity source/Intent/Router/plan/tool/result/answer/DB/oracle evidence is linked in R0. One earliest primary error is counted per task. Accompanying score symptoms are retained without counting the same task multiple times.

Primary counts: {'PLANNER_EXTRA_TOOL': 13, 'ENTITY_BINDING_ERROR': 1, 'AMBIGUOUS_REFERENCE': 1, 'SCORER_CONTRACT_ISSUE': 1}. Surplus25calls by name: {'track_shipment': 21, 'get_order': 4}.

## Why environment15/16 can coexist with task0/16

The committed-state oracle permits unchanged state and finds any matching observation across the whole case. An initial valid read may satisfy it despite a later wrong/missing reference or surplus call. Task success additionally checks every turn's required/allowed/max trajectory, errors and proposal/refusal constraints. Thus environment15/16is neither final-answer accuracy nor per-turn freshness. Only the state-change case lacks a required new observation. No stale state substitution is inferred without an actual new read/answer trace.

## Cases

### nu01

First: **PLANNER_EXTRA_TOOL** at t0 Planner. Skill expands fixed get_order+track_shipment sequence outside narrow fullmatch; no per-goal evidence stop
Direct score failures: `turn:0:trajectory_invalid; turn:1:trajectory_invalid`.
Surplus: `[{"turn": 0, "tool": "track_shipment", "arguments": {"order_id": "ORD10003"}, "success": true, "branch": "execute_tools planned step", "needed_for_goal": false}, {"turn": 1, "tool": "track_shipment", "arguments": {"order_id": "ORD10003"}, "success": true, "branch": "execute_tools planned step", "needed_for_goal": false}]`.
Accompanying categories: PLANNER_EXTRA_TOOL. Plan/execute node invocations: 2/2 across all turns. Repair boundary: Planner. Evidence sufficient for these observed boundaries; real-model generalization remains untested.

### nu02

First: **PLANNER_EXTRA_TOOL** at t0 Planner. Skill expands fixed get_order+track_shipment sequence outside narrow fullmatch; no per-goal evidence stop
Direct score failures: `turn:0:trajectory_invalid; turn:1:trajectory_invalid`.
Surplus: `[{"turn": 0, "tool": "track_shipment", "arguments": {"order_id": "ORD10002"}, "success": true, "branch": "execute_tools planned step", "needed_for_goal": false}, {"turn": 1, "tool": "track_shipment", "arguments": {"order_id": "ORD10002"}, "success": true, "branch": "execute_tools planned step", "needed_for_goal": false}]`.
Accompanying categories: PLANNER_EXTRA_TOOL. Plan/execute node invocations: 2/2 across all turns. Repair boundary: Planner. Evidence sufficient for these observed boundaries; real-model generalization remains untested.

### nu03

First: **PLANNER_EXTRA_TOOL** at t0 Planner. Skill expands fixed get_order+track_shipment sequence outside narrow fullmatch; no per-goal evidence stop
Direct score failures: `turn:0:trajectory_invalid; turn:1:trajectory_invalid`.
Surplus: `[{"turn": 0, "tool": "track_shipment", "arguments": {"order_id": "ORD10001"}, "success": true, "branch": "execute_tools planned step", "needed_for_goal": false}, {"turn": 1, "tool": "track_shipment", "arguments": {"order_id": "ORD10001"}, "success": true, "branch": "execute_tools planned step", "needed_for_goal": false}]`.
Accompanying categories: PLANNER_EXTRA_TOOL. Plan/execute node invocations: 2/2 across all turns. Repair boundary: Planner. Evidence sufficient for these observed boundaries; real-model generalization remains untested.

### nu04

First: **PLANNER_EXTRA_TOOL** at t0 Planner. Skill expands fixed get_order+track_shipment sequence outside narrow fullmatch; no per-goal evidence stop
Direct score failures: `turn:0:trajectory_invalid; turn:1:trajectory_invalid; turn:2:trajectory_invalid`.
Surplus: `[{"turn": 0, "tool": "track_shipment", "arguments": {"order_id": "ORD10002"}, "success": true, "branch": "execute_tools planned step", "needed_for_goal": false}, {"turn": 1, "tool": "track_shipment", "arguments": {"order_id": "ORD10003"}, "success": true, "branch": "execute_tools planned step", "needed_for_goal": false}, {"turn": 2, "tool": "track_shipment", "arguments": {"order_id": "ORD10003"}, "success": true, "branch": "execute_tools planned step", "needed_for_goal": false}]`.
Accompanying categories: PLANNER_EXTRA_TOOL. Plan/execute node invocations: 3/3 across all turns. Repair boundary: Planner. Evidence sufficient for these observed boundaries; real-model generalization remains untested.

### nu05

First: **PLANNER_EXTRA_TOOL** at t0 Planner. Skill expands fixed get_order+track_shipment sequence outside narrow fullmatch; no per-goal evidence stop
Direct score failures: `turn:0:trajectory_invalid; turn:1:trajectory_invalid`.
Surplus: `[{"turn": 0, "tool": "track_shipment", "arguments": {"order_id": "ORD10003"}, "success": true, "branch": "execute_tools planned step", "needed_for_goal": false}, {"turn": 1, "tool": "track_shipment", "arguments": {"order_id": "ORD10001"}, "success": true, "branch": "execute_tools planned step", "needed_for_goal": false}]`.
Accompanying categories: PLANNER_EXTRA_TOOL. Plan/execute node invocations: 2/2 across all turns. Repair boundary: Planner. Evidence sufficient for these observed boundaries; real-model generalization remains untested.

### nu06

First: **ENTITY_BINDING_ERROR** at t0 ContextBuilder. Two explicit jointly requested read targets are treated as an unresolved singular reference; graph skips Intent/Router/Planner
Direct score failures: `turn:0:missing_tool; turn:0:trajectory_invalid; turn:0:wrong_arguments`.
Surplus: `[]`.
Accompanying categories: none. Plan/execute node invocations: 0/0 across all turns. Repair boundary: Context. Evidence sufficient for these observed boundaries; real-model generalization remains untested.

### nu07

First: **AMBIGUOUS_REFERENCE** at t0 ContextBuilder. Entity absent and reference form not recognized; no clarification or bound target before graph
Direct score failures: `turn:0:trajectory_invalid; turn:0:unexpected_tool_failure`.
Surplus: `[{"turn": 0, "tool": "get_order", "arguments": {}, "success": false, "branch": "execute_tools planned step", "needed_for_goal": false}, {"turn": 0, "tool": "track_shipment", "arguments": {}, "success": false, "branch": "execute_tools planned step", "needed_for_goal": false}]`.
Accompanying categories: PLANNER_EXTRA_TOOL. Plan/execute node invocations: 1/1 across all turns. Repair boundary: Context. Evidence sufficient for these observed boundaries; real-model generalization remains untested.

### nu08

First: **PLANNER_EXTRA_TOOL** at t0 Planner. Skill expands fixed get_order+track_shipment sequence outside narrow fullmatch; no per-goal evidence stop
Direct score failures: `missing_observation:get_order; turn:0:trajectory_invalid; turn:1:trajectory_invalid; turn:1:unexpected_tool_failure; turn:1:wrong_arguments`.
Surplus: `[{"turn": 0, "tool": "track_shipment", "arguments": {"order_id": "ORD10003"}, "success": true, "branch": "execute_tools planned step", "needed_for_goal": false}, {"turn": 1, "tool": "track_shipment", "arguments": {}, "success": false, "branch": "execute_tools planned step", "needed_for_goal": false}]`.
Accompanying categories: REFERENCE_RESOLUTION_ERROR, PLANNER_EXTRA_TOOL, MISSING_FRESH_OBSERVATION. Plan/execute node invocations: 2/2 across all turns. Repair boundary: Planner. Evidence sufficient for these observed boundaries; real-model generalization remains untested.

### nu09

First: **PLANNER_EXTRA_TOOL** at t0 Planner. Skill expands fixed get_order+track_shipment sequence outside narrow fullmatch; no per-goal evidence stop
Direct score failures: `turn:0:trajectory_invalid`.
Surplus: `[{"turn": 0, "tool": "track_shipment", "arguments": {"order_id": "ORD10002"}, "success": true, "branch": "execute_tools planned step", "needed_for_goal": false}]`.
Accompanying categories: none. Plan/execute node invocations: 1/1 across all turns. Repair boundary: Planner. Evidence sufficient for these observed boundaries; real-model generalization remains untested.

### nu10

First: **PLANNER_EXTRA_TOOL** at t0 Planner. Skill expands fixed get_order+track_shipment sequence outside narrow fullmatch; no per-goal evidence stop
Direct score failures: `turn:0:trajectory_invalid`.
Surplus: `[{"turn": 0, "tool": "track_shipment", "arguments": {"order_id": "ORD10001"}, "success": true, "branch": "execute_tools planned step", "needed_for_goal": false}]`.
Accompanying categories: none. Plan/execute node invocations: 1/1 across all turns. Repair boundary: Planner. Evidence sufficient for these observed boundaries; real-model generalization remains untested.

### nu11

First: **PLANNER_EXTRA_TOOL** at t0 Planner. Skill expands fixed get_order+track_shipment sequence outside narrow fullmatch; no per-goal evidence stop
Direct score failures: `turn:0:trajectory_invalid`.
Surplus: `[{"turn": 0, "tool": "track_shipment", "arguments": {"order_id": "ORD10002"}, "success": false, "branch": "execute_tools planned step", "needed_for_goal": false}]`.
Accompanying categories: none. Plan/execute node invocations: 1/1 across all turns. Repair boundary: Planner. Evidence sufficient for these observed boundaries; real-model generalization remains untested.

### nu12

First: **SCORER_CONTRACT_ISSUE** at t0 Goal/trajectory contract. Legitimate RAG retrieve_docs path does not emit registered search_knowledge tool event
Direct score failures: `turn:0:missing_tool; turn:0:trajectory_invalid; turn:0:wrong_arguments`.
Surplus: `[]`.
Accompanying categories: none. Plan/execute node invocations: 0/0 across all turns. Repair boundary: Evaluation dispute; no Gold change. Evidence sufficient for these observed boundaries; real-model generalization remains untested.

### nu13

First: **PLANNER_EXTRA_TOOL** at t0 Planner. Skill expands fixed get_order+track_shipment sequence outside narrow fullmatch; no per-goal evidence stop
Direct score failures: `turn:0:trajectory_invalid; turn:1:missing_tool; turn:1:trajectory_invalid; turn:1:wrong_arguments`.
Surplus: `[{"turn": 0, "tool": "track_shipment", "arguments": {"order_id": "ORD10001"}, "success": true, "branch": "execute_tools planned step", "needed_for_goal": false}]`.
Accompanying categories: SCORER_CONTRACT_ISSUE. Plan/execute node invocations: 1/1 across all turns. Repair boundary: Planner. Evidence sufficient for these observed boundaries; real-model generalization remains untested.

### nu14

First: **PLANNER_EXTRA_TOOL** at t0 Planner. Skill expands fixed get_order+track_shipment sequence outside narrow fullmatch; no per-goal evidence stop
Direct score failures: `turn:0:trajectory_invalid; turn:1:trajectory_invalid`.
Surplus: `[{"turn": 0, "tool": "get_order", "arguments": {"order_id": "ORD10001"}, "success": true, "branch": "execute_tools planned step", "needed_for_goal": false}, {"turn": 1, "tool": "get_order", "arguments": {"order_id": "ORD10001"}, "success": true, "branch": "execute_tools planned step", "needed_for_goal": false}]`.
Accompanying categories: PLANNER_EXTRA_TOOL. Plan/execute node invocations: 2/2 across all turns. Repair boundary: Planner. Evidence sufficient for these observed boundaries; real-model generalization remains untested.

### nu15

First: **PLANNER_EXTRA_TOOL** at t0 Planner. Skill expands fixed get_order+track_shipment sequence outside narrow fullmatch; no per-goal evidence stop
Direct score failures: `turn:0:trajectory_invalid; turn:1:trajectory_invalid`.
Surplus: `[{"turn": 0, "tool": "track_shipment", "arguments": {"order_id": "ORD10002"}, "success": true, "branch": "execute_tools planned step", "needed_for_goal": false}, {"turn": 1, "tool": "get_order", "arguments": {"order_id": "ORD10002"}, "success": true, "branch": "execute_tools planned step", "needed_for_goal": false}]`.
Accompanying categories: PLANNER_EXTRA_TOOL. Plan/execute node invocations: 2/2 across all turns. Repair boundary: Planner. Evidence sufficient for these observed boundaries; real-model generalization remains untested.

### nu16

First: **PLANNER_EXTRA_TOOL** at t0 Planner. Skill expands fixed get_order+track_shipment sequence outside narrow fullmatch; no per-goal evidence stop
Direct score failures: `turn:0:trajectory_invalid; turn:1:missing_tool; turn:1:trajectory_invalid; turn:1:wrong_arguments; turn:2:trajectory_invalid`.
Surplus: `[{"turn": 0, "tool": "track_shipment", "arguments": {"order_id": "ORD10003"}, "success": true, "branch": "execute_tools planned step", "needed_for_goal": false}, {"turn": 2, "tool": "track_shipment", "arguments": {"order_id": "ORD10003"}, "success": true, "branch": "execute_tools planned step", "needed_for_goal": false}]`.
Accompanying categories: SCORER_CONTRACT_ISSUE, PLANNER_EXTRA_TOOL. Plan/execute node invocations: 2/2 across all turns. Repair boundary: Planner. Evidence sufficient for these observed boundaries; real-model generalization remains untested.

## Mechanism and independent business judgment

Fixed skill expansion is the source of surplus steps, rather than an actual looping LangGraph replan: graph routes plan→execute→generate once per business turn. There is no recursive planning loop in these16. The executor runs every planned step even after the current goal already has sufficient evidence; it also runs shipment lookup after deterministic owner rejection. Tools themselves retain live Owner reads, so these repetitions do not show a permission bypass. Unknown-order plans contain empty arguments and fail schema validation instead of clarifying. A bounded same-turn read duplicate guard and parameter validation are justified; no new general autonomous loop is needed.

Correct header and shipment observations are different capabilities. Shipment tracking already calls get_visible_order, so an extra get_order solely to check the same Owner is unnecessary for shipment-only tasks. Conversely, real transport-history requests need track_shipment and must not be pruned because they contain 状态. Replace full-utterance status templates and unconditional skill ordering with per-goal required evidence, keeping unknown capabilities available to real Planner.

The ContextBuilder conflates multi-entity explicit requests with singular ambiguity and misses 张-style/no-ID references. History itself is loaded; absence of a selected entity does not establish history retrieval failure. The source-bound entity hint adds status wording even for shipment goals: preserve user semantics separately from grounding, and never use summary state as business authority. Current explicit targets generally override correctly; no executed wrong-order ID or owner leak is observed in this run.

Three policy turns (nu12,nu13,nu16) use legitimate retrieve_docs paths but frozen Gold requires the registered search_knowledge tool. Original metrics remain unchanged; this is a contract disagreement, not proof of wrong Router. Supplemental business judgment only certifies route/evidence availability; scripted fixed answers and scripted supported judge cannot establish answer semantics. Do not reroute legitimate policy traffic merely to satisfy a tool-event label. New datasets allow optional tool versus RAG policy paths, with the semantic-answer-judge limitation explicit.

All old16inputs are valid; old12ASCII? corruption is a separate historical issue. No output-schema error, repeated model-planning loop or hard-safety violation is observed here. P2-Q's real Planner512-token truncations and invalid order placeholders are distinct archived real failures; do not infer a real failure rate from this offline trace.

Required next changes: generic Context provenance/multi-target/clarification repair; task/evidence-aware Planner selection and structural arguments; same-turn bounded read deduplication retaining all permissions/freshness/HITL/idempotency. Each needs independent RED/GREEN and module-separated offline/real controls. No frozen Gold, dataset, max-call or success criterion change.
