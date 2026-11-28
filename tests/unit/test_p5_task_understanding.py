import pytest

from app.agents.goals import resolve_goals
from app.agents.nodes.router import _verified_order_scope
from app.config.settings import Settings
from app.memory.context import ContextBuilder
from app.schemas.chat import ChatMessage
from app.schemas.goals import GoalKind, GoalSignal, SkillHint
from app.skills.registry import get_skill_registry
from app.skills.selector import select_skill


def choose(query, intent="order_inquiry", signals=(), hints=()):
    goals = resolve_goals(query, suggestions=signals)
    return goals, select_skill(
        get_skill_registry(), query, intent, goals, hints, mode="conditional"
    )


def test_status_only_request_is_not_a_condition():
    query = "劳烦看一眼 ORD10003 的订单现在是什么状态，只要状态就行。"
    signals = [GoalSignal(category="dependency", quote="只要状态就行")]
    goals = resolve_goals(query, suggestions=signals)
    assert [(g.kind, g.entity_id, g.conditions) for g in goals] == [
        (GoalKind.ORDER_STATUS, "ORD10003", ()),
    ]


def test_fixed_live_cancellation_hint_is_bound_as_an_action():
    query = "刚才付款时点了两次，后下的 ORD10003 请撤掉，另一笔要留着。"
    signals = [GoalSignal(kind="order_status", quote="后下的 ORD10003 请撤掉")]
    hints = [SkillHint(name="order-cancellation", quote="后下的 ORD10003 请撤掉")]
    goals, skill = choose(query, signals=signals, hints=hints)
    assert any(g.kind == GoalKind.CANCEL and g.entity_id == "ORD10003" for g in goals)
    assert skill.name == "order-cancellation" and skill.use_workflow


def test_conditional_order_is_distinct_from_verified_independent_read():
    text = (
        "麻烦查一下 ORD10002 有没有退款单。另外 ORD10003 得先确认已付款，付了才查那单的商品明细。"
    )
    # This repeats the misleading terminal dependency from the real P4 response.
    signals = [GoalSignal(category="dependency", quote="付了才查那单的商品明细")]
    goals, skill = choose(text, signals=signals)
    assert any(g.kind == GoalKind.REFUND_STATUS and not g.conditions for g in goals)
    assert skill.use_workflow and skill.order_id == "ORD10003"
    proof = skill.conditional_goal.verified_dependency
    assert proof.prerequisite_order_id == "ORD10003"
    assert any(
        g.kind == GoalKind.REFUND_STATUS and g.entity_id == "ORD10002"
        for g in skill.independent_goals
    )


@pytest.mark.parametrize(
    "clause", ["没付才查这笔商品明细", "付了才查另一笔订单的商品明细", "付了也别查订单商品明细"]
)
def test_payment_signal_does_not_replace_scope_or_negation(clause):
    text = f"先核对 ORD10003 是否已经付款，{clause}。"
    _, skill = choose(text, signals=[GoalSignal(category="dependency", quote=clause)])
    assert not skill.use_workflow


def test_consultation_maps_to_policy_goal_but_cannot_activate_approval():
    query = "ORD10003 我还没决定是否留着，想看看取消订单有什么规定。"
    goals, skill = choose(query, intent="cancel_order")
    assert any(g.kind == GoalKind.POLICY for g in goals)
    assert not any(g.operation == "write" and not g.negated for g in goals)
    assert not skill.use_workflow


def test_scoped_approval_is_missing_eligible_when_reason_and_item_scope_are_unresolved():
    query = "帮我给 ORD10001 的耳机开个退货申请，退货原因我还没说。"
    goals, skill = choose(query, intent="return_exchange")
    assert any(g.kind == GoalKind.RETURN_REQUEST for g in goals)
    assert "return-request" in skill.relevant
    assert "return-request" not in skill.eligible
    assert skill.clarification == "return_scope"


def test_unannotated_preface_does_not_block_two_explicit_independent_order_reads():
    query = "两张单要对账。ORD10001 我只要订单总额；ORD10002 麻烦列一下买了什么和数量。"
    signals = [
        GoalSignal(kind="order_amount", quote="ORD10001 我只要订单总额"),
        GoalSignal(kind="order_items", quote="ORD10002 麻烦列一下买了什么和数量"),
    ]
    goals = resolve_goals(query, suggestions=signals)
    assert _verified_order_scope(query, goals)
    assert {(g.kind, g.entity_id) for g in goals if g.entity_id} == {
        (GoalKind.ORDER_AMOUNT, "ORD10001"),
        (GoalKind.ORDER_ITEMS, "ORD10002"),
    }


def test_explicit_unresolved_prefix_does_not_disappear_as_background():
    prefix = "能替我补开发票吗"
    query = f"{prefix}？请查 ORD10001 总额。请查 ORD10002 商品明细。"
    signals = [GoalSignal(category="unresolved", quote=prefix)]
    goals = resolve_goals(query, suggestions=signals)
    assert any(g.kind == GoalKind.UNKNOWN and not g.independent for g in goals)
    assert not _verified_order_scope(query, goals)


def test_catalog_pronoun_does_not_bind_an_order_from_history_or_request_clarification():
    context_builder = ContextBuilder(Settings(memory_mode="M2"))
    query = "我想找定制马克杯。它标多少钱？现在还有多少件？"
    history = [ChatMessage(role="user", content="查 ORD10001 的订单状态。")]
    for messages in ([], history):
        context = context_builder.build(query, messages)
        assert context.effective_query == query
        assert context.order_id is None and not context.needs_clarification
    order_context = context_builder.build("它什么时候能到？", history)
    assert order_context.order_id == "ORD10001"


def test_catalog_action_spans_are_not_order_amounts_or_item_quantities():
    query = "我想找定制马克杯。它标多少钱？现在还有多少件？"
    signals = [
        GoalSignal(kind="product_detail", quote="我想找定制马克杯"),
        GoalSignal(kind="product_price", quote="它标多少钱"),
        GoalSignal(kind="inventory", quote="现在还有多少件"),
    ]
    hints = [SkillHint(name="catalog-title-lookup", quote="我想找定制马克杯")]
    goals, skill = choose(query, intent="product_consult", signals=signals, hints=hints)
    assert {goal.kind for goal in goals} == {
        GoalKind.PRODUCT_DETAIL,
        GoalKind.PRODUCT_PRICE,
        GoalKind.INVENTORY,
    }
    assert skill.name == "catalog-title-lookup" and skill.open_catalog


def test_payment_clause_and_foreign_dependent_target_cannot_be_flattened():
    query = "先核对 ORD10003 有没有付款记录，付了再给我看 ORD10002 的商品明细。"
    goals, skill = choose(query)
    assert not skill.use_workflow
    assert any(
        goal.kind == GoalKind.ORDER_ITEMS
        and goal.entity_id == "ORD10002"
        and goal.conditions
        and goal.verified_dependency is None
        for goal in goals
    )
