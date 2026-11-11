"""Real request-session transaction interruption; only a guarded synthetic sandbox."""

import asyncio
import os
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.request_scope import request_session
from app.repositories.idempotency import IdempotencyRepository
from app.repositories.models import AuditLogRow, OrderRow
from app.repositories.order_repository import OrderRepository
from research.docs.agent_engineering_upgrade.p4_dependency_integration.sandbox import (
    command,
    live_config,
)

pytestmark = pytest.mark.skipif(
    os.environ.get("P4B_RUN_LIVE") != "1", reason="requires explicit owned real PostgreSQL"
)


@pytest.mark.parametrize("interruption", [RuntimeError, asyncio.CancelledError])
async def test_flushed_business_audit_idempotency_roll_back_on_interruption(interruption):
    path, cfg = live_config()
    command(path, "ps")
    engine = create_async_engine(cfg["database_url"])
    factory = async_sessionmaker(engine)
    order_id, trace = "ORD" + uuid.uuid4().hex[:12], "p4e_" + uuid.uuid4().hex
    try:
        async with factory() as session:
            session.add(
                OrderRow(order_id=order_id, user_id="p4e_owner", status="paid", total_cents=4200)
            )
            await session.commit()
        with pytest.raises(interruption):
            async with request_session(factory) as session:
                output = await OrderRepository(session).cancel_order(order_id, trace_id=trace)
                await IdempotencyRepository(session).put(trace, "synthetic_fingerprint", output)
                await session.flush()
                assert (await session.get(OrderRow, order_id)).status == "cancelled"
                raise interruption("controlled interruption after actual SQL flush")
        async with factory() as session:
            assert (await session.get(OrderRow, order_id)).status == "paid"
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(AuditLogRow)
                    .where(AuditLogRow.trace_id == trace)
                )
                == 0
            )
            assert (
                await IdempotencyRepository(session).get_if_matches(trace, "synthetic_fingerprint")
                is None
            )
    finally:
        await engine.dispose()
