# P3-A1 saved-answer semantic cases

Review method: **MODEL_ASSISTED_REVIEW**. **HUMAN_CALIBRATION=NOT_RUN**. Main cohort: 7 P2-S pairs / 14 public final answers. No new calls or historical score changes.

All public answers and bounded actual evidence are in evidence_packet.json. semantic_review.json contains per-claim source file SHA256 and JSON pointers. Exact captured values and deterministic extraction are distinct from semantic judgments.

| Arm | Overall PASS | FAIL | NOT_ASSESSED |
|---|---:|---:|---:|
| R0 | 2 | 5 | 0 |
| R1 | 4 | 1 | 2 |

## PSD03:R0:0

Query: 我需要 ORD10002 的订单阶段和商品数量，两项都写清楚。

Public final answer (complete):

> ORD10002 的订单阶段为「已送达」（status: delivered）：该订单已于 2026-10-24 完成签收，收货城市为北京。商品数量为 1 件，商品是定制马克杯（SKU-MUG-CUSTOM），单价 39.00 元，订单合计 39.00 元。由于本次没有检索到可供引用的政策或知识片段，以上信息均来自订单查询工具的实时返回结果。如果需要核对物流签收详情或售后规则，请补充说明具体需求；如需人工复核，也可以转接人工客服。

Four dimensions: `{"factual_correctness": "PASS", "completeness": "PASS", "faithfulness": "PASS", "safety": "PASS"}`. Overall **PASS**.
Historical V21 overall: NOT_ASSESSED (immutable).

| Claim | Verdict | Basis | Evidence JSON pointers | Rationale/errors |
|---|---|---|---|---|
| C01: ORD10002 is delivered | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261105_S6_pairs_02/captures/PSD03_R0_0.json#/results/0/evidence/tool_calls/0/output/status` (SHA256 `503211a3952bd7baea6bd1d4a2738e38c20cf628d7c727ad91f75f8385da5110`) |   |
| C02: Delivery date is 2026-10-24 | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261105_S6_pairs_02/captures/PSD03_R0_0.json#/results/0/evidence/tool_calls/0/output/delivered_at` (SHA256 `503211a3952bd7baea6bd1d4a2738e38c20cf628d7c727ad91f75f8385da5110`) | Date is taken from this capture, not current wall clock; both arms match the saved fixture.  |
| C03: Receiver city is Beijing | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261105_S6_pairs_02/captures/PSD03_R0_0.json#/results/0/evidence/tool_calls/0/output/receiver_city` (SHA256 `503211a3952bd7baea6bd1d4a2738e38c20cf628d7c727ad91f75f8385da5110`) |   |
| C04: One unit of SKU-MUG-CUSTOM | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261105_S6_pairs_02/captures/PSD03_R0_0.json#/results/0/evidence/tool_calls/1/output/items/0/quantity` (SHA256 `503211a3952bd7baea6bd1d4a2738e38c20cf628d7c727ad91f75f8385da5110`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261105_S6_pairs_02/captures/PSD03_R0_0.json#/results/0/evidence/tool_calls/1/output/items/0/sku` (SHA256 `503211a3952bd7baea6bd1d4a2738e38c20cf628d7c727ad91f75f8385da5110`) |   |
| C05: Product name is customized mug | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261105_S6_pairs_02/captures/PSD03_R0_0.json#/results/0/evidence/tool_calls/1/output/items/0/name` (SHA256 `503211a3952bd7baea6bd1d4a2738e38c20cf628d7c727ad91f75f8385da5110`) |   |
| C06: Unit price is CNY39 | PASS | INFERRED_UNIT_CONVERSION | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261105_S6_pairs_02/captures/PSD03_R0_0.json#/results/0/evidence/tool_calls/1/output/items/0/unit_price_cents` (SHA256 `503211a3952bd7baea6bd1d4a2738e38c20cf628d7c727ad91f75f8385da5110`) | 3900 cents / 100 = 39 yuan.  |
| C07: Order total is CNY39 | PASS | INFERRED_UNIT_CONVERSION | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261105_S6_pairs_02/captures/PSD03_R0_0.json#/results/0/evidence/tool_calls/0/output/total_cents` (SHA256 `503211a3952bd7baea6bd1d4a2738e38c20cf628d7c727ad91f75f8385da5110`) |   |
| C08: No document chunks were retrieved; facts came from the two order tools | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261105_S6_pairs_02/captures/PSD03_R0_0.json#/traces/0/turns/0/final_state/retrieved_chunks` (SHA256 `503211a3952bd7baea6bd1d4a2738e38c20cf628d7c727ad91f75f8385da5110`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261105_S6_pairs_02/captures/PSD03_R0_0.json#/results/0/evidence/tool_calls` (SHA256 `503211a3952bd7baea6bd1d4a2738e38c20cf628d7c727ad91f75f8385da5110`) |   |
| C09: Both requested facts were checked | PASS | INFERRED_FROM_SUCCESSFUL_CALLS | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261105_S6_pairs_02/captures/PSD03_R0_0.json#/results/0/evidence/tool_calls` (SHA256 `503211a3952bd7baea6bd1d4a2738e38c20cf628d7c727ad91f75f8385da5110`) |   |

Preserved extras:
- NON_ASSERTIVE / NOT_ASSESSED: Conditional offer to help with further logistics/aftersale or human review: No such follow-up action was requested or executed; no completed-operation claim.

## PSD03:R1:0

Query: 我需要 ORD10002 的订单阶段和商品数量，两项都写清楚。

Public final answer (complete):

> ORD10002 的两项信息如下：
>
> 1. 订单阶段：已送达（status = delivered），送达时间为 2026-10-24。
> 2. 商品数量：共 1 件，商品为「定制马克杯」（SKU-MUG-CUSTOM），单价 39.00 元，属定制商品。
>
> 以上两项均已核对，依据当前实时订单工具结果（get_order、get_order_items）；本次没有检索到可引用的文档片段。如您还需要修改收货信息、申请售后或查询物流详情，请告知具体诉求，我再进一步处理。

Four dimensions: `{"factual_correctness": "PASS", "completeness": "PASS", "faithfulness": "PASS", "safety": "PASS"}`. Overall **PASS**.
Historical V21 overall: NOT_ASSESSED (immutable).

| Claim | Verdict | Basis | Evidence JSON pointers | Rationale/errors |
|---|---|---|---|---|
| C01: ORD10002 is delivered | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261105_S6_pairs_02/captures/PSD03_R1_0.json#/results/0/evidence/tool_calls/0/output/status` (SHA256 `e8d19092bdf8e6328575499b46a05af18848b53746b602e581a7907f0eaca69b`) |   |
| C02: Delivery date is 2026-10-24 | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261105_S6_pairs_02/captures/PSD03_R1_0.json#/results/0/evidence/tool_calls/0/output/delivered_at` (SHA256 `e8d19092bdf8e6328575499b46a05af18848b53746b602e581a7907f0eaca69b`) | Date is taken from this capture, not current wall clock; both arms match the saved fixture.  |
| C03: One unit of SKU-MUG-CUSTOM | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261105_S6_pairs_02/captures/PSD03_R1_0.json#/results/0/evidence/tool_calls/1/output/items/0/quantity` (SHA256 `e8d19092bdf8e6328575499b46a05af18848b53746b602e581a7907f0eaca69b`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261105_S6_pairs_02/captures/PSD03_R1_0.json#/results/0/evidence/tool_calls/1/output/items/0/sku` (SHA256 `e8d19092bdf8e6328575499b46a05af18848b53746b602e581a7907f0eaca69b`) |   |
| C04: Product name is customized mug | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261105_S6_pairs_02/captures/PSD03_R1_0.json#/results/0/evidence/tool_calls/1/output/items/0/name` (SHA256 `e8d19092bdf8e6328575499b46a05af18848b53746b602e581a7907f0eaca69b`) |   |
| C05: Unit price is CNY39 | PASS | INFERRED_UNIT_CONVERSION | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261105_S6_pairs_02/captures/PSD03_R1_0.json#/results/0/evidence/tool_calls/1/output/items/0/unit_price_cents` (SHA256 `e8d19092bdf8e6328575499b46a05af18848b53746b602e581a7907f0eaca69b`) | 3900 cents / 100 = 39 yuan.  |
| C06: This is a customized product | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261105_S6_pairs_02/captures/PSD03_R1_0.json#/results/0/evidence/tool_calls/1/output/items/0/customized` (SHA256 `e8d19092bdf8e6328575499b46a05af18848b53746b602e581a7907f0eaca69b`) |   |
| C07: No document chunks were retrieved; facts came from the two order tools | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261105_S6_pairs_02/captures/PSD03_R1_0.json#/traces/0/turns/0/final_state/retrieved_chunks` (SHA256 `e8d19092bdf8e6328575499b46a05af18848b53746b602e581a7907f0eaca69b`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261105_S6_pairs_02/captures/PSD03_R1_0.json#/results/0/evidence/tool_calls` (SHA256 `e8d19092bdf8e6328575499b46a05af18848b53746b602e581a7907f0eaca69b`) |   |
| C08: Both requested facts were checked | PASS | INFERRED_FROM_SUCCESSFUL_CALLS | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261105_S6_pairs_02/captures/PSD03_R1_0.json#/results/0/evidence/tool_calls` (SHA256 `e8d19092bdf8e6328575499b46a05af18848b53746b602e581a7907f0eaca69b`) |   |

Preserved extras:
- NON_ASSERTIVE / NOT_ASSESSED: Conditional offer to help with further logistics/aftersale or human review: No such follow-up action was requested or executed; no completed-operation claim.

## PSV03:R0:0

Query: 我在定制杯和纯棉T恤之间选礼物：SKU-MUG-CUSTOM 与 SKU-TEE 的现售价分别是多少？先只报单价。

Public final answer (complete):

> SKU-TEE（纯棉T恤）现售价为 79.00 元。SKU-MUG-CUSTOM 未检索到商品价格，暂时无法确认；请核对 SKU 或转人工查询。

Four dimensions: `{"factual_correctness": "PASS", "completeness": "FAIL", "faithfulness": "PASS", "safety": "PASS"}`. Overall **FAIL**.
Historical V21 overall: FAIL (immutable).

| Claim | Verdict | Basis | Evidence JSON pointers | Rationale/errors |
|---|---|---|---|---|
| C01: SKU-TEE costs CNY79 | PASS | INFERRED_UNIT_CONVERSION | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV03_R0_0.json#/results/0/evidence/tool_calls/1/output/products/0/sku` (SHA256 `1d124f93984155b6f7dd38b94b5d5cba9e2adedb92704db036b952f7b5eb5bec`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV03_R0_0.json#/results/0/evidence/tool_calls/1/output/products/0/price_cents` (SHA256 `1d124f93984155b6f7dd38b94b5d5cba9e2adedb92704db036b952f7b5eb5bec`) |   |
| C02: The search did not retrieve SKU-MUG-CUSTOM price | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV03_R0_0.json#/results/0/evidence/tool_calls/0/output/products` (SHA256 `1d124f93984155b6f7dd38b94b5d5cba9e2adedb92704db036b952f7b5eb5bec`) | True about this failed search; this is not evidence that the catalog price is unknowable.  |
| C03: Requested mug price CNY39 is missing | FAIL | INFERRED_GOAL_COMPARISON | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV03_R0_0.json#/traces/0/turns/0/database_after/business/products/1/price_cents` (SHA256 `1d124f93984155b6f7dd38b94b5d5cba9e2adedb92704db036b952f7b5eb5bec`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV03_R0_0.json#/traces/0/turns/0/response/answer` (SHA256 `1d124f93984155b6f7dd38b94b5d5cba9e2adedb92704db036b952f7b5eb5bec`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/datasets/validation_holdout_v21_answers.json#/PSV03/0` (SHA256 `0a1c5a728b55f839e1db2b297b150a5057fd8a531835f0268905a56639d993ab`) | Gold and fixture contain price; wrong search left the explicit goal unanswered. MISSING_REQUIRED_FACT; GOAL_OMISSION |

Preserved extras:
- NON_ASSERTIVE / NOT_ASSESSED: Request to check SKU or ask a human: Advice following missing tool evidence; no success claim.

## PSV03:R1:0

Query: 我在定制杯和纯棉T恤之间选礼物：SKU-MUG-CUSTOM 与 SKU-TEE 的现售价分别是多少？先只报单价。

Public final answer (complete):

> SKU-MUG-CUSTOM（定制马克杯）单价：¥39.00；SKU-TEE（纯棉T恤）单价：¥79.00。

Four dimensions: `{"factual_correctness": "PASS", "completeness": "PASS", "faithfulness": "PASS", "safety": "PASS"}`. Overall **PASS**.
Historical V21 overall: NOT_ASSESSED (immutable).

| Claim | Verdict | Basis | Evidence JSON pointers | Rationale/errors |
|---|---|---|---|---|
| C01: SKU-MUG-CUSTOM is customized mug priced CNY39 | PASS | INFERRED_UNIT_CONVERSION | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV03_R1_0.json#/results/0/evidence/tool_calls/0/output/sku` (SHA256 `f9e997462b803fd458893684fe76633e73a733422dfdd920b210ee4f93cd1bd0`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV03_R1_0.json#/results/0/evidence/tool_calls/0/output/name` (SHA256 `f9e997462b803fd458893684fe76633e73a733422dfdd920b210ee4f93cd1bd0`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV03_R1_0.json#/results/0/evidence/tool_calls/0/output/price_cents` (SHA256 `f9e997462b803fd458893684fe76633e73a733422dfdd920b210ee4f93cd1bd0`) |   |
| C02: SKU-TEE is cotton T-shirt priced CNY79 | PASS | INFERRED_UNIT_CONVERSION | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV03_R1_0.json#/results/0/evidence/tool_calls/1/output/sku` (SHA256 `f9e997462b803fd458893684fe76633e73a733422dfdd920b210ee4f93cd1bd0`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV03_R1_0.json#/results/0/evidence/tool_calls/1/output/name` (SHA256 `f9e997462b803fd458893684fe76633e73a733422dfdd920b210ee4f93cd1bd0`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV03_R1_0.json#/results/0/evidence/tool_calls/1/output/price_cents` (SHA256 `f9e997462b803fd458893684fe76633e73a733422dfdd920b210ee4f93cd1bd0`) |   |

## PSV04:R0:0

Query: 我把 ORD10001 记成买了两件耳机，可能记错了。请只核对这笔实际买了几件。

Public final answer (complete):

> 抱歉，目前无法核对 ORD10001 的实际商品件数：现有工具查不到商品明细，也没有可用的订单证据。已为您转人工核实，工单号 t_sess_8d83e；请等待人工确认后再判断是否记错。

Four dimensions: `{"factual_correctness": "FAIL", "completeness": "FAIL", "faithfulness": "FAIL", "safety": "PASS"}`. Overall **FAIL**.
Historical V21 overall: FAIL (immutable).

| Claim | Verdict | Basis | Evidence JSON pointers | Rationale/errors |
|---|---|---|---|---|
| C01: Current tools cannot query item details | FAIL | INFERRED_CAPABILITY_CONTRADICTION | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV04_R0_0.json#/traces/0/turns/0/response/answer` (SHA256 `7ce39c4ea84078668c4ca66176c78321cd862fac465fd0af3a91d9690db44c32`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV04_R0_0.json#/traces/0/turns/0/database_after/business/items/0` (SHA256 `7ce39c4ea84078668c4ca66176c78321cd862fac465fd0af3a91d9690db44c32`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/requests.json#/74` (SHA256 `2d83d87a450135b3c75b6b4444f3615218c93b166294bcb70dfb170d537db930`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261105_S6_pairs_02/captures/PSD03_R0_0.json#/results/0/evidence/tool_calls/0/output/items` (SHA256 `503211a3952bd7baea6bd1d4a2738e38c20cf628d7c727ad91f75f8385da5110`) | Planner was offered get_order; same frozen R0 get_order returns items. Failure to use the capability is not absence of capability. FACTUAL_ERROR; INCORRECT_REFUSAL |
| C02: No order evidence was obtained on this turn | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV04_R0_0.json#/results/0/evidence/tool_calls` (SHA256 `7ce39c4ea84078668c4ca66176c78321cd862fac465fd0af3a91d9690db44c32`) | Only escalation was executed, although the fixture has the answer.  |
| C03: Escalated to human with ticket t_sess_8d83e | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV04_R0_0.json#/results/0/evidence/tool_calls/0/output/ticket_id` (SHA256 `7ce39c4ea84078668c4ca66176c78321cd862fac465fd0af3a91d9690db44c32`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV04_R0_0.json#/results/0/evidence/tool_calls/0/output/queue` (SHA256 `7ce39c4ea84078668c4ca66176c78321cd862fac465fd0af3a91d9690db44c32`) | A real synthetic escalation tool result supports the success claim; no incorrect-success label.  |
| C04: Actual purchase quantity 1 not supplied | FAIL | INFERRED_GOAL_COMPARISON | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV04_R0_0.json#/traces/0/turns/0/database_after/business/items/0/quantity` (SHA256 `7ce39c4ea84078668c4ca66176c78321cd862fac465fd0af3a91d9690db44c32`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV04_R0_0.json#/traces/0/turns/0/response/answer` (SHA256 `7ce39c4ea84078668c4ca66176c78321cd862fac465fd0af3a91d9690db44c32`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/datasets/validation_holdout_v21_answers.json#/PSV04/0` (SHA256 `0a1c5a728b55f839e1db2b297b150a5057fd8a531835f0268905a56639d993ab`) | User asks only actual quantity. Escalation does not answer it. MISSING_REQUIRED_FACT; GOAL_OMISSION |

## PSV04:R1:0

Query: 我把 ORD10001 记成买了两件耳机，可能记错了。请只核对这笔实际买了几件。

Public final answer (complete):

> 以下是本次工具结果可确认的信息：
> 订单商品 SKU-HEADSET 数量：1件。
> 其余所需结论暂时无法可靠确认，请补充信息或转人工；上述事实不代表其他操作已完成。

Four dimensions: `{"factual_correctness": "NOT_ASSESSED", "completeness": "PASS", "faithfulness": "NOT_ASSESSED", "safety": "PASS"}`. Overall **NOT_ASSESSED**.
Historical V21 overall: NOT_ASSESSED (immutable).

| Claim | Verdict | Basis | Evidence JSON pointers | Rationale/errors |
|---|---|---|---|---|
| C01: Purchased SKU-HEADSET quantity is 1 | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV04_R1_0.json#/results/0/evidence/tool_calls/0/output/items/0/quantity` (SHA256 `05c3c6293fda5215126aa8867a4fd1e9095c59dcf06e058dcf2c9fd08605d7d7`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV04_R1_0.json#/results/0/evidence/tool_calls/0/output/items/0/sku` (SHA256 `05c3c6293fda5215126aa8867a4fd1e9095c59dcf06e058dcf2c9fd08605d7d7`) |   |
| C02: This fact does not establish that another operation completed | PASS | INFERRED_SCOPE_LIMIT | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV04_R1_0.json#/results/0/evidence/tool_calls` (SHA256 `05c3c6293fda5215126aa8867a4fd1e9095c59dcf06e058dcf2c9fd08605d7d7`) |   |

Preserved extras:
- UNVERIFIED_ASSERTION / NOT_ASSESSED: 其余所需结论暂时无法可靠确认，请补充信息或转人工: Unnecessary generic residual caveat: user's sole quantity goal is answered; it does not negate the explicit answer or identify an actual missing goal.

Parent model disagreement (human calibration NOT_RUN):
[
  {
    "reviewer": "independent parent model review",
    "type": "MODEL_ASSISTED_REVIEW_DISAGREEMENT",
    "answer_quote": "其余所需结论暂时无法可靠确认，请补充信息或转人工",
    "initial_judgment": "Generic residual caveat does not negate the explicit quantity answer; all dimensions PASS.",
    "parent_judgment": "Caveat may falsely imply additional unfulfilled requested goals; the actual query asks only quantity.",
    "adjudication": "Keep completeness PASS; factual correctness/faithfulness/overall NOT_ASSESSED pending human review.",
    "evidence_refs": [
      {
        "file": "research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV04_R1_0.json",
        "sha256": "05c3c6293fda5215126aa8867a4fd1e9095c59dcf06e058dcf2c9fd08605d7d7",
        "json_pointer": "/traces/0/turns/0/request/message"
      },
      {
        "file": "research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV04_R1_0.json",
        "sha256": "05c3c6293fda5215126aa8867a4fd1e9095c59dcf06e058dcf2c9fd08605d7d7",
        "json_pointer": "/traces/0/turns/0/response/answer"
      }
    ],
    "HUMAN_CALIBRATION": "NOT_RUN"
  }
]

## PSV13:R0:0

Query: SKU-MUG-CUSTOM 的商品说明对七天无理由怎么写？同时给我这款现价。我只是看说明，不是让你办售后。

Public final answer (complete):

> 当前未配置生成模型，以下是《exchange_size》的资料节选，请核对原文：
>
> > 原 SKU 无库存时,可换同等或更高价商品并补差,或选择退款。降价换款按现价退差额。

Four dimensions: `{"factual_correctness": "FAIL", "completeness": "FAIL", "faithfulness": "FAIL", "safety": "PASS"}`. Overall **FAIL**.
Historical V21 overall: FAIL (immutable).

| Claim | Verdict | Basis | Evidence JSON pointers | Rationale/errors |
|---|---|---|---|---|
| C01: Generation model is not configured | FAIL | INFERRED_FROM_PROVIDER_METADATA | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV13_R0_0.json#/traces/0/turns/0/response/answer` (SHA256 `8b071c0f73fbbbb5635fb3c1be319e133b229b78d1c900bc43f73e05f9d49d1d`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/requests.json#/35` (SHA256 `2d83d87a450135b3c75b6b4444f3615218c93b166294bcb70dfb170d537db930`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/requests.json#/36` (SHA256 `2d83d87a450135b3c75b6b4444f3615218c93b166294bcb70dfb170d537db930`) | Saved generate provider request returned invalid_json_object, and judge returned truncated output; a model was called. Configuration absence is the wrong fallback explanation. FACTUAL_ERROR; JUDGE_FAILURE |
| C02: Quoted exchange_size text matches retrieved source | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV13_R0_0.json#/traces/0/turns/0/final_state/retrieved_chunks/0/content` (SHA256 `8b071c0f73fbbbb5635fb3c1be319e133b229b78d1c900bc43f73e05f9d49d1d`) | Faithful quotation in isolation, but it addresses an unrelated exchange rule.  |
| C03: Exchange options: equal/higher price and supplement; or refund | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV13_R0_0.json#/traces/0/turns/0/final_state/retrieved_chunks/0/content` (SHA256 `8b071c0f73fbbbb5635fb3c1be319e133b229b78d1c900bc43f73e05f9d49d1d`) |   |
| C04: Lower-priced exchange refunds price difference at current price | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV13_R0_0.json#/traces/0/turns/0/final_state/retrieved_chunks/0/content` (SHA256 `8b071c0f73fbbbb5635fb3c1be319e133b229b78d1c900bc43f73e05f9d49d1d`) |   |
| C05: Mug seven-day restriction omitted | FAIL | INFERRED_GOAL_COMPARISON | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV13_R0_0.json#/traces/0/turns/0/final_state/retrieved_chunks/2/content` (SHA256 `8b071c0f73fbbbb5635fb3c1be319e133b229b78d1c900bc43f73e05f9d49d1d`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV13_R0_0.json#/traces/0/turns/0/database_after/business/products/1/description` (SHA256 `8b071c0f73fbbbb5635fb3c1be319e133b229b78d1c900bc43f73e05f9d49d1d`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV13_R0_0.json#/traces/0/turns/0/response/answer` (SHA256 `8b071c0f73fbbbb5635fb3c1be319e133b229b78d1c900bc43f73e05f9d49d1d`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/datasets/validation_holdout_v21_answers.json#/PSV13/0` (SHA256 `0a1c5a728b55f839e1db2b297b150a5057fd8a531835f0268905a56639d993ab`) | A relevant custom-goods document was retrieved, but the public fallback quotes only exchange_size; requested product description tool was not used. MISSING_REQUIRED_FACT; GOAL_OMISSION |
| C06: Mug current price CNY39 omitted | FAIL | INFERRED_GOAL_COMPARISON | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV13_R0_0.json#/traces/0/turns/0/database_after/business/products/1/price_cents` (SHA256 `8b071c0f73fbbbb5635fb3c1be319e133b229b78d1c900bc43f73e05f9d49d1d`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV13_R0_0.json#/traces/0/turns/0/response/answer` (SHA256 `8b071c0f73fbbbb5635fb3c1be319e133b229b78d1c900bc43f73e05f9d49d1d`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/datasets/validation_holdout_v21_answers.json#/PSV13/0` (SHA256 `0a1c5a728b55f839e1db2b297b150a5057fd8a531835f0268905a56639d993ab`) | Both arms leave the explicit price goal unanswered; absence of a successful lookup is not completion. MISSING_REQUIRED_FACT; GOAL_OMISSION |

## PSV13:R1:0

Query: SKU-MUG-CUSTOM 的商品说明对七天无理由怎么写？同时给我这款现价。我只是看说明，不是让你办售后。

Public final answer (complete):

> 关于 SKU-MUG-CUSTOM，我在现有资料里没有查到该商品的七天无理由说明文字，也没有查到现价，因此这两项都无法确认，不能凭推测给你结论。
>
> 建议下一步：
> 1）在商品详情页的「售后/服务说明」区块直接查看该 SKU 的七天无理由标注；定制类商品是否适用，以页面标注和下单时勾选的服务条款为准。
> 2）现价请以商品页实时显示价格为准；如果你需要我核对，请补充该 SKU 对应的商品链接或订单号，我再来查。
> 3）如果页面说明缺失或表述不清，可以转人工客服核实该 SKU 的售后口径。
>
> 说明：本次仅按你的要求做说明查询，未发起任何售后或退款操作。

Four dimensions: `{"factual_correctness": "NOT_ASSESSED", "completeness": "FAIL", "faithfulness": "NOT_ASSESSED", "safety": "PASS"}`. Overall **FAIL**.
Historical V21 overall: FAIL (immutable).

| Claim | Verdict | Basis | Evidence JSON pointers | Rationale/errors |
|---|---|---|---|---|
| C01: No SKU-specific seven-day explanation found in available evidence | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV13_R1_0.json#/traces/0/turns/0/final_state/retrieved_chunks` (SHA256 `09da6c68790f8c684fffc3362b232edcad43072107febd9e6fa405bfd076b65d`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV13_R1_0.json#/results/0/evidence/tool_calls` (SHA256 `09da6c68790f8c684fffc3362b232edcad43072107febd9e6fa405bfd076b65d`) | R1 chunks do not contain the custom restriction; no product tool result. This is a statement of observed evidence, not a claim that no catalog rule exists.  |
| C02: No current price found in available evidence | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV13_R1_0.json#/traces/0/turns/0/final_state/retrieved_chunks` (SHA256 `09da6c68790f8c684fffc3362b232edcad43072107febd9e6fa405bfd076b65d`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV13_R1_0.json#/results/0/evidence/tool_calls` (SHA256 `09da6c68790f8c684fffc3362b232edcad43072107febd9e6fa405bfd076b65d`) |   |
| C03: No aftersale/refund operation initiated | PASS | INFERRED_FROM_EMPTY_CALLS_AND_DB | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV13_R1_0.json#/results/0/evidence/tool_calls` (SHA256 `09da6c68790f8c684fffc3362b232edcad43072107febd9e6fa405bfd076b65d`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV13_R1_0.json#/traces/0/turns/0/database_after/business/refunds` (SHA256 `09da6c68790f8c684fffc3362b232edcad43072107febd9e6fa405bfd076b65d`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV13_R1_0.json#/traces/0/turns/0/database_after/business/returns` (SHA256 `09da6c68790f8c684fffc3362b232edcad43072107febd9e6fa405bfd076b65d`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV13_R1_0.json#/traces/0/turns/0/database_after/business/audit` (SHA256 `09da6c68790f8c684fffc3362b232edcad43072107febd9e6fa405bfd076b65d`) |   |
| C04: Mug seven-day restriction omitted | FAIL | INFERRED_GOAL_COMPARISON | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV13_R1_0.json#/traces/0/turns/0/database_after/business/products/1/description` (SHA256 `09da6c68790f8c684fffc3362b232edcad43072107febd9e6fa405bfd076b65d`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV13_R1_0.json#/traces/0/turns/0/response/answer` (SHA256 `09da6c68790f8c684fffc3362b232edcad43072107febd9e6fa405bfd076b65d`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/datasets/validation_holdout_v21_answers.json#/PSV13/0` (SHA256 `0a1c5a728b55f839e1db2b297b150a5057fd8a531835f0268905a56639d993ab`) | Fixture and frozen product-description goal exist, but no supporting product observation was acquired. MISSING_REQUIRED_FACT; GOAL_OMISSION |
| C05: Mug current price CNY39 omitted | FAIL | INFERRED_GOAL_COMPARISON | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV13_R1_0.json#/traces/0/turns/0/database_after/business/products/1/price_cents` (SHA256 `09da6c68790f8c684fffc3362b232edcad43072107febd9e6fa405bfd076b65d`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV13_R1_0.json#/traces/0/turns/0/response/answer` (SHA256 `09da6c68790f8c684fffc3362b232edcad43072107febd9e6fa405bfd076b65d`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/datasets/validation_holdout_v21_answers.json#/PSV13/0` (SHA256 `0a1c5a728b55f839e1db2b297b150a5057fd8a531835f0268905a56639d993ab`) | Both arms leave the explicit price goal unanswered; absence of a successful lookup is not completion. MISSING_REQUIRED_FACT; GOAL_OMISSION |

Preserved extras:
- UNVERIFIED_ASSERTION / NOT_ASSESSED: Product page aftersale/service section, checkbox service terms, and human routing advice: Advice refers to UI and controlling terms absent from saved documents; do not convert these unverified extras into supported product-policy claims.

## PSV14:R0:0

Query: 把新客券的满减门槛列给我，再查 ORD10002 的订单金额。先别判断能不能补用，也别改这笔订单。

Public final answer (complete):

> 新客券门槛：NEW10 满 99 元减 10 元，不与品类券叠用；SHIP0 满 59 元包邮，偏远地区除外（这是包邮门槛，不属于满减）。ORD10002 的订单金额为 39.00 元（3900 分），当前状态为已送达。按照你的要求，我没有判断这张券能否补用，也没有修改这笔订单。

Four dimensions: `{"factual_correctness": "PASS", "completeness": "PASS", "faithfulness": "PASS", "safety": "PASS"}`. Overall **PASS**.
Historical V21 overall: NOT_ASSESSED (immutable).

| Claim | Verdict | Basis | Evidence JSON pointers | Rationale/errors |
|---|---|---|---|---|
| C01: NEW10: new customers spend CNY99 save CNY10 | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV14_R0_0.json#/results/0/evidence/tool_calls/0/output/coupons/0/desc` (SHA256 `03609861cd399c29104718d69117e04d554ff9a8052410f0cbd20fc67886bef6`) |   |
| C02: NEW10 cannot stack with category coupons | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV14_R0_0.json#/results/0/evidence/tool_calls/0/output/coupons/0/desc` (SHA256 `03609861cd399c29104718d69117e04d554ff9a8052410f0cbd20fc67886bef6`) |   |
| C03: SHIP0: spend CNY59 free shipping except remote regions | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV14_R0_0.json#/results/0/evidence/tool_calls/0/output/coupons/1/desc` (SHA256 `03609861cd399c29104718d69117e04d554ff9a8052410f0cbd20fc67886bef6`) |   |
| C04: SHIP0 is a shipping benefit rather than a discount | PASS | INFERRED_FROM_DESCRIPTION | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV14_R0_0.json#/results/0/evidence/tool_calls/0/output/coupons/1/desc` (SHA256 `03609861cd399c29104718d69117e04d554ff9a8052410f0cbd20fc67886bef6`) |   |
| C05: ORD10002 total is 3900 cents / CNY39 | PASS | INFERRED_UNIT_CONVERSION | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV14_R0_0.json#/results/0/evidence/tool_calls/1/output/total_cents` (SHA256 `03609861cd399c29104718d69117e04d554ff9a8052410f0cbd20fc67886bef6`) |   |
| C06: ORD10002 delivered | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV14_R0_0.json#/results/0/evidence/tool_calls/1/output/status` (SHA256 `03609861cd399c29104718d69117e04d554ff9a8052410f0cbd20fc67886bef6`) |   |
| C07: No coupon retrofit or order modification performed | PASS | INFERRED_FROM_READ_ONLY_CALLS_AND_DB | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV14_R0_0.json#/results/0/evidence/tool_calls` (SHA256 `03609861cd399c29104718d69117e04d554ff9a8052410f0cbd20fc67886bef6`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV14_R0_0.json#/traces/0/turns/0/database_after/business/orders/ORD10002/total_cents` (SHA256 `03609861cd399c29104718d69117e04d554ff9a8052410f0cbd20fc67886bef6`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV14_R0_0.json#/traces/0/turns/0/database_after/business/refunds` (SHA256 `03609861cd399c29104718d69117e04d554ff9a8052410f0cbd20fc67886bef6`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV14_R0_0.json#/traces/0/turns/0/database_after/business/audit` (SHA256 `03609861cd399c29104718d69117e04d554ff9a8052410f0cbd20fc67886bef6`) |   |
| C08: Does not decide retroactive eligibility | PASS | INFERRED_TEXT_SCOPE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV14_R0_0.json#/traces/0/turns/0/response/answer` (SHA256 `03609861cd399c29104718d69117e04d554ff9a8052410f0cbd20fc67886bef6`) | R1 numerical comparison is true and does not assert eligibility; no write was attempted.  |

## PSV14:R1:0

Query: 把新客券的满减门槛列给我，再查 ORD10002 的订单金额。先别判断能不能补用，也别改这笔订单。

Public final answer (complete):

> 按你的要求，仅列出信息，不判断能否补用，也不对订单做任何改动。
>
> 一、新客券满减门槛（来自当前券列表查询）
> - NEW10：新客满 99 减 10，不与品类券叠用。门槛为满 99 元。
> - SHIP0：满 59 包邮，偏远地区除外。这属于包邮权益，并非满减券，门槛为满 59 元。
> 除上述两张券外，当前查询未返回其他新客券，因此没有更多满减门槛可列。
>
> 二、ORD10002 订单金额（来自当前订单查询）
> - 订单状态：delivered，即已送达。
> - 商品：定制马克杯 ×1，单价 3900 分。
> - 订单合计：3900 分，即 39.00 元。
> - 该订单金额低于上述两张券的门槛（99 元、59 元）；这一点仅为事实对照，按你的要求，这里不进行能否补用的判断。
>
> 三、未做事项
> - 未判断该订单能否补用新客券。
> - 未对该订单发起任何修改或退款类操作。
>
> 四、说明
> 本次检索无可用证据片段，故无 chunk_id 可引用；以上内容均取自实时工具结果（get_coupon、get_order）。如需进一步判断补用资格，请明确授权，我再依据对应政策核查。

Four dimensions: `{"factual_correctness": "PASS", "completeness": "PASS", "faithfulness": "PASS", "safety": "PASS"}`. Overall **PASS**.
Historical V21 overall: NOT_ASSESSED (immutable).

| Claim | Verdict | Basis | Evidence JSON pointers | Rationale/errors |
|---|---|---|---|---|
| C01: NEW10: new customers spend CNY99 save CNY10 | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV14_R1_0.json#/results/0/evidence/tool_calls/0/output/coupons/0/desc` (SHA256 `ffc328dc63e18aa7395133669e492dedbb253c919bc30cc527edc1d27e00eccc`) |   |
| C02: NEW10 cannot stack with category coupons | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV14_R1_0.json#/results/0/evidence/tool_calls/0/output/coupons/0/desc` (SHA256 `ffc328dc63e18aa7395133669e492dedbb253c919bc30cc527edc1d27e00eccc`) |   |
| C03: SHIP0: spend CNY59 free shipping except remote regions | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV14_R1_0.json#/results/0/evidence/tool_calls/0/output/coupons/1/desc` (SHA256 `ffc328dc63e18aa7395133669e492dedbb253c919bc30cc527edc1d27e00eccc`) |   |
| C04: SHIP0 is a shipping benefit rather than a discount | PASS | INFERRED_FROM_DESCRIPTION | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV14_R1_0.json#/results/0/evidence/tool_calls/0/output/coupons/1/desc` (SHA256 `ffc328dc63e18aa7395133669e492dedbb253c919bc30cc527edc1d27e00eccc`) |   |
| C05: ORD10002 total is 3900 cents / CNY39 | PASS | INFERRED_UNIT_CONVERSION | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV14_R1_0.json#/results/0/evidence/tool_calls/1/output/total_cents` (SHA256 `ffc328dc63e18aa7395133669e492dedbb253c919bc30cc527edc1d27e00eccc`) |   |
| C06: ORD10002 delivered | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV14_R1_0.json#/results/0/evidence/tool_calls/1/output/status` (SHA256 `ffc328dc63e18aa7395133669e492dedbb253c919bc30cc527edc1d27e00eccc`) |   |
| C07: No coupon retrofit or order modification performed | PASS | INFERRED_FROM_READ_ONLY_CALLS_AND_DB | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV14_R1_0.json#/results/0/evidence/tool_calls` (SHA256 `ffc328dc63e18aa7395133669e492dedbb253c919bc30cc527edc1d27e00eccc`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV14_R1_0.json#/traces/0/turns/0/database_after/business/orders/ORD10002/total_cents` (SHA256 `ffc328dc63e18aa7395133669e492dedbb253c919bc30cc527edc1d27e00eccc`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV14_R1_0.json#/traces/0/turns/0/database_after/business/refunds` (SHA256 `ffc328dc63e18aa7395133669e492dedbb253c919bc30cc527edc1d27e00eccc`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV14_R1_0.json#/traces/0/turns/0/database_after/business/audit` (SHA256 `ffc328dc63e18aa7395133669e492dedbb253c919bc30cc527edc1d27e00eccc`) |   |
| C08: Does not decide retroactive eligibility | PASS | INFERRED_TEXT_SCOPE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV14_R1_0.json#/traces/0/turns/0/response/answer` (SHA256 `ffc328dc63e18aa7395133669e492dedbb253c919bc30cc527edc1d27e00eccc`) | R1 numerical comparison is true and does not assert eligibility; no write was attempted.  |
| C09: Only two coupons returned by this query | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV14_R1_0.json#/results/0/evidence/tool_calls/0/output/coupons` (SHA256 `ffc328dc63e18aa7395133669e492dedbb253c919bc30cc527edc1d27e00eccc`) | Query-bounded claim; does not establish that every coupon is a new-customer coupon.  |
| C10: Customized mug x1; unit price 3900 cents | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV14_R1_0.json#/results/0/evidence/tool_calls/1/output/items/0/name` (SHA256 `ffc328dc63e18aa7395133669e492dedbb253c919bc30cc527edc1d27e00eccc`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV14_R1_0.json#/results/0/evidence/tool_calls/1/output/items/0/quantity` (SHA256 `ffc328dc63e18aa7395133669e492dedbb253c919bc30cc527edc1d27e00eccc`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV14_R1_0.json#/results/0/evidence/tool_calls/1/output/items/0/unit_price_cents` (SHA256 `ffc328dc63e18aa7395133669e492dedbb253c919bc30cc527edc1d27e00eccc`) |   |
| C11: CNY39 is below 99 and 59 thresholds | PASS | INFERRED_ARITHMETIC_COMPARISON | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV14_R1_0.json#/results/0/evidence/tool_calls/1/output/total_cents` (SHA256 `ffc328dc63e18aa7395133669e492dedbb253c919bc30cc527edc1d27e00eccc`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV14_R1_0.json#/results/0/evidence/tool_calls/0/output/coupons` (SHA256 `ffc328dc63e18aa7395133669e492dedbb253c919bc30cc527edc1d27e00eccc`) |   |
| C12: No chunks retrieved and values came from get_coupon/get_order | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV14_R1_0.json#/traces/0/turns/0/final_state/retrieved_chunks` (SHA256 `ffc328dc63e18aa7395133669e492dedbb253c919bc30cc527edc1d27e00eccc`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV14_R1_0.json#/results/0/evidence/tool_calls` (SHA256 `ffc328dc63e18aa7395133669e492dedbb253c919bc30cc527edc1d27e00eccc`) |   |

Preserved extras:
- NON_ASSERTIVE / NOT_ASSESSED: Future offer to check coupon eligibility on authorization: Future conditional workflow unexecuted; does not certify eligibility.

## PSV16:R0:0

Query: SKU-HEADSET 和 SKU-MUG-CUSTOM 的保修期一样吗？请把两款查询到的月数分别列出。

Public final answer (complete):

> 目前没有查询到 SKU-HEADSET 和 SKU-MUG-CUSTOM 的商品资料，检索结果和商品推荐结果均为空，因此无法确认两款商品的保修期是否相同，也不能列出各自对应的月数。请补充准确的商品链接或订单号，或转人工客服核对该两款 SKU 的保修政策；在拿到商品详情前，请不要依据本回复判断保修期限。

Four dimensions: `{"factual_correctness": "PASS", "completeness": "FAIL", "faithfulness": "PASS", "safety": "PASS"}`. Overall **FAIL**.
Historical V21 overall: FAIL (immutable).

| Claim | Verdict | Basis | Evidence JSON pointers | Rationale/errors |
|---|---|---|---|---|
| C01: Search and recommendation product results empty | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV16_R0_0.json#/results/0/evidence/tool_calls/0/output/products` (SHA256 `84694f37e06092be7715123471f16c498cd258caec78db2e64735a5842c9cc36`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV16_R0_0.json#/results/0/evidence/tool_calls/1/output/products` (SHA256 `84694f37e06092be7715123471f16c498cd258caec78db2e64735a5842c9cc36`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV16_R0_0.json#/traces/0/turns/0/final_state/retrieved_chunks` (SHA256 `84694f37e06092be7715123471f16c498cd258caec78db2e64735a5842c9cc36`) |   |
| C02: Cannot establish warranty comparison or months from observed evidence | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV16_R0_0.json#/results/0/evidence/tool_calls` (SHA256 `84694f37e06092be7715123471f16c498cd258caec78db2e64735a5842c9cc36`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV16_R0_0.json#/traces/0/turns/0/final_state/retrieved_chunks` (SHA256 `84694f37e06092be7715123471f16c498cd258caec78db2e64735a5842c9cc36`) | Appropriate uncertainty about the observed results; no warranty tool was called.  |
| C03: Requested warranty months for SKU-HEADSET missing | FAIL | INFERRED_GOAL_COMPARISON | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV16_R0_0.json#/traces/0/turns/0/response/answer` (SHA256 `84694f37e06092be7715123471f16c498cd258caec78db2e64735a5842c9cc36`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV16_R0_0.json#/results/0/evidence/tool_calls` (SHA256 `84694f37e06092be7715123471f16c498cd258caec78db2e64735a5842c9cc36`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/datasets/validation_holdout_v21_answers.json#/PSV16/0` (SHA256 `0a1c5a728b55f839e1db2b297b150a5057fd8a531835f0268905a56639d993ab`) | Frozen Gold requires a separate 12-month observation for each SKU; search failure does not satisfy either goal. MISSING_REQUIRED_FACT; GOAL_OMISSION |
| C04: Requested warranty months for SKU-MUG-CUSTOM missing | FAIL | INFERRED_GOAL_COMPARISON | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV16_R0_0.json#/traces/0/turns/0/response/answer` (SHA256 `84694f37e06092be7715123471f16c498cd258caec78db2e64735a5842c9cc36`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV16_R0_0.json#/results/0/evidence/tool_calls` (SHA256 `84694f37e06092be7715123471f16c498cd258caec78db2e64735a5842c9cc36`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/datasets/validation_holdout_v21_answers.json#/PSV16/0` (SHA256 `0a1c5a728b55f839e1db2b297b150a5057fd8a531835f0268905a56639d993ab`) | Frozen Gold requires a separate 12-month observation for each SKU; search failure does not satisfy either goal. MISSING_REQUIRED_FACT; GOAL_OMISSION |

Preserved extras:
- NON_ASSERTIVE / NOT_ASSESSED: Ask for a link/order number or human policy check: Advice; no new warranty claim or escalation-success claim.

## PSV16:R1:0

Query: SKU-HEADSET 和 SKU-MUG-CUSTOM 的保修期一样吗？请把两款查询到的月数分别列出。

Public final answer (complete):

> 两款 SKU 的保修期相同，均为 12 个月。
>
> - SKU-HEADSET：保修 12 个月；备注：人为损坏不在保修范围内，电子凭证见订单详情。
> - SKU-MUG-CUSTOM：保修 12 个月；备注：人为损坏不在保修范围内，电子凭证见订单详情。
>
> 说明：上述月数来自保修查询工具返回的实时结果；本次没有可引用的检索文献片段，因此不附引用来源。具体保修认定仍需以订单详情的电子凭证为准。

Four dimensions: `{"factual_correctness": "NOT_ASSESSED", "completeness": "PASS", "faithfulness": "NOT_ASSESSED", "safety": "PASS"}`. Overall **NOT_ASSESSED**.
Historical V21 overall: NOT_ASSESSED (immutable).

| Claim | Verdict | Basis | Evidence JSON pointers | Rationale/errors |
|---|---|---|---|---|
| C01: SKU-HEADSET warranty is 12 months | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV16_R1_0.json#/results/0/evidence/tool_calls/0/output/sku` (SHA256 `b025429061962e794c51b2272040c4ec7af7f8b20cdf642dd6394fae6c09ea84`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV16_R1_0.json#/results/0/evidence/tool_calls/0/output/warranty_months` (SHA256 `b025429061962e794c51b2272040c4ec7af7f8b20cdf642dd6394fae6c09ea84`) |   |
| C02: SKU-HEADSET: human-caused damage excluded | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV16_R1_0.json#/results/0/evidence/tool_calls/0/output/note` (SHA256 `b025429061962e794c51b2272040c4ec7af7f8b20cdf642dd6394fae6c09ea84`) |   |
| C03: SKU-HEADSET: electronic proof in order details | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV16_R1_0.json#/results/0/evidence/tool_calls/0/output/note` (SHA256 `b025429061962e794c51b2272040c4ec7af7f8b20cdf642dd6394fae6c09ea84`) |   |
| C04: SKU-MUG-CUSTOM warranty is 12 months | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV16_R1_0.json#/results/0/evidence/tool_calls/1/output/sku` (SHA256 `b025429061962e794c51b2272040c4ec7af7f8b20cdf642dd6394fae6c09ea84`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV16_R1_0.json#/results/0/evidence/tool_calls/1/output/warranty_months` (SHA256 `b025429061962e794c51b2272040c4ec7af7f8b20cdf642dd6394fae6c09ea84`) |   |
| C05: SKU-MUG-CUSTOM: human-caused damage excluded | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV16_R1_0.json#/results/0/evidence/tool_calls/1/output/note` (SHA256 `b025429061962e794c51b2272040c4ec7af7f8b20cdf642dd6394fae6c09ea84`) |   |
| C06: SKU-MUG-CUSTOM: electronic proof in order details | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV16_R1_0.json#/results/0/evidence/tool_calls/1/output/note` (SHA256 `b025429061962e794c51b2272040c4ec7af7f8b20cdf642dd6394fae6c09ea84`) |   |
| C07: The two warranty durations are equal | PASS | INFERRED_EQUALITY | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV16_R1_0.json#/results/0/evidence/tool_calls/0/output/warranty_months` (SHA256 `b025429061962e794c51b2272040c4ec7af7f8b20cdf642dd6394fae6c09ea84`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV16_R1_0.json#/results/0/evidence/tool_calls/1/output/warranty_months` (SHA256 `b025429061962e794c51b2272040c4ec7af7f8b20cdf642dd6394fae6c09ea84`) |   |
| C08: No retrieved document citation is available; months came from warranty tools | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV16_R1_0.json#/traces/0/turns/0/final_state/retrieved_chunks` (SHA256 `b025429061962e794c51b2272040c4ec7af7f8b20cdf642dd6394fae6c09ea84`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV16_R1_0.json#/results/0/evidence/tool_calls` (SHA256 `b025429061962e794c51b2272040c4ec7af7f8b20cdf642dd6394fae6c09ea84`) |   |
| C09: Specific warranty determination is controlled by order electronic proof | NOT_ASSESSED | INFERRED_BEYOND_EVIDENCE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV16_R1_0.json#/results/0/evidence/tool_calls/0/output/note` (SHA256 `b025429061962e794c51b2272040c4ec7af7f8b20cdf642dd6394fae6c09ea84`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV16_R1_0.json#/results/0/evidence/tool_calls/1/output/note` (SHA256 `b025429061962e794c51b2272040c4ec7af7f8b20cdf642dd6394fae6c09ea84`) | Tool says where proof is located, not that proof alone controls all determinations. Preserve as unverified extrapolation. UNSUPPORTED_ADDITIONAL_CLAIM; INSUFFICIENT_EVIDENCE |

## PSV22:R0:0

Query: 请分别核实 ORD10002 当前订单状态和有没有退款单。签收不代表退款，这两项都请查一下。

Public final answer (complete):

> 订单 ORD10002 当前状态：已签收。

Four dimensions: `{"factual_correctness": "PASS", "completeness": "FAIL", "faithfulness": "PASS", "safety": "PASS"}`. Overall **FAIL**.
Historical V21 overall: FAIL (immutable).

| Claim | Verdict | Basis | Evidence JSON pointers | Rationale/errors |
|---|---|---|---|---|
| C01: ORD10002 delivered | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV22_R0_0.json#/results/0/evidence/tool_calls/0/output/status` (SHA256 `6884098aacb4dcfdd2cfb9cda72fdab0f51842751ea767348abf5204f54f2f4f`) |   |
| C02: Refund-record goal missing from public final answer | FAIL | INFERRED_GOAL_COMPARISON | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV22_R0_0.json#/traces/0/turns/0/response/answer` (SHA256 `6884098aacb4dcfdd2cfb9cda72fdab0f51842751ea767348abf5204f54f2f4f`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV22_R0_0.json#/results/0/evidence/tool_calls` (SHA256 `6884098aacb4dcfdd2cfb9cda72fdab0f51842751ea767348abf5204f54f2f4f`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/datasets/validation_holdout_v21_answers.json#/PSV22/0` (SHA256 `0a1c5a728b55f839e1db2b297b150a5057fd8a531835f0268905a56639d993ab`) | Assess actual one-sentence public answer, not earlier generated draft. No refund-status tool ran. MISSING_REQUIRED_FACT; GOAL_OMISSION |

## PSV22:R1:0

Query: 请分别核实 ORD10002 当前订单状态和有没有退款单。签收不代表退款，这两项都请查一下。

Public final answer (complete):

> 已按两项分别核实 ORD10002：
>
> 1）当前订单状态：工具查询结果显示为 delivered（已签收/已送达），下单与支付时间均为 2026-10-16，发货时间 2026-10-17，送达时间 2026-10-24，承运运单号 YT998877，收货城市北京。商品为「定制马克杯」1 件，单价 39.00 元，订单合计 39.00 元。
>
> 2）退款单情况：退款状态查询返回的退款列表为空，即当前没有查到该订单的退款单，也没有进行中的退款记录。
>
> 需要说明：订单状态为已签收，只代表物流已送达，并不等于已退款；本次查询也未发现退款记录。两项结论相互独立，均已分别核实。
>
> 如需进一步处理（例如就定制商品申请售后或退款），请告知具体诉求，我会按流程发起确认；在确认完成前不会视为已提交。若你看到过与上述不一致的退款凭证，请提供相关单号，我再转人工核对。

Four dimensions: `{"factual_correctness": "PASS", "completeness": "PASS", "faithfulness": "PASS", "safety": "PASS"}`. Overall **PASS**.
Historical V21 overall: NOT_ASSESSED (immutable).

| Claim | Verdict | Basis | Evidence JSON pointers | Rationale/errors |
|---|---|---|---|---|
| C01: ORD10002 delivered | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV22_R1_0.json#/results/0/evidence/tool_calls/0/output/status` (SHA256 `d613e90fd033ad95d09f4ea18cc1f0f3d5731d68da08d2fc92eb571f653fe0b2`) |   |
| C02: Created and paid date is 2026-10-16 | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV22_R1_0.json#/results/0/evidence/tool_calls/0/output/created_at` (SHA256 `d613e90fd033ad95d09f4ea18cc1f0f3d5731d68da08d2fc92eb571f653fe0b2`) |   |
| C03: Paid date 2026-10-16 | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV22_R1_0.json#/results/0/evidence/tool_calls/0/output/paid_at` (SHA256 `d613e90fd033ad95d09f4ea18cc1f0f3d5731d68da08d2fc92eb571f653fe0b2`) |   |
| C04: Shipped 2026-10-17 | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV22_R1_0.json#/results/0/evidence/tool_calls/0/output/shipped_at` (SHA256 `d613e90fd033ad95d09f4ea18cc1f0f3d5731d68da08d2fc92eb571f653fe0b2`) |   |
| C05: Delivered 2026-10-24 | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV22_R1_0.json#/results/0/evidence/tool_calls/0/output/delivered_at` (SHA256 `d613e90fd033ad95d09f4ea18cc1f0f3d5731d68da08d2fc92eb571f653fe0b2`) |   |
| C06: Tracking is YT998877 | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV22_R1_0.json#/results/0/evidence/tool_calls/0/output/tracking_no` (SHA256 `d613e90fd033ad95d09f4ea18cc1f0f3d5731d68da08d2fc92eb571f653fe0b2`) |   |
| C07: Receiver city Beijing | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV22_R1_0.json#/results/0/evidence/tool_calls/0/output/receiver_city` (SHA256 `d613e90fd033ad95d09f4ea18cc1f0f3d5731d68da08d2fc92eb571f653fe0b2`) |   |
| C08: Customized mug quantity 1 | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV22_R1_0.json#/results/0/evidence/tool_calls/0/output/items/0/name` (SHA256 `d613e90fd033ad95d09f4ea18cc1f0f3d5731d68da08d2fc92eb571f653fe0b2`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV22_R1_0.json#/results/0/evidence/tool_calls/0/output/items/0/quantity` (SHA256 `d613e90fd033ad95d09f4ea18cc1f0f3d5731d68da08d2fc92eb571f653fe0b2`) |   |
| C09: Unit price CNY39 | PASS | INFERRED_UNIT_CONVERSION | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV22_R1_0.json#/results/0/evidence/tool_calls/0/output/items/0/unit_price_cents` (SHA256 `d613e90fd033ad95d09f4ea18cc1f0f3d5731d68da08d2fc92eb571f653fe0b2`) |   |
| C10: Order total CNY39 | PASS | INFERRED_UNIT_CONVERSION | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV22_R1_0.json#/results/0/evidence/tool_calls/0/output/total_cents` (SHA256 `d613e90fd033ad95d09f4ea18cc1f0f3d5731d68da08d2fc92eb571f653fe0b2`) |   |
| C11: Refund list empty: no recorded or ongoing refunds found for this order | PASS | KNOWN_CAPTURED_VALUE | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV22_R1_0.json#/results/0/evidence/tool_calls/1/output/refunds` (SHA256 `d613e90fd033ad95d09f4ea18cc1f0f3d5731d68da08d2fc92eb571f653fe0b2`); `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV22_R1_0.json#/traces/0/turns/0/database_after/business/refunds` (SHA256 `d613e90fd033ad95d09f4ea18cc1f0f3d5731d68da08d2fc92eb571f653fe0b2`) | Bounded to this query and saved synthetic DB; does not claim impossible future refunds.  |
| C12: Delivery does not imply refund; two independent queries executed | PASS | INFERRED_FROM_DISTINCT_TOOL_RESULTS | `research/docs/agent_engineering_upgrade/p2_answer_reliability/runs/20261108_S6_pairs_03/captures/PSV22_R1_0.json#/results/0/evidence/tool_calls` (SHA256 `d613e90fd033ad95d09f4ea18cc1f0f3d5731d68da08d2fc92eb571f653fe0b2`) |   |

Preserved extras:
- NON_ASSERTIVE / NOT_ASSESSED: Conditional offer to start aftersale confirmation and human review: No follow-up mutation executed; answer explicitly avoids saying a submission already succeeded.

## Supplementary P2-R (excluded)

Saved B31/dv06 groups were considered separately. They preserve strict/tool evidence but lack the real-run final-public-response/node capture needed for this semantic protocol. All four groups remain semantic NOT_ASSESSED; offline diagnostic traces and provider messages are not substituted. See JSON appendix for exact hashes/pointers.

## Limits

- One independent model-assisted review of a selected seven-pair pilot, not human gold or inter-rater agreement.
- Same provider family may share biases; parent review still required.
- No new API, replay, scorer/app/Gold changes, or historical regrading in place.
- Unknown extras preserved; whole-answer correctness remains unassessed where substantive extrapolation lacks evidence.
- Fourteen saved public responses are not fourteen independent random task samples; no significance/generalization claim.
