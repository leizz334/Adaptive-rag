import pytest

from app.observability.execution import capture_tools
from app.schemas.chat import ChatRequest
from eval.environment import BusinessEnvironment


@pytest.mark.parametrize(
    ("query", "intent", "calls"),
    [
        ("帮我查一下订单 ORD10001 的状态。", "order_inquiry", [("get_order", "ORD10001")]),
        ("查一下 ORD10001 的快递到哪儿了", "logistics", [("track_shipment", "ORD10001")]),
        ("ORD10002 的退款到哪了，之前已经申请了", "refund", [("get_refund_status", "ORD10002")]),
        ("SKU-HEADSET 现货还剩多少", "product_consult", [("check_inventory", "SKU-HEADSET")]),
        (
            "看 ORD10001 的订单状态，同时查退款进度和物流轨迹",
            "order_inquiry",
            [
                ("get_order", "ORD10001"),
                ("get_refund_status", "ORD10001"),
                ("track_shipment", "ORD10001"),
            ],
        ),
    ],
)
async def test_task_goals_drive_exact_registered_reads(query, intent, calls):
    async with BusinessEnvironment(memory_mode="M2") as env:
        with capture_tools() as events:
            response = await env.service.chat(
                ChatRequest(user_id="u_demo", message=query), trace_id="p2"
            )
        assert response.intent == intent
        assert response.strategy == "agent" and response.pending_action is None
        assert [
            (e["name"], e["arguments"].get("order_id") or e["arguments"].get("sku")) for e in events
        ] == calls
        assert all(e["success"] for e in events)
        if len(calls) > 1:
            assert "订单状态" in response.answer
            assert "物流状态" in response.answer
            assert "退款" in response.answer


async def test_p2_contract_cannot_read_another_owners_refund():
    async with BusinessEnvironment(memory_mode="M2") as env:
        with capture_tools() as events:
            await env.service.chat(
                ChatRequest(user_id="other", message="查一下 ORD10002 的退款进度"),
                trace_id="p2_owner",
            )
        assert [event["name"] for event in events] == ["get_refund_status"]
        assert events[0]["failure_kind"] == "business_rejected"
        assert not events[0]["output"]


async def test_supported_model_answer_still_covers_all_bound_facts():
    from app.prompts.answer import ANSWER_SYSTEM
    from app.providers.base import LLMResponse
    from eval.memory_ablation import ScriptedProvider

    class OmitAmount(ScriptedProvider):
        async def generate(self, messages, **kwargs):
            result = await super().generate(messages, **kwargs)
            if messages[0]["content"] == ANSWER_SYSTEM:
                return LLMResponse('{"answer":"订单已支付。"}')
            return result

    provider = OmitAmount()
    async with BusinessEnvironment(memory_mode="M2", llm=provider) as env:
        result = await env.service.chat(
            ChatRequest(user_id="u_demo", message="查 ORD10003 的订单状态和实付金额"),
            trace_id="p2-coverage",
        )
    assert "已支付" in result.answer and "79.00 元" in result.answer
    assert len(provider.calls) == 2  # Intent and Router. Exact facts are rendered from the tools.
