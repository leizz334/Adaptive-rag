"""Opt-in PostgreSQL checks against the disposable final engineering cluster."""

import asyncio
import json
import os
from contextlib import aclosing
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app import main
from app.config.settings import Settings
from app.core.exceptions import InvalidRequestError
from app.observability.execution import capture_tools
from app.repositories.models import AuditLogRow, MessageRow, OrderRow, SessionRow
from app.repositories.session_repository import SessionRepository
from app.schemas.chat import ChatRequest
from app.services.seed import seed_demo_data

_SANDBOX = "adaptive_rag_final_engineering"
_OWNER = "u_demo"


@pytest.fixture
async def postgres_app(monkeypatch):
    raw_url = os.getenv("ADAPTIVE_RAG_FINAL_PG_URL")
    if not raw_url:
        pytest.skip("requires the disposable PostgreSQL engineering cluster")
    url = make_url(raw_url)
    assert (url.drivername, url.host, url.database, url.username) == (
        "postgresql+asyncpg",
        "127.0.0.1",
        _SANDBOX,
        "adaptive_rag_final",
    )
    assert url.port and url.port >= 1024 and not url.query
    probe = create_async_engine(url, connect_args={"timeout": 3})
    try:
        async with probe.connect() as connection:
            assert await connection.scalar(text("SHOW cluster_name")) == _SANDBOX
            assert await connection.scalar(text("SELECT current_database()")) == _SANDBOX
    finally:
        await probe.dispose()

    # The archive runner has no .env. Supply the settings objects directly too.
    settings = Settings(
        _env_file=None,
        app_env="testing",
        database_url=raw_url,
        memory_mode="M2",
        deepseek_api_key="",
        embedding_api_key="",
        embedding_base_url="",
        local_embedding_enabled=False,
        cross_encoder_enabled=False,
        unstructured_enabled=False,
        mcp_enabled=False,
        mcp_remote_url="",
        redis_url="",
        qdrant_url="",
        agent_tracing_enabled=False,
    )
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    app = main.create_app()
    async with app.router.lifespan_context(app):
        factory = app.state.container.session_factory
        async with factory() as db:
            await seed_demo_data(db)
            await db.commit()
        yield app


async def _append_history(app, session_id, order_id):
    async with app.state.container.session_factory() as db:
        repo = SessionRepository(db)
        await repo.get_or_create(session_id, _OWNER)
        await repo.append_message(session_id, "user", f"请查询订单 {order_id} 的订单状态。")
        await repo.append_message(session_id, "assistant", "收到订单查询。")
        for index in range(12):
            await repo.append_message(session_id, "user", f"补充背景 {index}。")
            await repo.append_message(session_id, "assistant", "收到。")
        await db.commit()


async def _summary(app, session_id):
    async with app.state.container.session_factory() as db:
        row = await db.get(SessionRow, session_id)
        return json.loads(row.summary)


async def test_postgres_lifespan_sse_and_owner_boundary(postgres_app):
    app = postgres_app
    session_id = f"eng-sse-{uuid4().hex}"
    await _append_history(app, session_id, "ORD10001")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://engineering.test"
    ) as client:
        ready = await client.get("/api/v1/ready")
        capabilities = await client.get("/api/v1/capabilities")
        assert ready.status_code == capabilities.status_code == 200
        assert any(
            dep["name"] == "database" and dep["ready"] for dep in ready.json()["dependencies"]
        )
        assert capabilities.json()["database"] == "postgresql"
        assert capabilities.json()["llm"] == "offline"

        body = {"message": "它现在是什么状态？", "session_id": session_id}
        denied = await client.post("/api/v1/chat", json={**body, "user_id": "different-owner"})
        assert denied.status_code == 400 and denied.json()["error_code"] == "INVALID_REQUEST"
        with capture_tools() as events:
            async with client.stream(
                "POST", "/api/v1/chat/stream", json={**body, "user_id": _OWNER}
            ) as stream:
                assert stream.status_code == 200
                assert stream.headers["content-type"].startswith("text/event-stream")
                payload = [
                    json.loads(line[6:])
                    async for line in stream.aiter_lines()
                    if line.startswith("data: ")
                ]
    assert payload[0]["event"] == "started" and payload[-1]["event"] == "done"
    answer = next(item["data"] for item in payload if item["event"] == "answer")
    assert answer["session_id"] == session_id and "已发货" in answer["answer"]
    assert "".join(item["text"] for item in payload if item["event"] == "token") == answer["answer"]
    assert [(item["name"], item["arguments"]) for item in events] == [
        ("get_order", {"order_id": "ORD10001"})
    ]
    assert (await _summary(app, session_id))["owner_id"] == _OWNER


async def test_postgres_row_lock_blocks_another_transaction_until_release(postgres_app):
    app = postgres_app
    session_id = f"eng-lock-{uuid4().hex}"
    await _append_history(app, session_id, "ORD10001")
    factory = app.state.container.session_factory
    async with factory() as holder, factory() as waiting, factory() as observer:
        first = SessionRepository(holder)
        second = SessionRepository(waiting)
        first_pid = await holder.scalar(text("SELECT pg_backend_pid()"))
        second_pid = await waiting.scalar(text("SELECT pg_backend_pid()"))
        assert first_pid != second_pid
        await first.lock_owned(session_id, _OWNER)
        competing = asyncio.create_task(second.lock_owned(session_id, _OWNER))
        try:
            async with asyncio.timeout(5):
                while first_pid not in await observer.scalar(
                    text("SELECT pg_blocking_pids(:pid)"), {"pid": second_pid}
                ):
                    await asyncio.sleep(0.01)
            assert not competing.done()
            await holder.rollback()
            acquired = await asyncio.wait_for(competing, 5)
            assert acquired.user_id == _OWNER
        finally:
            if not competing.done():
                competing.cancel()
                await asyncio.gather(competing, return_exceptions=True)
        await waiting.rollback()
        with pytest.raises(InvalidRequestError):
            await SessionRepository(observer).lock_owned(session_id, "different-owner")


async def test_postgres_overlapping_turns_preserve_both_messages_and_newer_summary(postgres_app):
    app = postgres_app
    service = app.state.container.chat_service
    session_id = f"eng-overlap-{uuid4().hex}"
    slow = "请查询订单 ORD10001 的订单状态。"
    fast = "请查询订单 ORD10003 的实付金额。"
    await _append_history(app, session_id, "ORD10001")
    async with aclosing(
        service.stream(
            ChatRequest(message=slow, session_id=session_id, user_id=_OWNER), trace_id="eng-slow"
        )
    ) as stream:
        assert (await anext(stream))["event"] == "started"
        await asyncio.wait_for(_append_history(app, session_id, "ORD10003"), 5)
        newer = await asyncio.wait_for(
            service.chat(
                ChatRequest(message=fast, session_id=session_id, user_id=_OWNER),
                trace_id="eng-fast",
            ),
            5,
        )
        assert "79.00 元" in newer.answer
        earlier_commit = await _summary(app, session_id)
        assert earlier_commit["order_ids"] == ["ORD10003"]
        assert ([item["event"] async for item in stream])[-1] == "done"

    latest = await _summary(app, session_id)
    assert latest["coverage_message_id"] >= earlier_commit["coverage_message_id"]
    assert latest["order_ids"] == ["ORD10003"]
    async with app.state.container.session_factory() as db:
        rows = (
            await db.execute(
                select(MessageRow.role, MessageRow.content)
                .where(MessageRow.session_id == session_id)
                .order_by(MessageRow.id)
            )
        ).all()
    assert [role for role, _ in rows[-4:]] == ["user", "assistant", "user", "assistant"]
    assert rows[-4].content == fast and rows[-2].content == slow


async def test_postgres_failed_commit_rolls_back_confirmed_write_and_summary(
    postgres_app, monkeypatch
):
    app = postgres_app
    factory = app.state.container.session_factory
    service = app.state.container.chat_service
    session_id = f"eng-rollback-{uuid4().hex}"
    proposal = await service.chat(
        ChatRequest(message="请取消订单 ORD10003。", user_id=_OWNER, session_id=session_id),
        trace_id="eng-proposal",
    )
    assert proposal.pending_action
    original_summary = await _summary(app, session_id)

    async def fail_after_flush(db):
        await db.flush()
        assert (await db.get(OrderRow, "ORD10003")).status == "cancelled"
        raise RuntimeError("engineering synthetic commit failure")

    monkeypatch.setattr(service, "_commit", fail_after_flush)
    with capture_tools() as events, pytest.raises(RuntimeError, match="synthetic commit failure"):
        await service.chat(
            ChatRequest(
                message="确认取消。",
                user_id=_OWNER,
                session_id=session_id,
                confirm_action_id=proposal.pending_action.action_id,
            ),
            trace_id="eng-rollback",
        )
    assert [(item["name"], item["success"]) for item in events] == [("cancel_order", True)]
    async with factory() as db:
        assert (await db.get(OrderRow, "ORD10003")).status == "paid"
        assert (
            await db.scalar(
                select(func.count())
                .select_from(AuditLogRow)
                .where(AuditLogRow.trace_id == "eng-rollback")
            )
            == 0
        )
        assert (
            await db.scalar(
                select(func.count())
                .select_from(MessageRow)
                .where(MessageRow.session_id == session_id)
            )
            == 2
        )
    assert await _summary(app, session_id) == original_summary
