import copy

import pytest


def contract():
    from eval.answer_scoring import AnswerGold, EvidenceRequirement, FactAssertion

    return AnswerGold(
        subgoals=["订单状态", "金额"],
        facts=[
            FactAssertion(
                id="status",
                goal="订单状态",
                subject="ORD7000",
                patterns=[r"(?:订单状态[：:]?)?已支付", r"paid"],
                evidence_any_of=[
                    EvidenceRequirement(
                        tool="get_order",
                        arguments={"order_id": "ORD7000"},
                        path="status",
                        expected="paid",
                    )
                ],
            ),
            FactAssertion(
                id="amount",
                goal="金额",
                subject="ORD7000",
                patterns=[r"(?:总金额[：:]?)?12\.50\s*元"],
                evidence_any_of=[
                    EvidenceRequirement(
                        tool="get_order",
                        arguments={"order_id": "ORD7000"},
                        path="total_cents",
                        expected=1250,
                    )
                ],
            ),
        ],
        forbidden_patterns=[r"已取消", r"退款成功"],
        semantic_required=False,
    )


def observation():
    return [
        dict(
            name="get_order",
            arguments=dict(order_id="ORD7000"),
            success=True,
            output=dict(order_id="ORD7000", status="paid", total_cents=1250),
        )
    ]


def score(answer, **kwargs):
    from eval.answer_scoring import score_answer

    return score_answer(
        answer=answer,
        gold=contract(),
        calls=kwargs.pop("calls", observation()),
        tool_success=kwargs.pop("tool_success", True),
        environment_success=True,
        **kwargs,
    )


def test_correct_facts_alternate_phrasing_and_complete_goal():
    result = score("ORD7000 已支付。总金额12.50元。")
    assert result["ANSWER_COMPLETENESS"] == 1
    assert result["OVERALL_TASK_SUCCESS"] == "PASS"


def test_correct_tools_but_omitted_answer_goal_is_failure():
    value = score("ORD7000 已支付。")
    assert value["TOOL_SUCCESS"] == "PASS"
    assert value["ANSWER_COMPLETENESS"] == 0.5
    assert value["OVERALL_TASK_SUCCESS"] == "FAIL"


def test_fluid_correct_answer_without_required_execution_fails():
    value = score("ORD7000已支付，总金额12.50元。", calls=[], tool_success=False)
    assert value["ANSWER_FAITHFULNESS"] == "FAIL"
    assert value["OVERALL_TASK_SUCCESS"] == "FAIL"


def test_actual_evidence_disagreement_is_not_hidden_by_fluent_text():
    calls = observation()
    calls[0]["output"]["total_cents"] = 9999
    value = score("ORD7000已支付，总金额12.50元。", calls=calls)
    assert value["ANSWER_FAITHFULNESS"] == "FAIL"


def test_wrong_fact_and_false_write_claim_fail():
    value = score("ORD7000 已取消，退款成功。金额99元。")
    assert value["ANSWER_FACTUAL_CORRECTNESS"] == "FAIL"
    assert value["OVERALL_TASK_SUCCESS"] == "FAIL"


@pytest.mark.parametrize(
    "answer", ["ORD7000并非已支付。总金额12.50元。", "ORD7999已支付，总金额12.50元。"]
)
def test_negation_and_wrong_entity_do_not_satisfy_gold(answer):
    assert score(answer)["OVERALL_TASK_SUCCESS"] == "FAIL"


def test_gold_and_actual_calls_never_mutate_or_enter_agent():
    before = copy.deepcopy(observation())
    score("ORD7000已支付，总金额12.50元。", calls=before)
    assert before == observation()


def test_knowledge_requires_retrieved_evidence_and_unknown_semantics_stays_unknown():
    from eval.answer_scoring import AnswerGold, FactAssertion, score_answer

    gold = AnswerGold(
        subgoals=["政策"],
        facts=[FactAssertion(id="policy", goal="政策", patterns=["定制商品不适用七天无理由"])],
        semantic_required=True,
    )
    value = score_answer(
        answer="定制商品不适用七天无理由。",
        gold=gold,
        calls=[],
        tool_success=True,
        environment_success=True,
        judge_status="JUDGE_ERROR",
    )
    assert value["JUDGE_VALIDITY"] == "JUDGE_ERROR"
    assert value["ANSWER_FAITHFULNESS"] == "NOT_ASSESSED"
    assert value["OVERALL_TASK_SUCCESS"] == "NOT_ASSESSED"


def test_correct_clarification_is_valid_abstention_not_unknown_success():
    from eval.answer_scoring import AnswerGold, FactAssertion, score_answer

    gold = AnswerGold(
        subgoals=["澄清"],
        facts=[FactAssertion(id="clarify", goal="澄清", patterns=["请明确.*订单号"])],
        expected_abstention=True,
        semantic_required=False,
    )
    value = score_answer(
        answer="请明确需要查询的订单号。",
        gold=gold,
        calls=[],
        tool_success=True,
        environment_success=True,
    )
    assert value["ABSTENTION_CORRECTNESS"] == "PASS"
    assert value["OVERALL_TASK_SUCCESS"] == "PASS"


def test_unannotated_semantics_never_defaults_to_pass():
    from eval.answer_scoring import AnswerGold, score_answer

    value = score_answer(
        answer="听起来不错",
        gold=AnswerGold(subgoals=["开放政策解释"]),
        calls=[],
        tool_success=True,
        environment_success=True,
    )
    assert value["OVERALL_TASK_SUCCESS"] == "NOT_ASSESSED"


def test_added_unverified_sentence_does_not_become_faithful_from_other_facts():
    value = score("ORD7000已支付。总金额12.50元。明天一定送到。")
    assert value["ANSWER_FAITHFULNESS"] == "NOT_ASSESSED"
    assert value["OVERALL_TASK_SUCCESS"] == "NOT_ASSESSED"


def test_static_policy_can_pass_closed_fact_contract_with_actual_retrieval():
    from eval.answer_scoring import AnswerGold, EvidenceRequirement, FactAssertion, score_answer

    content = "定制商品不适用七天无理由。"
    gold = AnswerGold(
        subgoals=["政策"],
        facts=[
            FactAssertion(
                id="policy",
                goal="政策",
                patterns=["定制商品不适用七天无理由"],
                evidence_any_of=[
                    EvidenceRequirement(source="retrieval", path="content", expected=content)
                ],
            )
        ],
        semantic_required=False,
    )
    value = score_answer(
        answer=content,
        gold=gold,
        calls=[],
        retrieved=[dict(content=content)],
        tool_success=True,
        environment_success=True,
    )
    assert value["OVERALL_TASK_SUCCESS"] == "PASS"
