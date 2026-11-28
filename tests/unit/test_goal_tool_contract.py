from app.agents.goals import resolve_goals
from app.schemas.agent import ToolResult
from app.tools.aftersale_tools import GetRefundStatusTool
from app.tools.goal_contract import observed_goal, required_read_calls
from app.tools.logistics_tools import TrackShipmentTool
from app.tools.order_tools import GetOrderItemsTool, GetOrderTool
from app.tools.product_tools import CheckInventoryTool, GetProductDetailTool
from app.tools.registry import ToolRegistry


def registry_for(*tools):
    registry = ToolRegistry()
    for tool in tools:
        registry.register(tool)
    return registry


def test_bound_plan_deduplicates_by_entity_and_registered_capability():
    registry = registry_for(GetOrderTool(), TrackShipmentTool(), GetRefundStatusTool())
    goals = resolve_goals("查 ORD10001 的订单状态和实付金额，同时看物流轨迹和运单号")
    calls = required_read_calls(goals, registry)
    assert calls is not None
    assert [(call.name, call.arguments) for call in calls] == [
        ("get_order", {"order_id": "ORD10001"}),
        ("track_shipment", {"order_id": "ORD10001"}),
    ]


def test_inventory_prefers_the_light_lookup_and_detail_covers_both_fields():
    registry = registry_for(CheckInventoryTool(), GetProductDetailTool())
    inventory = required_read_calls(resolve_goals("SKU-HEADSET 有货吗"), registry)
    combined = required_read_calls(resolve_goals("SKU-HEADSET 有货吗，顺便看参数"), registry)
    assert inventory and [c.name for c in inventory] == ["check_inventory"]
    assert combined and [c.name for c in combined] == ["get_product_detail"]


def test_missing_capability_parameters_or_conditional_write_do_not_materialize_reads():
    registry = registry_for(GetOrderTool())
    assert required_read_calls(resolve_goals("ORD10001 退款处理到哪了"), registry) is None
    assert required_read_calls(resolve_goals("查询订单状态"), registry) is None
    assert required_read_calls(resolve_goals("如果没发货就取消 ORD10001"), registry) is None
    assert required_read_calls(resolve_goals("查 ORD" + "1" * 40 + " 状态"), registry) is None


def test_actual_observation_requires_success_fields_and_correlation():
    (goal,) = resolve_goals("帮我查 ORD10001 的订单商品明细")
    registry = registry_for(GetOrderItemsTool())
    assert required_read_calls([goal], registry)
    args = {"order_id": "ORD10001"}
    assert not observed_goal(goal, args, ToolResult(name="get_order_items", success=True))
    result = ToolResult(name="get_order_items", success=True, output={"items": []})
    assert observed_goal(goal, args, result)
    assert not observed_goal(goal, {"order_id": "ORD10002"}, result)
    assert not observed_goal(goal, args, result.model_copy(update={"truncated": True}))


def test_explicit_absence_is_an_observation_but_a_missing_field_is_not():
    (refund,) = resolve_goals("查 ORD10001 的退款进度")
    (tracking,) = resolve_goals("查 ORD10001 的运单号")
    args = {"order_id": "ORD10001"}
    assert observed_goal(
        refund, args, ToolResult(name="get_refund_status", success=True, output={"refunds": []})
    )
    assert not observed_goal(
        tracking,
        args,
        ToolResult(name="track_shipment", success=True, output={"tracking_no": None}),
    )
    assert observed_goal(
        tracking,
        args,
        ToolResult(
            name="track_shipment",
            success=True,
            output={"tracking_no": None, "order_id": "ORD10001"},
        ),
    )
