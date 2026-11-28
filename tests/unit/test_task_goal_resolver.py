import pytest

from app.agents.goals import resolve_goals
from app.memory.context import SelectedContext
from app.schemas.goals import GoalKind, GoalSignal


@pytest.mark.parametrize(
    ("query", "kinds"),
    [
        ("查一下 ORD10001 的订单状态和实付金额", {"order_status", "order_amount"}),
        ("ORD10001 的物流状态和运单号给我", {"shipment", "tracking_number"}),
        ("ORD10002 的退款到哪了，之前已经申请了", {"refund_status"}),
        (
            "SKU-HEADSET 有货吗，顺便看一下规格和价格",
            {"inventory", "product_detail", "product_price"},
        ),
        ("查询 ORD10001 的订单商品明细，再查 SKU-TEE 库存", {"order_items", "inventory"}),
        ("退款一般多久到账？", {"policy"}),
    ],
)
def test_goal_fields_and_composite_scope(query, kinds):
    goals = resolve_goals(query)
    assert {goal.kind.value for goal in goals if not goal.negated} == kinds
    assert all(goal.fields for goal in goals if goal.kind != GoalKind.UNKNOWN)


def test_only_current_request_defines_goals_and_context_can_supply_order_id():
    context = SelectedContext(
        "多少钱来着？（会话指代：订单 ORD10001，状态须实时查询）",
        order_id="ORD10001",
        source="session_summary_user_entity",
        summary="物流已签收",
    )
    (amount,) = resolve_goals("多少钱来着？", context)
    assert (amount.kind, amount.entity_id, amount.entity_source) == (
        GoalKind.ORDER_AMOUNT,
        "ORD10001",
        "session_summary_user_entity",
    )
    assert amount.fields == ("total_cents",)


def test_negated_and_conditional_operations_remain_explicit_and_unresolved():
    goals = resolve_goals("不要取消 ORD10001，只查这单的物流")
    assert any(g.kind == GoalKind.CANCEL and g.negated and g.operation == "write" for g in goals)
    assert any(g.kind == GoalKind.SHIPMENT and not g.negated for g in goals)
    conditional = resolve_goals("如果还没发货就取消 ORD10001")
    assert any(g.kind == GoalKind.CANCEL and g.conditions for g in conditional)
    goals = resolve_goals("查一下这款的库存")
    assert goals[0].clarification == ("sku",)


def test_model_suggestion_requires_current_grounding_and_can_add_a_goal_without_a_keyword():
    query = "ORD10001 仓库已经交件了没有？"
    goals = resolve_goals(
        query,
        suggestions=[
            GoalSignal(kind="order_status", quote="已经交件了没有"),
            GoalSignal(kind="inventory", quote="历史的库存"),
        ],
    )
    assert [g.kind for g in goals if g.kind != GoalKind.UNKNOWN] == [GoalKind.ORDER_STATUS]


async def test_existing_intent_call_populates_goals_and_keeps_a_compound_read_on_agent():
    from app.agents.nodes.intent import IntentClassifier
    from app.agents.nodes.router import intent_node, router_node
    from app.providers.fake import OfflineLLMProvider
    from app.retrieval.adaptive import AdaptiveRouter

    llm = OfflineLLMProvider()
    state = {"user_query": "SKU-HEADSET 还有货吗？顺便看价格"}
    result = await intent_node(state, IntentClassifier(llm))
    assert {goal.kind for goal in result["task_goals"]} == {
        GoalKind.INVENTORY,
        GoalKind.PRODUCT_PRICE,
    }
    route = await router_node({**state, **result}, AdaptiveRouter(llm))
    assert route["strategy"].value == "agent"


def test_compound_sku_price_cannot_acquire_the_other_clauses_order_target():
    goals = resolve_goals("查 ORD10001 的订单状态，SKU-HEADSET 多少钱？")
    assert [(goal.kind, goal.entity_id) for goal in goals] == [
        (GoalKind.ORDER_STATUS, "ORD10001"),
        (GoalKind.PRODUCT_PRICE, "SKU-HEADSET"),
    ]


def test_only_clause_keeps_a_read_restriction_and_negated_companion():
    goals = resolve_goals("只查 ORD10001 的订单状态，不查物流")
    assert goals[0].constraints == ("只查 ORD10001 的订单状态",)
    assert goals[1].negated and goals[1].kind == GoalKind.SHIPMENT


def test_politeness_and_conditional_reporting_do_not_hide_an_independent_read():
    (refund,) = resolve_goals("谢谢，查 ORD10002 有没有退款记录，如果没记录也直接告诉我。")
    assert refund.kind == GoalKind.REFUND_STATUS and not refund.conditions
    assert refund.constraints == ("如果没记录也直接告诉我",)


def test_refunded_amount_does_not_request_the_order_charge():
    assert [g.kind for g in resolve_goals("ORD10002 退了多少钱？")] == [GoalKind.REFUND_STATUS]


def test_order_can_request_details_without_repeating_the_word_product():
    assert {g.kind for g in resolve_goals("查一下 ORD10001 的状态、明细和物流。")} == {
        GoalKind.ORDER_STATUS,
        GoalKind.ORDER_ITEMS,
        GoalKind.SHIPMENT,
    }


def test_condition_belongs_to_the_dependent_goal_only():
    goals = resolve_goals("查 ORD10001 的订单商品明细。如果没有发货，帮我取消 ORD10001。")
    lookup = next(g for g in goals if g.kind == GoalKind.ORDER_ITEMS)
    cancel = next(g for g in goals if g.kind == GoalKind.CANCEL)
    assert not lookup.conditions
    assert cancel.conditions == ("如果没有发货",)


def test_negation_governs_the_coordinated_reads_until_the_next_clause():
    goals = resolve_goals("别查 ORD10001 的物流和退款进度，只看订单状态。")
    assert {g.kind for g in goals if g.negated} == {GoalKind.SHIPMENT, GoalKind.REFUND_STATUS}
    assert [g.kind for g in goals if not g.negated] == [GoalKind.ORDER_STATUS]


async def test_invalid_optional_goal_hint_does_not_replace_a_valid_model_intent():
    from app.agents.nodes.intent import IntentClassifier
    from app.providers.base import LLMResponse

    class Provider:
        calls = 0

        async def generate(self, *args, **kwargs):
            self.calls += 1
            return LLMResponse(
                '{"label":"product_consult","confidence":0.9,"prompt_version":"test",'
                '"goal_signals":[{"kind":"bogus","quote":"商品"}]}'
            )

    provider = Provider()
    result = await IntentClassifier(provider).classify("请帮我核对这项业务")
    assert result.label == "product_consult" and not result.goal_signals
    assert provider.calls == 1
