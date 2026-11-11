import json

import pytest

from app.agents.nodes.planner import Planner, planner_node
from app.providers.base import LLMResponse
from app.schemas.agent import IntentResult
from app.tools.aftersale_tools import CancelOrderTool
from app.tools.order_tools import GetOrderTool
from app.tools.registry import ToolRegistry


class ReadOnlyModel:
    async def generate(self, *args, **kwargs):
        return LLMResponse(
            content=json.dumps(
                dict(
                    rationale="先只查询，等待确认再取消",
                    steps=[
                        dict(
                            step_id=1,
                            goal="查询状态",
                            tool_name="get_order",
                            arguments=dict(order_id="ORD82036"),
                        )
                    ],
                )
            )
        )


@pytest.mark.parametrize(
    "query,proposal",
    [
        ("请取消 ORD82036。", True),
        ("不要取消 ORD82036，只查询状态", False),
        ("如果还没发货再取消 ORD82036", False),
    ],
)
async def test_readonly_model_plan_still_proposes_only_explicit_cancellation(query, proposal):
    registry = ToolRegistry()
    registry.register(GetOrderTool())
    registry.register(CancelOrderTool())
    result = await planner_node(
        {
            "user_query": query,
            "intent": IntentResult(label="cancel_order", confidence=1, prompt_version="test"),
        },
        Planner(ReadOnlyModel(), registry),
    )
    assert bool(result.get("pending_action")) is proposal
    if proposal:
        assert result["pending_action"].tool_name == "cancel_order"
        assert result["pending_action"].arguments == dict(order_id="ORD82036")
