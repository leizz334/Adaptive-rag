from research.docs.agent_engineering_upgrade.p4_real_llm_e2e.score import score


def row(answer="金额208.60元，订单已发货。", tools=None):
    state = {
        "orders": [{"order_id": "ORD71021", "status": "shipped"}],
        "audit_logs": [],
        "idempotency_keys": [],
    }
    return dict(
        status=200,
        body=dict(answer=answer, citations=[]),
        tools=tools or [],
        before=state,
        after=state,
        events=[],
    )


def test_fact_strings_alone_cannot_pass_without_fresh_tool():
    case = dict(facts=["208.60", "已发货"], tools=["get_order"])
    assert not score(case, row())["task_success_proxy"]
    assert score(case, row(tools=[dict(name="get_order", success=True)]))["task_success_proxy"]


def test_wrong_amount_or_write_blocks_readonly_success():
    case = dict(facts=["208.60"], tools=[])
    assert not score(case, row(answer="208.61"))["task_success_proxy"]
    r = row()
    r["after"] = {"orders": [{"order_id": "ORD71021", "status": "cancelled"}]}
    assert not score(case, r)["task_success_proxy"]


def test_ambiguity_requires_question_and_no_business_call():
    case = dict(facts=[], tools=[], clarify=True)
    assert score(case, row(answer="请提供订单号，我才能核对金额。"))["task_success_proxy"]
    assert not score(case, row(answer="已为您退款。"))["task_success_proxy"]


def test_wrong_entity_tool_cannot_pass_gold():
    case = dict(order="ORD71021", facts=["208.60"], tools=["get_order"])
    wrong = row(tools=[dict(name="get_order", success=True, arguments=dict(order_id="ORD99999"))])
    assert not score(case, wrong)["task_success_proxy"]


def test_presence_proxy_is_not_semantic_certification():
    case = dict(facts=["208.60", "已发货"], tools=["get_order"])
    negated = row(
        answer="金额不是208.60元，也不是已发货", tools=[dict(name="get_order", success=True)]
    )
    result = score(case, negated)
    assert result["required_claims_present"] == 2
    assert result["task_success"] == "NOT_ASSESSED"
    assert result["full_answer_factual_correctness"] == "NOT_ASSESSED"
