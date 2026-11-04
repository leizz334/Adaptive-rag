import pytest

from app.repositories.session_repository import SessionRepository
from app.schemas.chat import ChatRequest
from eval.environment import BusinessEnvironment


@pytest.mark.parametrize("query", ["之前买的商品退货规则是什么", "之前买的商品怎么退货"])
async def test_temporal_general_policy_question_does_not_require_an_order(query):
    async with BusinessEnvironment(memory_mode="M2") as env:
        result = await env.service.chat(
            ChatRequest(message=query, user_id="u_demo"), trace_id="policy"
        )
        assert result.intent is not None
        assert result.citations
        assert "请明确需要处理的订单号" not in result.answer


async def test_m1_loads_the_configured_window_beyond_twenty_messages():
    async with BusinessEnvironment(memory_mode="M1") as env:
        env.service._settings.memory_recent_messages = 100
        async with env.container.session_factory() as db:
            repo = SessionRepository(db)
            await repo.get_or_create("window100", "u_demo")
            await repo.append_message("window100", "user", "查询订单 ORD10001")
            for i in range(24):
                await repo.append_message("window100", "user", f"补充信息{i}")
            await db.commit()
        async with env.container.session_factory() as db:
            state = await env.service._initial_state(
                db,
                ChatRequest(message="它现在是什么状态", user_id="u_demo", session_id="window100"),
                "window100",
                "test",
            )
        assert len(state["messages"]) == 25
        assert state["selected_context"].order_id == "ORD10001"
