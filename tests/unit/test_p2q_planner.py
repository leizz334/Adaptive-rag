"""Generic QC repros, independent of frozen scenario IDs and order numbers."""

import json

import pytest
from pydantic import BaseModel

from app.agents.nodes.executor import execute_with_fallback
from app.agents.nodes.planner import Planner, skill_to_plan
from app.core.exceptions import InvalidRequestError, ToolExecutionError
from app.providers.base import LLMResponse
from app.schemas.agent import PlanStep, ToolResult
from app.tools.base import Tool, ToolContext
from app.tools.registry import ToolRegistry


class Input(BaseModel):
    order_id: str = "ORD24680"


class Read(Tool):
    name = "track_shipment"
    description = "synthetic read"
    input_model = Input

    def __init__(self, failure=None):
        self.failure = failure
        self.calls = 0

    async def execute(self, parsed, context):
        self.calls += 1
        if self.failure:
            raise self.failure
        return ToolResult(name=self.name, success=True, output={"status": "shipped"})


def registry_for(*tools):
    registry = ToolRegistry()
    for tool in tools:
        registry.register(tool)
    return registry


async def test_deterministic_business_rejection_never_repeats_owner_lookup():
    denied = Read(InvalidRequestError("order not found"))
    backup = Read()
    backup.name = "get_order"
    registry = registry_for(denied, backup)
    with pytest.raises(InvalidRequestError):
        await execute_with_fallback(
            denied,
            PlanStep(
                step_id=1, goal="lookup", tool_name=denied.name, arguments={"order_id": "ORD24680"}
            ),
            ToolContext(user_id="test-user", session_id="test-session", trace_id="test"),
            registry,
            "查询订单 ORD24680 状态",
        )
    assert denied.calls == 1
    assert backup.calls == 0


async def test_transient_read_failure_keeps_fallback_and_fresh_next_turn():
    failed = Read(ToolExecutionError("temporary backend outage"))
    backup = Read()
    backup.name = "get_order"
    registry = registry_for(failed, backup)
    for _ in range(2):
        result = await execute_with_fallback(
            failed,
            PlanStep(
                step_id=1, goal="lookup", tool_name=failed.name, arguments={"order_id": "ORD24680"}
            ),
            ToolContext(user_id="test-user", session_id="test-session", trace_id="test"),
            registry,
            "查询物流",
        )
        assert result.name == "get_order"
    assert failed.calls == backup.calls == 2


@pytest.mark.parametrize(
    "query", ["查询订单 ORD24680 状态", "订单 ORD24680 金额是多少", "ORD24680 是否已发货"]
)
def test_status_only_skill_does_not_query_shipment_events(query):
    skill = dict(name="order_tracking", tools=["get_order", "track_shipment"])
    order, shipment = Read(), Read()
    order.name = "get_order"
    plan = skill_to_plan(skill, query, registry_for(order, shipment))
    assert [step.tool_name for step in plan.steps] == ["get_order"]


@pytest.mark.parametrize(
    "query",
    [
        "订单 ORD24680 物流到哪了",
        "订单 ORD24680 状态和快递轨迹",
        "查 ORD24680 运单号",
        "查订单 ORD24680 的运输状态和历史节点",
    ],
)
def test_logistics_evidence_remains_available(query):
    skill = dict(name="order_tracking", tools=["get_order", "track_shipment"])
    order, shipment = Read(), Read()
    order.name = "get_order"
    plan = skill_to_plan(skill, query, registry_for(order, shipment))
    assert "track_shipment" in [step.tool_name for step in plan.steps]


async def test_real_shaped_planner_extra_step_is_pruned_only_for_status_request():
    class Provider:
        async def generate(self, *args, **kwargs):
            return LLMResponse(
                json.dumps(
                    dict(
                        steps=[
                            dict(
                                step_id=i,
                                goal="read",
                                tool_name=name,
                                arguments={"order_id": "ORD24680"},
                            )
                            for i, name in enumerate(["get_order", "track_shipment"], 1)
                        ]
                    )
                )
            )

    order, shipment = Read(), Read()
    order.name = "get_order"
    planner = Planner(Provider(), registry_for(order, shipment))
    status = await planner.create_plan("订单 ORD24680 状态", "order_inquiry", "")
    logistics = await planner.create_plan("订单 ORD24680 状态和物流轨迹", "logistics", "")
    assert [step.tool_name for step in status.steps] == ["get_order"]
    assert [step.tool_name for step in logistics.steps] == ["get_order", "track_shipment"]
    transport = await planner.create_plan(
        "查订单 ORD24680 的运输状态和历史节点", "order_inquiry", ""
    )
    assert [step.tool_name for step in transport.steps] == ["get_order", "track_shipment"]
