import json

import pytest

from app.agents.goals import resolve_goals
from app.agents.nodes.planner import Planner
from app.agents.planning import select_planning_strategy
from app.providers.base import LLMResponse
from app.schemas.goals import GoalKind, GoalSignal, TaskGoal
from app.tools.aftersale_tools import GetRefundStatusTool
from app.tools.goal_contract import evaluate_read_contract
from app.tools.logistics_tools import TrackShipmentTool
from app.tools.order_tools import GetOrderTool
from app.tools.product_tools import CheckInventoryTool, GetProductDetailTool
from app.tools.registry import ToolRegistry


class NoPlannerRequest:
    async def generate(self, *args, **kwargs):
        pytest.fail("complete read must skip the Planner model")


def registry():
    value = ToolRegistry()
    for tool in (
        GetOrderTool(),
        GetRefundStatusTool(),
        TrackShipmentTool(),
        CheckInventoryTool(),
        GetProductDetailTool(),
    ):
        value.register(tool)
    return value


@pytest.mark.parametrize(
    ("query", "expected", "combined"),
    [
        ("查 ORD10001 的状态和实付金额", [("get_order", "ORD10001")], 1),
        ("ORD10001 退款状态", [("get_refund_status", "ORD10001")], 0),
        ("查 ORD10001 物流轨迹", [("track_shipment", "ORD10001")], 0),
        ("SKU-HEADSET 价格和库存", [("get_product_detail", "SKU-HEADSET")], 1),
        (
            "查 ORD10001 的订单状态和退款进度",
            [("get_order", "ORD10001"), ("get_refund_status", "ORD10001")],
            0,
        ),
        (
            "查 SKU-HEADSET 的库存，查 SKU-TEE 的库存",
            [("check_inventory", "SKU-HEADSET"), ("check_inventory", "SKU-TEE")],
            0,
        ),
    ],
)
async def test_direct_contract_uses_minimal_distinct_reads(query, expected, combined):
    goals = resolve_goals(query)
    plan = await Planner(NoPlannerRequest(), registry()).create_plan(
        query, "order_inquiry", "", task_goals=goals
    )
    assert plan.planning_strategy == "direct" and plan.planner_llm_calls == 0
    assert plan.planning_covered_goals == len(goals)
    assert plan.planning_deduplicated_calls == combined
    assert [
        (step.tool_name, next(iter(step.arguments.values()))) for step in plan.steps
    ] == expected


def test_complete_contract_with_unsourced_entity_stays_dynamic():
    goals = [
        TaskGoal(
            kind=GoalKind.ORDER_STATUS,
            request_text="订单状态",
            entity_type="order",
            entity_id="ORD10001",
            fields=("status",),
        )
    ]
    decision = select_planning_strategy(goals, evaluate_read_contract(goals, registry()))
    assert decision.strategy == "dynamic" and decision.reason == "untrusted_entity"


async def test_conditional_read_uses_clarification_without_a_tool_plan():
    query = "如果订单已经支付，查 ORD10001 物流轨迹"
    plan = await Planner(NoPlannerRequest(), registry()).create_plan(
        query, "logistics", "", task_goals=resolve_goals(query)
    )
    assert plan.planning_strategy == "clarify" and plan.planner_llm_calls == 0
    assert not plan.steps


async def test_partial_read_keeps_the_bounded_dynamic_planner():
    class Provider:
        async def generate(self, messages, **kwargs):
            return LLMResponse(
                json.dumps(
                    {
                        "steps": [
                            {
                                "step_id": 1,
                                "goal": "x",
                                "tool_name": "track_shipment",
                                "arguments": {"order_id": "ORD10002"},
                            }
                        ]
                    }
                )
            )

    query = "查 ORD10001 物流轨迹。还需要最近一条物流的扫描地。"
    goals = resolve_goals(
        query,
        suggestions=[
            GoalSignal(
                category="field",
                kind="shipment",
                quote="还需要最近一条物流的扫描地",
                fields=("scan_location",),
            )
        ],
    )
    plan = await Planner(Provider(), registry()).create_plan(
        query, "logistics", "", task_goals=goals
    )
    assert plan.planning_strategy == "partial" and plan.planner_llm_calls == 1
    assert [step.arguments for step in plan.steps] == [{"order_id": "ORD10001"}]
