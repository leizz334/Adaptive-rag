from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.exceptions import InvalidRequestError
from app.core.time import utcnow
from app.repositories.models import Base
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService
from tests.unit.test_action_confirmation import _action


@pytest.fixture
async def confirmation_factory(tmp_path):
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/confirmation.db")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def test_confirmation_survives_service_replacement_and_binds_identity(confirmation_factory):
    first = ChatService.__new__(ChatService)
    second = ChatService.__new__(ChatService)
    request = ChatRequest(message="取消订单 ORD10003", user_id="u_demo")
    response = ChatResponse(
        answer="请确认", session_id="sess_demo", trace_id="t", pending_action=_action()
    )
    async with confirmation_factory() as db:
        await first._persist_pending(db, request, response)
        await db.commit()
    confirmed = request.model_copy(
        update=dict(session_id="sess_demo", confirm_action_id="act_test")
    )
    async with confirmation_factory() as db:
        assert await second._load_confirmation(db, confirmed, "sess_demo") == _action()
        with pytest.raises(InvalidRequestError):
            await second._load_confirmation(
                db, confirmed.model_copy(update={"user_id": "other"}), "sess_demo"
            )
        with pytest.raises(InvalidRequestError):
            await second._load_confirmation(db, confirmed, "other_session")
        with pytest.raises(InvalidRequestError):
            await second._load_confirmation(
                db, confirmed.model_copy(update={"confirm_action_id": "forged"}), "sess_demo"
            )
    from app.repositories.models import PendingConfirmationRow

    async with confirmation_factory() as db:
        row = await db.scalar(select(PendingConfirmationRow))
        row.expires_at = utcnow() - timedelta(seconds=1)
        await db.commit()
    async with confirmation_factory() as db:
        with pytest.raises(InvalidRequestError):
            await second._load_confirmation(db, confirmed, "sess_demo")


async def test_uncommitted_proposal_cannot_be_confirmed(confirmation_factory):
    service = ChatService.__new__(ChatService)
    request = ChatRequest(message="取消订单 ORD10003", user_id="u_demo")
    response = ChatResponse(
        answer="请确认", session_id="sess_demo", trace_id="t", pending_action=_action()
    )
    async with confirmation_factory() as db:
        await service._persist_pending(db, request, response)
        await db.rollback()
    confirmed = request.model_copy(
        update=dict(session_id="sess_demo", confirm_action_id="act_test")
    )
    async with confirmation_factory() as db:
        with pytest.raises(InvalidRequestError):
            await service._load_confirmation(db, confirmed, "sess_demo")
