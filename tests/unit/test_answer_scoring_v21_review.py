"""Independent review counterexamples; no private data or tool execution."""

import pytest

from eval.answer_scoring import AnswerGold, EvidenceRequirement, FactAssertion, score_answer


def _money_gold():
    return AnswerGold(
        subgoals=["amount"],
        facts=[
            FactAssertion(
                id="amount",
                goal="amount",
                subject="ORD7000",
                patterns=[r"12\.50\s*\u5143"],
                evidence_any_of=[
                    EvidenceRequirement(
                        tool="get_order",
                        arguments={"order_id": "ORD7000"},
                        path="total_cents",
                        expected=1250,
                    )
                ],
            )
        ],
        semantic_required=False,
    )


@pytest.mark.parametrize("amount", ["-12.50\u5143", "-12.5\u5143", "-\uffe512.50"])
def test_review_negative_cny_amount_is_not_positive_gold(amount):
    result = score_answer(
        answer="ORD7000 " + amount + "\u3002",
        gold=_money_gold(),
        calls=[
            dict(
                name="get_order",
                success=True,
                arguments={"order_id": "ORD7000"},
                output={"total_cents": 1250},
            )
        ],
        tool_success=True,
        environment_success=True,
    )
    assert result["OVERALL_TASK_SUCCESS"] != "PASS", result


def test_review_quantity_evidence_for_foreign_sku_does_not_support_subject():
    gold = AnswerGold(
        subgoals=["quantity"],
        facts=[
            FactAssertion(
                id="quantity",
                goal="quantity",
                subject="SKU-NEW",
                patterns=[r"1\s*\u4ef6"],
                evidence_any_of=[
                    EvidenceRequirement(
                        tool="get_order_items",
                        arguments={"order_id": "ORD7070"},
                        path="items.0.quantity",
                        expected=1,
                    )
                ],
            )
        ],
        semantic_required=False,
    )
    result = score_answer(
        answer="SKU-NEW\u6570\u91cf1\u4ef6\u3002",
        gold=gold,
        calls=[
            dict(
                name="get_order_items",
                success=True,
                arguments={"order_id": "ORD7070"},
                output={"items": [{"sku": "SKU-OTHER", "quantity": 1}]},
            )
        ],
        tool_success=True,
        environment_success=True,
    )
    assert result["OVERALL_TASK_SUCCESS"] != "PASS", result
