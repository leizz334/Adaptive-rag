# P2-QB: retained held-out failure diagnosis

All nine retained failures are unsuitable evidence for a Memory implementation fix. The frozen inputs contain literal ASCII question marks where the metadata claims meaningful references. The original committed blob already contains those bytes. This is a fixture integrity defect and insufficient evidence for causal attribution to Memory, Planner or a real model. Historical scores remain FAIL and original artifacts/Gold remain unchanged.

## Integrity and scope

- Frozen fixture SHA256: `f1200034a4048b20768ba2097bc408097f760dd7974ae8fe2ed093a15343fefc`.
- Initial freeze: `a9320d9391cf462335ab62f92cbb77dd80d4f6e1`. `git show <commit>:<path>` equals current file byte for byte.
- 12 scenarios / 32 messages: all 32 contain U+003F question marks; none contains a non-ASCII character. This is not PowerShell mojibake or JSON display escaping. The precise authoring failure and intended text cannot be established.
- Reviewed artifact SHA256: `ed6b518ae0e0fa121aee33bb8d07669092eba6f0b50372dac9da139cf1db9aa6`; recorded source commit `40d86224e7f3f12b952a86a8aa6e1301c87199f2`.
- Read-only investigation of production/evaluation code and historical evidence; only this report and `qb_diagnosis.json` are written. No API calls, Gold updates, app/tests/eval edits, unseen dataset inspection, or commits.

## What the evidence establishes

All hr01-hr09 fail in all eight OFFLINE_RULE/OFFLINE_SCRIPTED M0-M3 arms: 72 failing case/arm pairs. Each failing turn has zero actual tool events, with one missing required `get_order`. The `wrong_arguments` reason follows from missing-call scoring (`eval/tool_scoring.py:41`, `eval/multiturn.py:118`); it does not prove an executed call used the wrong ID. `trajectory_invalid` is another consequence of the same missing call. hr07-hr09 additionally lack an observation of harness-updated order state.

No historical node span/state trace is available: `span_count=0`, `root_run_id=null`, tracing disabled in `eval/memory_ablation.py:165`. The artifact preserves tool events and scores, not context selection, node input/output, final answer, or assistant message history. A first failing production node cannot honestly be certified from this artifact. The earliest provable defective boundary is DATASET_INPUT, before ChatService.

## Source-supported chain and focused probe

`eval/multiturn.py:93` forwards `turn.message` unchanged. `ChatService._initial_state` loads session history/summary and calls `ContextBuilder.build` (`app/services/chat_service.py:187`). For a query made only of `?`, `app/memory/context.py:110-118` returns the query unchanged before consulting history/summary (`124-133`). Its known reference/order cues are absent. Changing Memory to infer an order from any punctuation-only request would manufacture intent and weaken ambiguity protection.

For the offline rule/scripted branches, question marks default to `faq_policy` (`app/agents/nodes/intent.py:55`); no overlay matches. Router chooses SINGLE (`app/retrieval/adaptive.py:123`); the graph follows retrieval to generation and bypasses Planner/executor (`app/agents/graph.py:33`). Earlier explicit `ORD...` messages can still trigger the order overlay (`intent_overlay.py:112`) and the existing order_tracking skill (`get_order` + `track_shipment`). This explains the retained prior events without reconstructing missing language.

A focused offline component probe was executed in Conda `adaptive-rag` for all nine final queries in each M0-M3 mode (36 probes). User-only prior histories were supplied, plus deliberately nonempty summary candidates. All returned unchanged query / no selected order / no clarification / FAQ_POLICY / SINGLE. This is fresh component evidence, not a recreation of historical full-runtime node traces. No network/provider or application startup was used. An existing LangChain deprecation warning appeared on import.

## Case evidence

Turn numbers are zero-based. Inputs below are verbatim synthetic fixture bytes, not recovered Chinese. User history is retained below; assistant history was not preserved and is not reconstructed. Full trajectories, prior successful event arguments, all eight arm scores and probe outputs are in `qb_diagnosis.json`.

### hr01

- Query t1: `"???????????????"`.
- Prior user history: `t0="?????? ORD10001 ????"`.
- Required: `get_order({"order_id": "ORD10001"})`. Actual failing-turn tools/arguments: `[]`.
- Prior actual successful calls: `t0 get_order({"order_id": "ORD10001"}); t0 track_shipment({"order_id": "ORD10001"})`.
- First provable failure: DATASET_INPUT. Direct mismatch: missing required read. Root: OTHER/DATASET_CORRUPTION; production-node attribution: INSUFFICIENT_EVIDENCE. Memory fix justified: no; Planner fix justified by this case: no.
- Minimal action: preserve this case/Gold/result; require an independently frozen, text-integrity-checked valid case before proposing a behavioral fix.

### hr02

- Query t1: `"?????????????"`.
- Prior user history: `t0="????? ORD10002 ????"`.
- Required: `get_order({"order_id": "ORD10002"})`. Actual failing-turn tools/arguments: `[]`.
- Prior actual successful calls: `t0 get_order({"order_id": "ORD10002"}); t0 track_shipment({"order_id": "ORD10002"})`.
- First provable failure: DATASET_INPUT. Direct mismatch: missing required read. Root: OTHER/DATASET_CORRUPTION; production-node attribution: INSUFFICIENT_EVIDENCE. Memory fix justified: no; Planner fix justified by this case: no.
- Minimal action: preserve this case/Gold/result; require an independently frozen, text-integrity-checked valid case before proposing a behavioral fix.

### hr03

- Query t1: `"????????????"`.
- Prior user history: `t0="?????? ORD10003 ????"`.
- Required: `get_order({"order_id": "ORD10003"})`. Actual failing-turn tools/arguments: `[]`.
- Prior actual successful calls: `t0 get_order({"order_id": "ORD10003"}); t0 track_shipment({"order_id": "ORD10003"})`.
- First provable failure: DATASET_INPUT. Direct mismatch: missing required read. Root: OTHER/DATASET_CORRUPTION; production-node attribution: INSUFFICIENT_EVIDENCE. Memory fix justified: no; Planner fix justified by this case: no.
- Minimal action: preserve this case/Gold/result; require an independently frozen, text-integrity-checked valid case before proposing a behavioral fix.

### hr04

- Query t7: `"?????????????????"`.
- Prior user history: `t0="?????? ORD10001 ????"; t1="???"; t2="???"; t3="???"; t4="???"; t5="???"; t6="??"`.
- Required: `get_order({"order_id": "ORD10001"})`. Actual failing-turn tools/arguments: `[]`.
- Prior actual successful calls: `t0 get_order({"order_id": "ORD10001"}); t0 track_shipment({"order_id": "ORD10001"})`.
- First provable failure: DATASET_INPUT. Direct mismatch: missing required read. Root: OTHER/DATASET_CORRUPTION; production-node attribution: INSUFFICIENT_EVIDENCE. Memory fix justified: no; Planner fix justified by this case: no.
- Minimal action: preserve this case/Gold/result; require an independently frozen, text-integrity-checked valid case before proposing a behavioral fix.

### hr05

- Query t2: `"??????????????"`.
- Prior user history: `t0="???? ORD10001 ????"; t1="????????? ORD10002 ????"`.
- Required: `get_order({"order_id": "ORD10002"})`. Actual failing-turn tools/arguments: `[]`.
- Prior actual successful calls: `t0 get_order({"order_id": "ORD10001"}); t0 track_shipment({"order_id": "ORD10001"}); t1 get_order({"order_id": "ORD10002"}); t1 track_shipment({"order_id": "ORD10002"})`.
- First provable failure: DATASET_INPUT. Direct mismatch: missing required read. Root: OTHER/DATASET_CORRUPTION; production-node attribution: INSUFFICIENT_EVIDENCE. Memory fix justified: no; Planner fix justified by this case: no.
- Minimal action: preserve this case/Gold/result; require an independently frozen, text-integrity-checked valid case before proposing a behavioral fix.

### hr06

- Query t2: `"???????????????"`.
- Prior user history: `t0="???? ORD10003 ????"; t1="??????? ORD10001 ????"`.
- Required: `get_order({"order_id": "ORD10001"})`. Actual failing-turn tools/arguments: `[]`.
- Prior actual successful calls: `t0 get_order({"order_id": "ORD10003"}); t0 track_shipment({"order_id": "ORD10003"}); t1 get_order({"order_id": "ORD10001"}); t1 track_shipment({"order_id": "ORD10001"})`.
- First provable failure: DATASET_INPUT. Direct mismatch: missing required read. Root: OTHER/DATASET_CORRUPTION; production-node attribution: INSUFFICIENT_EVIDENCE. Memory fix justified: no; Planner fix justified by this case: no.
- Minimal action: preserve this case/Gold/result; require an independently frozen, text-integrity-checked valid case before proposing a behavioral fix.

### hr07

- Query t1: `"????????????????"`.
- Prior user history: `t0="???? ORD10001 ????"`.
- Required: `get_order({"order_id": "ORD10001"})`. Actual failing-turn tools/arguments: `[]`.
- Prior actual successful calls: `t0 get_order({"order_id": "ORD10001"}); t0 track_shipment({"order_id": "ORD10001"})`.
- Harness state change before failed turn: `{"ORD10001": "delivered"}`. No fresh matching get_order observation followed; an earlier read is not a freshness substitute.
- First provable failure: DATASET_INPUT. Direct mismatch: missing required read. Root: OTHER/DATASET_CORRUPTION; production-node attribution: INSUFFICIENT_EVIDENCE. Memory fix justified: no; Planner fix justified by this case: no.
- Minimal action: preserve this case/Gold/result; require an independently frozen, text-integrity-checked valid case before proposing a behavioral fix.

### hr08

- Query t1: `"?????????????"`.
- Prior user history: `t0="???? ORD10003 ????"`.
- Required: `get_order({"order_id": "ORD10003"})`. Actual failing-turn tools/arguments: `[]`.
- Prior actual successful calls: `t0 get_order({"order_id": "ORD10003"}); t0 track_shipment({"order_id": "ORD10003"})`.
- Harness state change before failed turn: `{"ORD10003": "shipped"}`. No fresh matching get_order observation followed; an earlier read is not a freshness substitute.
- First provable failure: DATASET_INPUT. Direct mismatch: missing required read. Root: OTHER/DATASET_CORRUPTION; production-node attribution: INSUFFICIENT_EVIDENCE. Memory fix justified: no; Planner fix justified by this case: no.
- Minimal action: preserve this case/Gold/result; require an independently frozen, text-integrity-checked valid case before proposing a behavioral fix.

### hr09

- Query t1: `"??????????????"`.
- Prior user history: `t0="???? ORD10002 ????"`.
- Required: `get_order({"order_id": "ORD10002"})`. Actual failing-turn tools/arguments: `[]`.
- Prior actual successful calls: `t0 get_order({"order_id": "ORD10002"}); t0 track_shipment({"order_id": "ORD10002"})`.
- Harness state change before failed turn: `{"ORD10002": "refunding"}`. No fresh matching get_order observation followed; an earlier read is not a freshness substitute.
- First provable failure: DATASET_INPUT. Direct mismatch: missing required read. Root: OTHER/DATASET_CORRUPTION; production-node attribution: INSUFFICIENT_EVIDENCE. Memory fix justified: no; Planner fix justified by this case: no.
- Minimal action: preserve this case/Gold/result; require an independently frozen, text-integrity-checked valid case before proposing a behavioral fix.

## Diagnosis statistics and decision

| Finding | Count |
|---|---:|
| Failed cases examined | 9 |
| Failed case/arm pairs | 72 |
| Failing turns with no executed tool event | 72/72 |
| Primary OTHER/DATASET_CORRUPTION | 9 |
| Insufficient production causal attribution | 9 |
| Confirmed Memory implementation defects from these cases | 0 |
| Confirmed Planner implementation defects from these cases | 0 |
| Missing fresh-state observation cases | 3 |
| Focused component probes completed | 36/36 |

The contract still correctly reports a failure against frozen required calls. Its semantics conflict with the punctuation-only current messages, so 3/12 held-out success in M1-M3 cannot establish generalization and 9/12 failure cannot establish nine Memory defects. Eight offline arms share rules and are not independent model samples. No real-model behavior, stale generated answer, summary/entity loss or retrieval failure is proved here. Absence of proof of a defect is not proof of correctness.

The justified change is evaluation hygiene: reject suspicious punctuation-only linguistic fixture messages before freezing/execution; verify UTF-8 round trips and content independently; keep immutable original results and use a separate new dataset/run ID. Do not repair these Gold labels, reconstruct intended utterances, tune reference cues to the corrupted cases, or add a question-mark order fallback. A Planner redundancy issue from the separate intact long-window development test requires its own evidence and fixed-Memory comparison; it is not established by these nine cases.

Validation: original blob/hash equality, 72 reviewed tool-event/score checks and 36 component probes passed. No historical files were modified; full regression and new-run validation belong to the parent task.
