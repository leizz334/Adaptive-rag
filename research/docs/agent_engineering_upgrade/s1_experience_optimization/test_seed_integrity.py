"""Only the owned synthetic fixture may be used for paid task comparisons."""

import os

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.repositories.models import OrderRow
from research.docs.agent_engineering_upgrade.p4_dependency_integration.sandbox import (
    command,
    live_config,
)
from research.docs.agent_engineering_upgrade.s1_experience_optimization.common import HERE, read
from research.docs.agent_engineering_upgrade.s1_experience_optimization.meter import SafetyStop
from research.docs.agent_engineering_upgrade.s1_experience_optimization.run import seed

pytestmark = pytest.mark.skipif(
    os.environ.get("P4B_RUN_LIVE") != "1", reason="explicit owned real database only"
)


async def test_existing_fixture_mismatch_denies_before_paid_dispatch():
    manifest, cfg = live_config()
    command(manifest, "ps")
    await seed(cfg)
    identifier = read(HERE / "tasks.json")["tasks"][0]["orders"][0]["order_id"]
    engine = create_async_engine(cfg["database_url"])
    factory = async_sessionmaker(engine)
    try:
        async with factory() as db:
            row = await db.get(OrderRow, identifier)
            original = row.user_id
            row.user_id = "synthetic_wrong_owner"
            await db.commit()
        try:
            with pytest.raises(SafetyStop):
                await seed(cfg)
        finally:
            async with factory() as db:
                row = await db.get(OrderRow, identifier)
                row.user_id = original
                await db.commit()
    finally:
        await engine.dispose()
