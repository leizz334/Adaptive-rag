"""Independent reviewer counterexamples; no network, gold or production edits."""

from app.agents.answer_evidence import safe_answer
from app.schemas.agent import ToolResult
from eval.answer_scoring import AnswerGold, EvidenceRequirement, FactAssertion, score_answer


def _status_gold(**kwargs):
    return AnswerGold(
        subgoals=["status"],
        facts=[
            FactAssertion(
                id="paid",
                goal="status",
                subject="ORD7000",
                patterns=["已支付"],
                evidence_any_of=[
                    EvidenceRequirement(
                        tool="get_order",
                        arguments={"order_id": "ORD7000"},
                        path="status",
                        expected="paid",
                    )
                ],
            )
        ],
        semantic_required=False,
        **kwargs,
    )


def _score(answer, gold=None, calls=None):
    return score_answer(
        answer=answer,
        gold=gold or _status_gold(),
        calls=calls
        if calls is not None
        else [
            dict(
                name="get_order",
                arguments={"order_id": "ORD7000"},
                success=True,
                output={"order_id": "ORD7000", "status": "paid"},
            )
        ],
        tool_success=True,
        environment_success=True,
    )


def test_extra_wrong_entity_claim_is_not_erased_as_known_fact():
    result = _score("ORD7000已支付。ORD7999已支付。")
    assert result["OVERALL_TASK_SUCCESS"] != "PASS", result


def test_truncated_observation_is_not_complete_evidence():
    result = _score(
        "ORD7000已支付。",
        calls=[
            dict(
                name="get_order",
                arguments={"order_id": "ORD7000"},
                success=True,
                truncated=True,
                output={"status": "paid"},
            )
        ],
    )
    assert result["ANSWER_FAITHFULNESS"] != "PASS", result


def test_missing_evidence_path_is_not_explicit_null():
    gold = AnswerGold(
        subgoals=["not_shipped"],
        semantic_required=False,
        facts=[
            FactAssertion(
                id="not_shipped",
                goal="not_shipped",
                subject="ORD7000",
                patterns=["尚未发货"],
                evidence_any_of=[
                    EvidenceRequirement(
                        tool="get_order",
                        path="shipped_at",
                        expected=None,
                    )
                ],
            )
        ],
    )
    result = _score(
        "ORD7000尚未发货。",
        gold=gold,
        calls=[
            dict(
                name="get_order",
                success=True,
                output={},
            )
        ],
    )
    assert result["OVERALL_TASK_SUCCESS"] != "PASS", result


def test_cancel_does_not_discard_verified_order_amount():
    result = safe_answer(
        [
            ToolResult(
                name="get_order",
                success=True,
                output={
                    "order_id": "ORD7000",
                    "status": "paid",
                    "total_cents": 1250,
                },
            ),
            ToolResult(
                name="cancel_order",
                success=True,
                output={
                    "order_id": "ORD7000",
                    "status": "cancelled",
                },
            ),
        ]
    )
    assert "12.50" in result, result
    assert "已支付" not in result


def test_abstention_with_unassessed_extra_claim_is_not_certified():
    gold = AnswerGold(
        subgoals=["clarify"],
        expected_abstention=True,
        semantic_required=False,
        facts=[FactAssertion(id="clarify", goal="clarify", patterns=["请明确订单号"])],
    )
    result = _score("请明确订单号。退款成功。", gold=gold, calls=[])
    assert result["ABSTENTION_CORRECTNESS"] != "PASS", result


def test_return_request_preserves_order_status():
    result = safe_answer([
        ToolResult(name="get_order", success=True, output={
            "order_id": "ORD7000", "status": "delivered", "total_cents": 1250,
        }),
        ToolResult(name="create_return_request", success=True, output={
            "order_id": "ORD7000", "status": "requested", "return_id": "rt_demo",
        }),
    ])
    assert "已签收" in result, result


def test_refund_request_preserves_actual_shipment_events():
    result = safe_answer([
        ToolResult(name="track_shipment", success=True, output={
            "order_id": "ORD7000", "events": [{"status": "delivered"}],
        }),
        ToolResult(name="create_refund_request", success=True, output={
            "order_id": "ORD7000", "status": "requested", "refund_id": "rf_demo",
        }),
    ])
    assert "已签收" in result, result
