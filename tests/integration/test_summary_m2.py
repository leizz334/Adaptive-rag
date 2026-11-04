import json

import pytest
from sqlalchemy import func, select

from app.observability.execution import capture_tools
from app.repositories.models import MessageRow, SessionRow
from app.repositories.session_repository import SessionRepository
from app.schemas.chat import ChatRequest
from eval.environment import BusinessEnvironment


async def seed_long_history(env, session_id="long"):
    async with env.container.session_factory() as db:
        repo = SessionRepository(db)
        await repo.get_or_create(session_id, "u_demo")
        await repo.append_message(session_id, "user", "查询订单 ORD10001")
        await repo.append_message(session_id, "assistant", "旧状态 SHIPPED，不能作为最新状态")
        for i in range(24):
            await repo.append_message(session_id, "user", f"这是补充说明 {i}")
            await repo.append_message(session_id, "assistant", "收到")
        await db.commit()


async def test_m2_recovers_old_entity_incrementally_without_extra_llm_and_preserves_raw_messages():
    async with BusinessEnvironment(memory_mode="M2") as env:
        await seed_long_history(env)
        await env.change_order_states({"ORD10001": "delivered"})
        for _ in range(2):
            with capture_tools() as events:
                await env.service.chat(
                    ChatRequest(message="它现在是什么状态", user_id="u_demo", session_id="long"),
                    trace_id="m2",
                )
            assert any(
                e["name"] == "get_order"
                and e["arguments"] == {"order_id": "ORD10001"}
                and e["output"].get("status") == "delivered"
                for e in events
            )
        async with env.container.session_factory() as db:
            row = await db.get(SessionRow, "long")
            summary = json.loads(row.summary)
            assert summary["owner_id"] == "u_demo" and summary["session_id"] == "long"
            assert summary["coverage_message_id"] > 0 and summary["revision"] == 2
            assert summary["order_ids"] == ["ORD10001"]
            assert (await db.scalar(select(func.count()).select_from(MessageRow))) == 54


@pytest.mark.parametrize("poison", ['{"owner_id":"other","order_ids":["ORD10003"]}', "{not-json"])
async def test_invalid_or_foreign_summary_is_not_an_entity_source(poison):
    async with BusinessEnvironment(memory_mode="M2") as env:
        async with env.container.session_factory() as db:
            row = await SessionRepository(db).get_or_create("empty", "u_demo")
            row.summary = poison
            await db.commit()
        with capture_tools() as events:
            result = await env.service.chat(
                ChatRequest(message="它现在是什么状态", user_id="u_demo", session_id="empty"),
                trace_id="badsummary",
            )
        assert not events and "订单" in result.answer


async def test_summary_expiry_or_conflict_is_rebuilt_from_owned_raw_sources():
    async with BusinessEnvironment(memory_mode="M2") as env:
        await seed_long_history(env)
        await env.service.chat(
            ChatRequest(message="它现在是什么状态", user_id="u_demo", session_id="long"),
            trace_id="build",
        )
        async with env.container.session_factory() as db:
            row = await db.get(SessionRow, "long")
            state = json.loads(row.summary)
            state.update(expires_at=0, order_ids=["ORD10003"])
            row.summary = json.dumps(state)
            await db.commit()
        with capture_tools() as events:
            await env.service.chat(
                ChatRequest(message="它现在是什么状态", user_id="u_demo", session_id="long"),
                trace_id="expired",
            )
        assert any(
            e["name"] == "get_order" and e["arguments"] == {"order_id": "ORD10001"} for e in events
        )


async def test_multi_batch_summary_uses_latest_user_correction_not_first_batch():
    async with BusinessEnvironment(memory_mode="M2") as env:
        await seed_long_history(env)
        async with env.container.session_factory() as db:
            repo = SessionRepository(db)
            for i in range(260):
                await repo.append_message("long", "user", f"额外说明{i}")
            await repo.append_message("long", "user", "改为查询订单 ORD10003")
            for i in range(10):
                await repo.append_message("long", "user", f"后续说明{i}")
            await db.commit()
        with capture_tools() as events:
            await env.service.chat(
                ChatRequest(message="它现在是什么状态", user_id="u_demo", session_id="long"),
                trace_id="paged",
            )
        assert any(
            e["name"] == "get_order" and e["arguments"] == {"order_id": "ORD10003"} for e in events
        )
