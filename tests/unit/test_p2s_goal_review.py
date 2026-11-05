"""Independent S3 review reproductions using synthetic inputs only."""

import json

from app.agents.goals import coverage
from app.agents.nodes.generate import generate_node
from app.agents.nodes.intent import rule_based_intent
from app.agents.nodes.planner import Planner, planner_node
from app.core.enums import RetrievalStrategy
from app.providers.base import LLMResponse
from app.retrieval.adaptive import rule_based_complexity
from app.schemas.agent import ToolResult
from app.tools.aftersale_tools import CancelOrderTool
from app.tools.order_tools import GetOrderTool
from app.tools.product_tools import CheckInventoryTool
from app.tools.registry import ToolRegistry


class Model:
    def __init__(self, payload):
        self.payload = payload

    async def generate(self, *args, **kwargs):
        return LLMResponse(content=json.dumps(self.payload, ensure_ascii=False))


def registry(*tools):
    value = ToolRegistry()
    for tool in tools:
        value.register(tool)
    return value


async def test_current_sku_does_not_accept_planner_invented_other_sku():
    llm = Model(
        {
            "steps": [
                {
                    "step_id": 1,
                    "goal": "库存",
                    "tool_name": "check_inventory",
                    "arguments": {"sku": "SKU-OTHER"},
                }
            ]
        }
    )
    plan = await Planner(llm, registry(CheckInventoryTool())).create_plan(
        "请查SKU-CURRENT的库存",
        "faq_policy",
        "",
    )
    assert all(step.arguments.get("sku") != "SKU-OTHER" for step in plan.steps), plan


async def test_product_price_goal_does_not_accept_name_only_answer():
    result = await generate_node(
        {
            "user_query": "SKU-CURRENT的价格是多少",
            "strategy": RetrievalStrategy.AGENT,
            "tool_results": [
                ToolResult(
                    name="get_product_detail",
                    success=True,
                    output={
                        "sku": "SKU-CURRENT",
                        "name": "耳机",
                        "price_cents": 1250,
                        "inventory": 7,
                    },
                )
            ],
        },
        Model({"answer": "SKU-CURRENT的名称是耳机。"}),
    )
    assert "12.50" in result["final_answer"], result


def test_other_sku_evidence_does_not_cover_current_inventory_goal():
    result = coverage(
        "请查SKU-CURRENT的库存",
        [
            ToolResult(
                name="check_inventory", success=True, output={"sku": "SKU-OTHER", "inventory": 7}
            ),
        ],
        "SKU-OTHER库存7件。",
    )
    assert not any(row["observed"] or row["conveyed"] for row in result), result


async def test_unresolved_only_if_write_does_not_create_unconditional_proposal():
    llm = Model(
        {
            "steps": [
                {
                    "step_id": 1,
                    "goal": "取消",
                    "tool_name": "cancel_order",
                    "arguments": {"order_id": "ORD7000"},
                }
            ]
        }
    )
    result = await planner_node(
        {
            "user_query": "SKU-CURRENT库存超过10件才取消订单ORD7000",
        },
        Planner(llm, registry(GetOrderTool(), CancelOrderTool())),
    )
    assert not result.get("pending_action"), result


def test_explicit_sku_coupon_policy_does_not_require_order_lookup():
    query = "SKU-CURRENT的优惠券优惠金额规则是什么"
    routed = rule_based_complexity(query, rule_based_intent(query))
    assert routed.strategy in {RetrievalStrategy.SINGLE, RetrievalStrategy.MULTI}, routed
