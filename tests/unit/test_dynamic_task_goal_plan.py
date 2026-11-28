import json
from functools import partial

import pytest

from app.agents.goals import resolve_goals
from app.agents.nodes.planner import Planner, planner_node
from app.agents.planning import select_planning_strategy
from app.providers.base import LLMResponse
from app.schemas.agent import IntentResult
from app.tools.aftersale_tools import CancelOrderTool, GetRefundStatusTool
from app.tools.logistics_tools import TrackShipmentTool
from app.tools.order_tools import GetOrderTool
from app.tools.registry import ToolRegistry


class Provider:
    def __init__(self, steps):
        self.calls = []
        self.steps = steps

    async def generate(self, messages, **kwargs):
        self.calls.append(messages)
        return LLMResponse(json.dumps({"steps": self.steps, "rationale": "fixture"}))


def tool_step(name, order="ORD10001"):
    return {"step_id": 1, "goal": "fixture", "tool_name": name, "arguments": {"order_id": order}}


def registry():
    value = ToolRegistry()
    for tool in (GetOrderTool(), TrackShipmentTool(), GetRefundStatusTool(), CancelOrderTool()):
        value.register(tool)
    return value


async def test_model_planner_still_runs_and_contract_repairs_missing_or_wrong_read_steps(
    monkeypatch,
):
    monkeypatch.setattr(
        "app.agents.nodes.planner.select_planning_strategy",
        partial(select_planning_strategy, direct_enabled=False),
    )
    query = "查询 ORD10001 的物流信息，顺便看退款进度"
    provider = Provider(
        [tool_step("get_order"), tool_step("track_shipment", "ORD10002"), tool_step("cancel_order")]
    )
    planner = Planner(provider, registry())
    plan = await planner.create_plan(query, "logistics", "", task_goals=resolve_goals(query))
    assert len(provider.calls) == 1
    assert "- track_shipment:" in provider.calls[0][0]["content"]
    assert "- get_refund_status:" in provider.calls[0][0]["content"]
    assert "- get_order:" not in provider.calls[0][0]["content"]
    assert [(s.tool_name, s.arguments) for s in plan.steps] == [
        ("track_shipment", {"order_id": "ORD10001"}),
        ("get_refund_status", {"order_id": "ORD10001"}),
    ]


@pytest.mark.parametrize("query", ["如果没发货就取消 ORD10001", "不要取消 ORD10001"])
async def test_conditional_or_negated_write_is_not_promoted_to_confirmation(query):
    provider = Provider([tool_step("cancel_order")])
    state = {
        "user_query": query,
        "task_goals": resolve_goals(query),
        "intent": IntentResult(label="cancel_order", confidence=1, prompt_version="test"),
    }
    result = await planner_node(state, Planner(provider, registry()))
    assert result["pending_action"] is None
    assert all(step.tool_name != "cancel_order" for step in result["plan"].steps)
