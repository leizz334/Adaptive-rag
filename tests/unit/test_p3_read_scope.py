import pytest

from app.agents.goal_answers import render_goal_answer
from app.agents.goals import resolve_goals
from app.schemas.agent import AgentPlan
from app.schemas.goals import GoalKind, GoalSignal
from app.tools.goal_contract import evaluate_read_contract
from app.tools.logistics_tools import TrackShipmentTool
from app.tools.order_tools import GetOrderTool
from app.tools.product_tools import CheckInventoryTool, GetProductDetailTool
from app.tools.registry import ToolRegistry


def _contract(goals):
    registry = ToolRegistry()
    for tool in (GetOrderTool(), TrackShipmentTool(), CheckInventoryTool(), GetProductDetailTool()):
        registry.register(tool)
    return evaluate_read_contract(goals, registry)


@pytest.mark.parametrize(
    ("background", "lookup", "entity", "kind"),
    [
        ("ORD20001 是这次对账的单子", "核对它的实付金额", "ORD20001", GoalKind.ORDER_AMOUNT),
        ("本次备货用 SKU-CABLE", "查一下库存", "SKU-CABLE", GoalKind.INVENTORY),
    ],
)
def test_validated_background_keeps_current_entity_without_adding_a_goal(
    background, lookup, entity, kind
):
    (goal,) = resolve_goals(
        f"{background}。{lookup}。",
        suggestions=[GoalSignal(quote=background, category="background")],
    )
    assert (goal.kind, goal.entity_id, goal.entity_source) == (kind, entity, "current_user")
    assert _contract([goal]).mode == "full"


def test_example_background_is_not_an_order_declaration():
    background = "例如 ORD20001 可以作为例子"
    goals = resolve_goals(
        f"{background}。查我的订单金额。",
        suggestions=[GoalSignal(quote=background, category="background")],
    )
    assert all(goal.entity_id is None for goal in goals)
    assert _contract(goals).mode == "clarify"


def test_verified_price_survives_independent_missing_order_and_asks_only_for_order():
    missing = "另想核对上次订单付了多少，手边没有订单号"
    goals = resolve_goals(
        f"查 SKU-CABLE 的价格。{missing}。",
        suggestions=[
            GoalSignal(
                quote=missing,
                kind="order_amount",
                category="unresolved",
                operation="read",
                independent=True,
            )
        ],
    )
    contract = _contract(goals)
    assert contract.mode == "partial"
    assert [(call.name, call.arguments) for call in contract.calls] == [
        ("get_product_detail", {"sku": "SKU-CABLE"})
    ]
    assert [goal.clarification for goal in goals if goal.independent] == [("order_id",)]
    answer = render_goal_answer(goals, AgentPlan(steps=[]), [])
    assert "订单号" in answer and "订单金额：暂未取得证据" not in answer


def test_only_unavailable_field_can_join_independent_verified_price():
    field = "接头外壳是什么材料"
    goals = resolve_goals(
        f"查 SKU-CABLE 的价格。{field}？",
        suggestions=[
            GoalSignal(
                quote=field, kind="product_detail", category="field", fields=("product_attribute",)
            )
        ],
    )
    contract = _contract(goals)
    assert contract.mode == "partial"
    assert [(call.name, call.arguments) for call in contract.calls] == [
        ("get_product_detail", {"sku": "SKU-CABLE"})
    ]
    assert [
        (g.fields, g.unavailable_fields) for g in goals if g.kind == GoalKind.PRODUCT_DETAIL
    ] == [((), ("product_attribute",))]


@pytest.mark.parametrize(
    ("query", "kind", "tool", "argument", "entities"),
    [
        (
            "请查 ORD20001 和 ORD20002 各自的订单状态。",
            GoalKind.ORDER_STATUS,
            "get_order",
            "order_id",
            ("ORD20001", "ORD20002"),
        ),
        (
            "分别查 SKU-CABLE、SKU-ADAPTER 的库存。",
            GoalKind.INVENTORY,
            "check_inventory",
            "sku",
            ("SKU-CABLE", "SKU-ADAPTER"),
        ),
    ],
)
def test_distributive_request_binds_every_explicit_entity(query, kind, tool, argument, entities):
    goals = resolve_goals(query)
    assert [(goal.kind, goal.entity_id, goal.entity_scope) for goal in goals] == [
        (kind, entity, "distributive") for entity in entities
    ]
    contract = _contract(goals)
    assert contract.mode == "full"
    assert [(call.name, call.arguments) for call in contract.calls] == [
        (tool, {argument: entity}) for entity in entities
    ]


def test_unsupported_typed_fields_do_not_authorize_a_read():
    (goal,) = resolve_goals("查 ORD20001 订单状态。")
    contract = _contract([goal.model_copy(update={"fields": ("receiver_city",)})])
    assert contract.mode == "clarify" and contract.calls is None


@pytest.mark.parametrize(
    ("query", "mode"),
    [
        ("查 ORD20001 状态。另外查 ORD20002 或 ORD20003 的物流。", "clarify"),
        ("查 ORD20001 或 ORD20002 各自的状态。", "clarify"),
        ("查 ORD20001 的订单状态。金额超过两百才查 ORD20002 物流。", "clarify"),
        ("查 ORD20001 状态。帮我取消 ORD20002。", "legacy"),
    ],
)
def test_scope_never_fans_out_alternatives_or_ignores_dependencies_and_writes(query, mode):
    assert _contract(resolve_goals(query)).mode == mode


def test_referenced_list_must_match_the_requested_number():
    background = "表格涉及 ORD20001 和 ORD20002 和 ORD20003"
    goals = resolve_goals(
        f"{background}。请查这两笔各自的订单状态。",
        suggestions=[GoalSignal(quote=background, category="background")],
    )
    assert all(goal.entity_id is None for goal in goals)
    assert _contract(goals).mode == "clarify"


def test_unstructured_result_dependency_cannot_become_an_independent_read():
    assert _contract(resolve_goals("ORD20001 扣款成功再查物流轨迹。")).mode == "clarify"
    assert _contract(resolve_goals("查 ORD20001 订单状态，再查物流轨迹。")).mode == "full"
