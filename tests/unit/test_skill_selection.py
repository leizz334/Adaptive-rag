import pytest

from app.agents.goals import resolve_goals
from app.schemas.goals import GoalKind, GoalSignal, SkillHint
from app.skills.registry import get_skill_registry
from app.skills.selector import select_skill, skill_discovery_prompt


def choose(query, intent="order_inquiry", hints=(), mode="conditional"):
    return select_skill(get_skill_registry(), query, intent, resolve_goals(query), hints, mode=mode)


def test_intent_receives_catalog_without_instructions():
    registry = get_skill_registry()
    catalog = skill_discovery_prompt(registry.metadata())
    assert "catalog-title-lookup" in catalog and "conditional-order-query" in catalog
    assert "references/catalog-evidence.md" not in catalog
    assert registry.load_instructions("product-recommend") not in catalog


def test_only_grounded_action_selects_approval_skill():
    assert choose("取消订单 ORD10003", "cancel_order").name == "order-cancellation"
    policy = "取消订单 ORD10003 的规则是什么？"
    hinted = [SkillHint(name="order-cancellation", quote=policy)]
    assert choose(policy, "cancel_order", hinted).name is None
    assert choose("订单 ORD10003 的取消状态", "order_inquiry").name != "order-cancellation"


@pytest.mark.parametrize(
    "query",
    [
        "请问还能不能取消订单 ORD10003？",
        "取消订单 ORD10003 可以吗？",
        "请检查是否已经取消订单 ORD10003。",
        "别帮我取消订单 ORD10003。",
        "我不是要取消订单 ORD10003。",
        "我只想看看现在取消订单 ORD10003 有什么规定，别替我操作。",
        "申请退货 ORD10001 可以吗？原因是尺码不合适。",
    ],
)
def test_status_eligibility_and_denial_never_select_approval(query):
    assert choose(query, "cancel_order").name is None


def test_return_proposal_needs_a_reason_and_order_scope():
    query = "给订单 ORD10002 提交退货申请，原因是尺码不合适"
    result = choose(query, "return_exchange")
    assert result.name == "return-request"
    assert result.order_id == "ORD10002" and result.reason == "尺码不合适"
    assert (
        choose("给订单 ORD10002 提交退货申请", "return_exchange").clarification == "return_reason"
    )
    assert (
        choose(
            "给订单 ORD10002 只退 SKU-TEE，提交退货申请，原因是太大", "return_exchange"
        ).clarification
        == "return_scope"
    )
    assert (
        choose(
            "帮我给 ORD10001 的键盘申请退货，原因是尺码不合适。", "return_exchange"
        ).clarification
        == "return_scope"
    )


def test_condition_requires_same_order_and_positive_payment_evidence():
    query = "如果订单 ORD10001 已经付款，就帮我查询商品明细。另请查 ORD10002 的实付金额。"
    result = choose(query)
    assert result.name == "conditional-order-query" and result.order_id == "ORD10001"
    assert result.conditional_goal is not None
    assert result.conditional_goal.kind == GoalKind.ORDER_ITEMS
    assert {(goal.kind, goal.entity_id) for goal in result.independent_goals} == {
        (GoalKind.ORDER_AMOUNT, "ORD10002")
    }
    no_pay = "如果订单 ORD10001 没有付款，就帮我查询商品明细。"
    other_order = "如果订单 ORD10001 已付款，就查 ORD10002 的商品明细。"
    assert choose(no_pay).name != "conditional-order-query"
    assert choose(other_order).name != "conditional-order-query"
    assert choose(query, mode="workflows").name != "conditional-order-query"


def test_grounded_terminal_action_can_also_be_labeled_dependency():
    query = "如果订单 ORD10003 已经付款，就帮我查询商品明细。"
    hints = [
        GoalSignal(category="action", kind="order_payment", quote="如果订单 ORD10003 已经付款"),
        GoalSignal(category="dependency", kind="order_items", quote="就帮我查询商品明细"),
    ]
    goals = resolve_goals(query, suggestions=hints)
    candidate = select_skill(
        get_skill_registry(), query, "order_inquiry", goals, mode="conditional"
    )
    assert candidate.use_workflow
    assert candidate.conditional_goal.conditions == ("如果订单 ORD10003 已经付款",)


@pytest.mark.parametrize(
    "action",
    [
        "就帮我查询另一笔订单的商品明细",
        "就帮我查询之前那笔订单的商品明细",
        "就别帮我查询商品明细",
        "就帮我查订单 ORD10001-WRONG 的商品明细",
    ],
)
def test_condition_does_not_authorize_negative_or_conflicting_references(action):
    assert choose(f"如果订单 ORD10001 已经付款，{action}。").name is None


def test_partial_identifier_or_generic_reason_cannot_approve():
    assert choose("取消订单 ORD10003-WRONG", "cancel_order").name is None
    text = "帮我申请退货 ORD10001，请尽快处理。"
    hint = SkillHint(
        name="return-request", quote="帮我申请退货 ORD10001", reason_quote="请尽快处理"
    )
    assert choose(text, "return_exchange", [hint]).clarification == "return_reason"


def test_extension_is_selected_via_metadata_and_current_quote():
    query = "找一下商品里叫便携蓝牙耳机的那款。"
    hint = SkillHint(name="catalog-title-lookup", quote="叫便携蓝牙耳机的那款")
    assert choose(query, "product_consult", [hint]).name == "catalog-title-lookup"
    assert choose("今天的天气如何？", "chitchat", [hint]).name is None


def test_equal_compatible_hints_fall_back_without_activation():
    query = "找一下推荐的便携蓝牙耳机。"
    hints = [
        SkillHint(name="catalog-title-lookup", quote="便携蓝牙耳机"),
        SkillHint(name="product-recommend", quote="推荐的便携蓝牙耳机"),
    ]
    assert choose(query, "product_consult", hints).name is None
