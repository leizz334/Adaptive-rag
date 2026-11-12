"""Offline contracts for authenticated, bounded workbench inspection."""

import json
from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.auth import Principal
from app.core.time import utcnow
from app.repositories.models import Base, IdempotencyRow, PendingConfirmationRow, SessionRow


def test_trace_store_bounds_ttl_owner_and_defensive_copy():
    from app.observability.workbench import WorkbenchStore

    now = [0.0]
    store = WorkbenchStore(ttl=10, max_records=1, clock=lambda: now[0])
    store.put("root", "alice", "session", {"nodes": ["memory"]})
    assert store.get("root", "bob", "session") is None
    assert store.get("root", "alice", "other") is None
    result = store.get("root", "alice", "session")
    result["nodes"].append("forged")
    assert store.get("root", "alice", "session")["nodes"] == ["memory"]
    now[0] = 11
    assert store.get("root", "alice", "session") is None
    store.put("one", "alice", "session", {})
    store.put("two", "alice", "session", {})
    assert store.get("one", "alice", "session") is None


def test_state_projection_has_no_raw_prompt_arguments_or_credentials():
    from app.observability.workbench import project_state

    state = dict(
        user_query="RAW_PROMPT",
        summary="PRIVATE_SUMMARY",
        messages=[1, 2],
        plan=SimpleNamespace(
            steps=[
                SimpleNamespace(
                    step_id=1,
                    tool_name="lookup",
                    needs_retrieval=True,
                    arguments={"secret": "RAW_ARGUMENT"},
                    goal="RAW_GOAL",
                )
            ]
        ),
        tool_results=[SimpleNamespace(name="lookup", success=True, output={"key": "RAW_OUTPUT"})],
        retrieved_chunks=[
            SimpleNamespace(
                document_id="doc",
                title="Title",
                content="Bearer abc123 api_key=secret123",
                chunk_id="chunk",
            )
        ],
    )
    value = project_state(state, "M2")
    serialized = json.dumps(value)
    assert all(
        secret not in serialized
        for secret in [
            "RAW_PROMPT",
            "PRIVATE_SUMMARY",
            "RAW_ARGUMENT",
            "RAW_GOAL",
            "RAW_OUTPUT",
            "abc123",
            "secret123",
        ]
    )
    assert value["memory"] == {"mode": "M2", "message_count": 2, "summary_used": True}
    assert value["tools"] == [{"name": "lookup", "success": True, "result": {}}]


@pytest.fixture
async def access():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as db:
        await db.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        db.add(SessionRow(session_id="session", user_id="alice"))
        db.add(
            PendingConfirmationRow(
                action_id="action",
                session_id="session",
                user_id="alice",
                action_json="{}",
                expires_at=utcnow() + timedelta(minutes=15),
            )
        )
        await db.commit()
    yield Principal("alice", frozenset({"user"})), SimpleNamespace(session_factory=factory)
    await engine.dispose()


async def test_cancel_rejects_foreign_completed_and_repeat(access):
    from app.api.routes.workbench import cancel_action

    principal, container = access
    with pytest.raises(HTTPException) as exc:
        await cancel_action("session", "action", (Principal("bob", frozenset({"user"})), container))
    assert exc.value.status_code == 404
    async with container.session_factory() as db:
        db.add(IdempotencyRow(key="action", fingerprint="f", response_json="{}"))
        await db.commit()
    with pytest.raises(HTTPException) as exc:
        await cancel_action("session", "action", access)
    assert exc.value.status_code == 409
    async with container.session_factory() as db:
        await db.delete(await db.get(IdempotencyRow, "action"))
        await db.commit()
    assert await cancel_action("session", "action", access) == {
        "action_id": "action",
        "status": "cancelled",
    }
    with pytest.raises(HTTPException) as exc:
        await cancel_action("session", "action", access)
    assert exc.value.status_code == 404


async def test_access_rejects_legacy_and_rate_failure():
    from app.api.routes.workbench import workbench_access
    from app.core.exceptions import RateLimitError, ToolPermissionError

    with pytest.raises(ToolPermissionError):
        await workbench_access(None, None)

    class Chat:
        async def _enforce_rate_limit(self, subject):
            raise RateLimitError()

    with pytest.raises(RateLimitError):
        await workbench_access(
            Principal("alice", frozenset({"user"})), SimpleNamespace(chat_service=Chat())
        )


async def test_principal_self_only_verified_identity():
    from app.api.routes.identity import self_principal
    from app.core.exceptions import ToolPermissionError

    called = []

    class Chat:
        async def _enforce_rate_limit(self, subject):
            called.append(subject)

    container = SimpleNamespace(chat_service=Chat())
    with pytest.raises(ToolPermissionError):
        await self_principal(None, container)
    assert await self_principal(Principal("alice", frozenset({"user"})), container) == {
        "subject": "alice",
        "roles": ["user"],
    }
    assert called == ["alice"]


async def test_actual_offline_chat_and_sse_capture_owner_nodes_and_disabled_miss():
    from app.api.routes.workbench import trace
    from app.config.settings import Settings
    from app.observability.tracing import TraceRecorder
    from app.schemas.chat import ChatRequest
    from app.services.container import build_container

    settings = Settings(
        _env_file=None,
        app_env="testing",
        database_url="sqlite+aiosqlite:///:memory:",
        deepseek_api_key="",
        embedding_api_key="",
        redis_url="",
        qdrant_url="",
        agent_tracing_enabled=False,
    )
    container = await build_container(settings, seed=True)
    try:
        service = container.chat_service
        off = await service.chat(ChatRequest(message="你好", user_id="alice"), trace_id="forged")
        assert off.root_run_id is None
        assert service.workbench_store.get("forged", "alice", off.session_id) is None
        service._tracer = TraceRecorder(enabled=True, sink=lambda spans: None)
        on = await service.chat(ChatRequest(message="你好", user_id="alice"), trace_id="forged")
        snapshot = await trace(
            on.session_id, on.root_run_id, (Principal("alice", frozenset({"user"})), container)
        )
        assert snapshot["root_run_id"] != "forged"
        assert {"guardrail", "intent", "router", "generate", "memory"} <= set(snapshot["nodes"])
        assert snapshot["spans"][0]["status"] == "ok"
        assert snapshot["memory"]["message_count"] == 0
        assert snapshot["availability"]["storage"] == "process_local"
        for session, root, who in [
            (on.session_id, on.root_run_id, "bob"),
            (off.session_id, on.root_run_id, "alice"),
            (on.session_id, "missing", "alice"),
        ]:
            with pytest.raises(HTTPException) as exc:
                await trace(session, root, (Principal(who, frozenset({"user"})), container))
            assert exc.value.status_code == 404
        events = [
            e
            async for e in service.stream(
                ChatRequest(message="你好", user_id="alice"), trace_id="forged"
            )
        ]
        answer = next(e["data"] for e in events if e["event"] == "answer")
        streamed = service.workbench_store.get(answer["root_run_id"], "alice", answer["session_id"])
        assert "generate" in streamed["nodes"]
        assert streamed["root_run_id"] != on.root_run_id
    finally:
        await container.aclose()


async def test_document_listing_own_metadata_only(access):
    from app.api.routes.knowledge import list_documents
    from app.repositories.models import PrivateKnowledgeDocumentRow

    async with access[1].session_factory() as db:
        db.add_all(
            [
                PrivateKnowledgeDocumentRow(
                    subject=who,
                    document_id=doc,
                    revision="r",
                    title="Title",
                    content="PRIVATE_CONTENT",
                )
                for who, doc in [("alice", "a"), ("bob", "b")]
            ]
        )
        await db.commit()
    result = await list_documents(access)
    assert result == {
        "documents": [
            {"document_id": "a", "title": "Title", "revision": "r", "character_count": 15}
        ]
    }
    assert "PRIVATE_CONTENT" not in json.dumps(result)


async def test_action_status_expiry_and_cancel_expired(access):
    from app.api.routes.workbench import action_status, cancel_action

    value = await action_status("session", "action", access)
    assert value["status"] == "pending" and value["expires_at"].endswith("+00:00")
    async with access[1].session_factory() as db:
        row = await db.get(PendingConfirmationRow, "action")
        row.expires_at = utcnow() - timedelta(seconds=1)
        await db.commit()
    assert (await action_status("session", "action", access))["status"] == "expired"
    with pytest.raises(HTTPException) as exc:
        await cancel_action("session", "action", access)
    assert exc.value.status_code == 409


def test_planner_and_tool_summaries_allowlist_nested_untrusted_values():
    from app.observability.workbench import project_state

    step = SimpleNamespace(
        step_id=1,
        tool_name="get_order",
        needs_retrieval=False,
        arguments={
            "order_id": "ORD10001",
            "sku": "SKU-01",
            "user_id": "PRIVATE_USER",
            "nested": {"secret": "PRIVATE_NESTED"},
        },
    )
    tool = SimpleNamespace(
        name="get_order",
        success=True,
        output={
            "status": "shipped",
            "total_cents": 123,
            "items": [{"secret": "PRIVATE_ITEM"}],
            "refunds": [{"secret": "PRIVATE_REFUND"}],
            "events": [{"secret": "PRIVATE_EVENT"}],
            "internal": {"password": "PRIVATE_PASSWORD"},
            "user_id": "PRIVATE_USER",
        },
    )
    value = project_state({"plan": SimpleNamespace(steps=[step]), "tool_results": [tool]}, "M1")
    assert value["planner_steps"][0]["arguments"] == {"order_id": "ORD10001", "sku": "SKU-01"}
    assert value["tools"][0]["result"] == {
        "status": "shipped",
        "total_cents": 123,
        "item_count": 1,
        "refunds_count": 1,
        "tracking_event_count": 1,
    }
    assert "PRIVATE_" not in json.dumps(value)
    tool.output["status"] = "Bearer credential"
    tool.output["total_cents"] = {"secret": "PRIVATE_NUMBER"}
    step.arguments["order_id"] = "Bearer credential"
    value = project_state({"plan": SimpleNamespace(steps=[step]), "tool_results": [tool]}, "M1")
    assert value["planner_steps"][0]["arguments"] == {"sku": "SKU-01"}
    assert "status" not in value["tools"][0]["result"]
    assert "total_cents" not in value["tools"][0]["result"]


async def test_identity_http_missing_and_forged_credentials_denied():
    import hashlib

    import httpx
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    from app.api.routes.identity import router
    from app.core.auth import Authenticator
    from app.core.exceptions import AppError

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.state.authenticator = Authenticator(
        json.dumps(
            {
                "version": 1,
                "credentials": [
                    {
                        "token_sha256": hashlib.sha256(("a" * 43).encode()).hexdigest(),
                        "subject": "alice",
                        "roles": ["user"],
                        "expires_at": "2099-01-01T00:00:00Z",
                    }
                ],
            }
        )
    )

    class Chat:
        async def _enforce_rate_limit(self, subject):
            pass

    app.state.container = SimpleNamespace(chat_service=Chat())

    @app.exception_handler(AppError)
    async def errors(request, exc):
        return JSONResponse({"message": exc.message}, status_code=exc.http_status)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (await client.get("/api/v1/auth/me")).status_code == 401
        assert (
            await client.get("/api/v1/auth/me", headers={"authorization": "Bearer " + "b" * 43})
        ).status_code == 401
        result = await client.get(
            "/api/v1/auth/me", headers={"authorization": "Bearer " + "a" * 43}
        )
        assert result.status_code == 200 and result.json() == {
            "subject": "alice",
            "roles": ["user"],
        }
