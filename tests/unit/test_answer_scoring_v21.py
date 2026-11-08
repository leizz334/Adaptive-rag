import pytest

from eval.answer_scoring import AnswerGold, EvidenceRequirement, FactAssertion, score_answer


def quantity_gold():
    return AnswerGold(
        subgoals=["件数"],
        facts=[
            FactAssertion(
                id="q",
                goal="件数",
                subject="SKU-NEW",
                patterns=[r"1\s*件"],
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


def quantity_score(answer):
    return score_answer(
        answer=answer,
        gold=quantity_gold(),
        calls=[
            dict(
                name="get_order_items",
                success=True,
                arguments=dict(order_id="ORD7070"),
                output=dict(items=[dict(sku="SKU-NEW", quantity=1)]),
            )
        ],
        tool_success=True,
        environment_success=True,
    )


def test_unique_quantity_before_its_sku_is_verified_coverage():
    value = quantity_score("订单ORD7070商品数量为1件，商品为杯子（SKU-NEW）。")
    assert value["ANSWER_COMPLETENESS"] == 1
    assert value["missing_subgoals"] == []


def test_single_logical_subject_need_not_be_printed_when_unique():
    value = quantity_score("数量1件。")
    assert value["OVERALL_TASK_SUCCESS"] == "PASS"


def test_ambiguous_multiple_skus_do_not_assign_total_to_each():
    value = quantity_score("一共1件，涉及SKU-NEW与SKU-SECOND。")
    assert value["OVERALL_TASK_SUCCESS"] != "PASS"


def test_wrong_explicit_sku_is_never_implicit_correct_subject():
    assert quantity_score("SKU-OTHER数量1件。")["OVERALL_TASK_SUCCESS"] == "FAIL"


@pytest.mark.parametrize("amount", ["12.5元", "￥12.50", "人民币12.5元", "12.50 CNY"])
def test_equivalent_cny_formats_use_same_exact_amount(amount):
    gold = AnswerGold(
        subgoals=["总额"],
        facts=[
            FactAssertion(
                id="m",
                goal="总额",
                subject="ORD7070",
                patterns=[r"总金额\s*12\.50\s*元"],
                evidence_any_of=[
                    EvidenceRequirement(
                        tool="get_order",
                        arguments=dict(order_id="ORD7070"),
                        path="total_cents",
                        expected=1250,
                    )
                ],
            )
        ],
        semantic_required=False,
    )
    value = score_answer(
        answer="ORD7070总金额" + amount + "。",
        gold=gold,
        calls=[
            dict(
                name="get_order",
                arguments=dict(order_id="ORD7070"),
                success=True,
                output=dict(total_cents=1250),
            )
        ],
        tool_success=True,
        environment_success=True,
    )
    assert value["OVERALL_TASK_SUCCESS"] == "PASS"


def test_unknown_paraphrase_is_not_certified_as_definite_omission():
    value = quantity_score("商品总共一个，就是前面那只杯子。")
    assert value["OVERALL_TASK_SUCCESS"] == "NOT_ASSESSED"
    assert value["ANSWER_COMPLETENESS"] is None
    assert value["unresolved_subgoals"] == ["件数"]
