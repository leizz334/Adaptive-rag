"""Read-only owner-scoped SQL history; no live execution metadata."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.auth import Principal
from app.repositories.models import Base, MessageRow, SessionRow


@pytest.fixture
async def access():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as db:
        await db.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        db.add_all(
            [
                SessionRow(session_id="own", user_id="alice", summary="PRIVATE"),
                SessionRow(session_id="foreign", user_id="bob"),
            ]
        )
        db.add(MessageRow(session_id="own", role="system", content="SECRET"))
        for i in range(105):
            db.add(
                MessageRow(
                    session_id="own",
                    role="user" if i % 2 == 0 else "assistant",
                    content=f"message {i}",
                )
            )
        await db.commit()
    yield Principal("alice", frozenset({"user"})), SimpleNamespace(session_factory=factory)
    await engine.dispose()


async def test_owned_bounded_projection(access):
    from app.api.routes.workbench import list_sessions, session_messages

    listed = await list_sessions(access)
    assert len(listed["sessions"]) == 1
    assert listed["sessions"][0]["title"] == "message 0"
    assert set(listed["sessions"][0]) == {"session_id", "title", "updated_at"}
    history = await session_messages("own", access)
    assert history["truncated"] is True
    assert len(history["messages"]) == 100
    assert history["messages"][0]["content"] == "message 5"
    assert history["messages"][-1]["content"] == "message 104"
    assert set(history["messages"][0]) == {"id", "role", "content", "created_at"}


@pytest.mark.parametrize("session_id", ["foreign", "missing"])
async def test_opaque_owner_rejection(access, session_id):
    from app.api.routes.workbench import session_messages

    with pytest.raises(HTTPException) as exc:
        await session_messages(session_id, access)
    assert exc.value.status_code == 404
    assert exc.value.detail == "not found"


async def test_list_limit_and_empty_history(access):
    from app.api.routes.workbench import list_sessions, session_messages

    async with access[1].session_factory() as db:
        db.add_all([SessionRow(session_id=f"new-{i:02}", user_id="alice") for i in range(55)])
        await db.commit()
    listed = await list_sessions(access)
    assert len(listed["sessions"]) == 50
    assert all(s["session_id"] != "foreign" for s in listed["sessions"])
    assert await session_messages("new-00", access) == {"messages": [], "truncated": False}


async def test_history_routes_share_verified_rate_limited_dependency():
    from app.api.routes.workbench import router, workbench_access

    paths = {"/sessions", "/sessions/{session_id}/messages"}
    routes = [r for r in router.routes if r.path in paths]
    assert len(routes) == 2
    assert all(any(d.call == workbench_access for d in r.dependant.dependencies) for r in routes)
