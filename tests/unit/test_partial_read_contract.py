import json

import pytest

from app.agents.goal_answers import render_goal_answer
from app.agents.goals import resolve_goals
from app.agents.nodes.executor import execute_with_fallback
from app.agents.nodes.generate import generate_node
from app.agents.nodes.planner import Planner
from app.config.settings import Settings
from app.core.exceptions import ToolExecutionError
from app.providers.base import LLMResponse
from app.schemas.agent import AgentPlan, PlanStep, ToolResult
from app.schemas.goals import GoalSignal
from app.tools.aftersale_tools import CancelOrderTool
from app.tools.base import ToolContext
from app.tools.goal_contract import evaluate_read_contract
from app.tools.logistics_tools import TrackShipmentTool
from app.tools.order_tools import GetOrderItemsTool, GetOrderTool
from app.tools.registry import ToolRegistry


def _registry():
    registry = ToolRegistry()
    for tool in (GetOrderTool(), TrackShipmentTool(), CancelOrderTool()):
        registry.register(tool)
    return registry


class _PlanProvider:
    def __init__(self):
        self.calls = []

    async def generate(self, messages, **kwargs):
        self.calls.append(messages)
        steps = [
            {
                "step_id": 1,
                "goal": "wrong",
                "tool_name": "get_order",
                "arguments": {"order_id": "ORD10002"},
            },
            {
                "step_id": 2,
                "goal": "write",
                "tool_name": "cancel_order",
                "arguments": {"order_id": "ORD10001"},
            },
        ]
        return LLMResponse(json.dumps({"steps": steps}))


async def test_independent_unknown_preserves_planner_and_verified_read_only():
    unknown = "积分余额也想核对一下"
    query = "查 ORD10001 订单状态。" + unknown
    goals = resolve_goals(
        query,
        suggestions=[
            GoalSignal(quote=unknown, category="unresolved", operation="read", independent=True)
        ],
    )
    provider = _PlanProvider()
    plan = await Planner(provider, _registry()).create_plan(
        query, "order_inquiry", "", task_goals=goals
    )
    assert len(provider.calls) == 1
    assert plan.read_contract_mode == "partial"
    assert [(s.tool_name, s.arguments) for s in plan.steps] == [
        ("get_order", {"order_id": "ORD10001"})
    ]
    result = await generate_node(
        {
            "plan": plan,
            "task_goals": goals,
            "tool_results": [
                ToolResult(
                    name="get_order",
                    success=True,
                    output={"order_id": "ORD10001", "status": "paid"},
                )
            ],
        },
        provider,
        settings=Settings(),
    )
    assert len(provider.calls) == 1
    assert "已支付" in result["final_answer"] and "请补充" in result["final_answer"]


@pytest.mark.parametrize(
    ("query", "mode"),
    [
        ("查 ORD10001 订单状态。还有一件事要核对。", "clarify"),
        ("查 ORD10001 订单状态。另查 ORD10002 或 ORD10003 的退款进度。", "clarify"),
        ("如果已经付款，查 ORD10001 的物流轨迹。", "clarify"),
        ("查 ORD10001 的订单状态。如果没发货就取消 ORD10001。", "legacy"),
    ],
)
def test_scope_does_not_skip_unknown_dependency_ambiguity_or_writes(query, mode):
    assert evaluate_read_contract(resolve_goals(query), _registry()).mode == mode


async def test_unsupported_scan_location_cannot_be_answered_with_receiver_city():
    query = "ORD10001 的物流轨迹和最新扫描地点。"
    goals = resolve_goals(
        query,
        suggestions=[
            GoalSignal(quote="物流轨迹", kind="shipment"),
            GoalSignal(
                quote="最新扫描地点", category="field", kind="shipment", fields=("scan_location",)
            ),
        ],
    )
    provider = _PlanProvider()
    plan = await Planner(provider, _registry()).create_plan(
        query, "logistics", "", task_goals=goals
    )
    assert plan.read_contract_mode == "partial"
    trace = ToolResult(
        name="track_shipment",
        success=True,
        output={
            "order_id": "ORD10001",
            "city": "深圳",
            "events": [{"status": "in_transit", "at": "2026-10-01"}],
        },
    )
    response = await generate_node(
        {"plan": plan, "task_goals": goals, "tool_results": [trace]}, provider
    )
    assert "扫描地点" in response["final_answer"] and "暂未取得" in response["final_answer"]
    assert "深圳" not in response["final_answer"] and "运输中" in response["final_answer"]


async def test_bound_read_failure_never_tries_an_unverified_fallback():
    class BrokenShipment(TrackShipmentTool):
        async def execute(self, parsed, context):
            raise RuntimeError("offline fixture failure")

    class UnexpectedOrder(GetOrderTool):
        async def run(self, arguments, context):
            pytest.fail("fallback escaped the bounded shipment read")

    registry = ToolRegistry()
    registry.register(UnexpectedOrder())
    step = PlanStep(
        step_id=1, goal="shipment", tool_name="track_shipment", arguments={"order_id": "ORD10001"}
    )
    with pytest.raises(ToolExecutionError):
        await execute_with_fallback(
            BrokenShipment(),
            step,
            ToolContext(user_id="u_demo", session_id="test", trace_id="test"),
            registry,
            "查物流",
            allow_fallback=False,
        )


def test_multiple_same_tool_results_follow_executed_steps_and_respect_projection():
    query = "ORD10001 商品明细是否定制。ORD10002 买了什么。"
    goals = resolve_goals(
        query,
        suggestions=[
            GoalSignal(quote="商品明细是否定制", kind="order_items", fields=("items.customized",))
        ],
    )
    registry = ToolRegistry()
    registry.register(GetOrderItemsTool())
    contract = evaluate_read_contract(goals, registry)
    assert contract.calls and len(contract.calls) == 2
    plan = AgentPlan(
        steps=[
            PlanStep(step_id=index, goal="fixture", tool_name=call.name, arguments=call.arguments)
            for index, call in enumerate(contract.calls, 1)
        ]
    )
    values = [
        ToolResult(
            name="get_order_items",
            success=True,
            output={"items": [{"name": "马克杯", "customized": True}]},
        ),
        ToolResult(name="get_order_items", success=True, output={"items": []}),
    ]
    assert render_goal_answer(goals, plan, values, [1, 2]).splitlines() == [
        "ORD10001 订单商品明细：马克杯（定制）。",
        "ORD10002 订单商品明细：暂无商品明细。",
    ]
