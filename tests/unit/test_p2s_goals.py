import pytest

from app.agents.nodes.intent import rule_based_intent
from app.agents.nodes.planner import Planner, _evidence_tools, _explicit_write_request
from app.core.enums import RetrievalStrategy
from app.providers.fake import OfflineLLMProvider
from app.retrieval.adaptive import rule_based_complexity
from eval.environment import BusinessEnvironment


@pytest.mark.parametrize(
    "query,expected",
    [
        ("核实这笔订单处于哪个处理阶段", ["get_order"]),
        ("付款一共花了多少，同时看看配送节点", ["get_order", "track_shipment"]),
        ("快递不用展开，只想知道实付总额", ["get_order"]),
        ("只问运输过程，不必讲支付金额", ["track_shipment"]),
        ("看看订单买的东西各有几件", ["get_order_items"]),
        ("我有没有退款申请记录，列出已有退款单", ["get_refund_status"]),
    ],
)
def test_generic_read_evidence_contract(query, expected):
    assert _evidence_tools(query) == expected


@pytest.mark.parametrize(
    "query",
    [
        "SKU-OTHER1 还剩多少现货",
        "请核实SKU-OTHER1保修期",
        "SKU-OTHER1的详细资料和价格",
    ],
)
def test_explicit_sku_business_goal_routes_to_actual_tools(query):
    assert (
        rule_based_complexity(query, rule_based_intent(query)).strategy == RetrievalStrategy.AGENT
    )


@pytest.mark.parametrize(
    "query,tool,args",
    [
        ("核对 ORD10001 已有退款单列表", "get_refund_status", dict(order_id="ORD10001")),
        ("SKU-HEADSET还有多少库存", "check_inventory", dict(sku="SKU-HEADSET")),
        ("SKU-HEADSET保修多久", "get_warranty", dict(sku="SKU-HEADSET")),
        ("SKU-HEADSET详细资料是什么", "get_product_detail", dict(sku="SKU-HEADSET")),
    ],
)
async def test_actual_catalog_read_goal_arguments(query, tool, args):
    async with BusinessEnvironment(memory_mode="M2") as env:
        plan = await Planner(OfflineLLMProvider(), env.service.registry).create_plan(
            query, rule_based_intent(query).label.value, ""
        )
        assert [(s.tool_name, s.arguments) for s in plan.steps] == [(tool, args)]


@pytest.mark.parametrize(
    "query",
    [
        "不要取消订单，只想查状态",
        "如果还没发货就取消订单",
        "不用申请退款，先查询",
        "别帮我退货，只查政策",
    ],
)
def test_negative_or_conditional_write_never_creates_proposal_without_resolution(query):
    assert not _explicit_write_request(query, "cancel_order")
    assert not _explicit_write_request(query, "create_refund_request")
    assert not _explicit_write_request(query, "create_return_request")


def test_static_general_policy_remains_rag_without_sku():
    query = "商品的一般保修规则是什么"
    assert rule_based_complexity(query, rule_based_intent(query)).strategy in {
        RetrievalStrategy.SINGLE,
        RetrievalStrategy.MULTI,
    }


def test_rejecting_product_then_explicit_cancel_is_not_negated_cancel():
    assert _explicit_write_request("这件不想要了，请帮我取消订单", "cancel_order")


async def test_offline_mixed_answer_conveys_both_actual_facts():
    from app.agents.nodes.generate import generate_node
    from app.schemas.agent import ToolResult

    result = await generate_node(
        dict(
            user_query="核对ORD2468实付总额和快递状态",
            strategy=RetrievalStrategy.AGENT,
            tool_results=[
                ToolResult(
                    name="get_order",
                    success=True,
                    output=dict(order_id="ORD2468", status="shipped", total_cents=37456),
                ),
                ToolResult(
                    name="track_shipment",
                    success=True,
                    output=dict(order_id="ORD2468", events=[dict(status="in_transit")]),
                ),
            ],
        ),
        OfflineLLMProvider(),
    )
    assert "374.56" in result["final_answer"] and "运输中" in result["final_answer"]


async def test_static_policy_answer_not_replaced_by_missing_business_goal():
    from app.agents.nodes.generate import generate_node
    from app.providers.base import LLMResponse

    class PolicyModel:
        async def generate(self, *args, **kwargs):
            return LLMResponse('{"answer":"定制商品不适用七天无理由。"}')

    value = await generate_node(
        dict(user_query="定制商品能退吗", strategy=RetrievalStrategy.SINGLE), PolicyModel()
    )
    assert value["final_answer"] == "定制商品不适用七天无理由。"


def test_mixed_live_shipment_and_policy_has_both_evidence_sources():
    assert _evidence_tools("查订单ORD2468的物流，并说明配送时效政策") == [
        "track_shipment",
        "search_knowledge",
    ]
