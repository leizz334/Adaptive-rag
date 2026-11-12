import json
import stat
from datetime import UTC, datetime, timedelta

import pytest


def test_bootstrap_persists_private_random_credentials(tmp_path):
    from app.demo.docker import bootstrap

    secret, state = tmp_path / "db", tmp_path / "state"
    bootstrap(secret, state, owner_uid=None)
    first = (state / "development_credentials.json").read_bytes()
    bootstrap(secret, state, owner_uid=None)
    assert first == (state / "development_credentials.json").read_bytes()
    row = json.loads(first)
    assert set(row["tokens"]) == {"a", "b"}
    assert row["tokens"]["a"] != row["tokens"]["b"]
    assert datetime.fromisoformat(row["expires_at"]) > datetime.now(UTC) + timedelta(days=29)
    assert stat.S_IMODE(state.stat().st_mode) == 0o700
    assert stat.S_IMODE((state / "development_credentials.json").stat().st_mode) == 0o600
    assert stat.S_IMODE(secret.stat().st_mode) == 0o755
    assert stat.S_IMODE((secret / "postgres_password").stat().st_mode) == 0o444


def test_malformed_state_is_never_replaced(tmp_path):
    from app.demo.docker import bootstrap

    secret, state = tmp_path / "db", tmp_path / "state"
    bootstrap(secret, state, owner_uid=None)
    target = state / "development_credentials.json"
    target.write_text("{broken")
    with pytest.raises(ValueError):
        bootstrap(secret, state, owner_uid=None)
    assert target.read_text() == "{broken"


def test_settings_ignore_hostile_environment(tmp_path, monkeypatch):
    from app.demo.docker import bootstrap, runtime_settings

    secret, state = tmp_path / "db", tmp_path / "state"
    bootstrap(secret, state, owner_uid=None)
    for key in ["DEEPSEEK_API_KEY", "EMBEDDING_API_KEY", "DATABASE_URL", "MCP_REMOTE_URL"]:
        monkeypatch.setenv(key, "hostile")
    monkeypatch.setenv("AUTH_MODE", "legacy_test")
    cfg = runtime_settings(secret, state)
    assert cfg.auth_mode == "required"
    assert cfg.knowledge_mode == "private"
    assert not cfg.llm_configured and not cfg.embedding_configured
    assert not cfg.local_embedding_configured and not cfg.cross_encoder_configured
    assert not cfg.mcp_enabled
    assert "@postgres:5432/adaptive_showcase" in cfg.database_url
    assert cfg.redis_url == "redis://redis:6379/13"


def test_expired_credentials_fail_closed(tmp_path):
    from app.demo.docker import bootstrap

    secret, state = tmp_path / "db", tmp_path / "state"
    bootstrap(secret, state, owner_uid=None)
    path = state / "development_credentials.json"
    row = json.loads(path.read_text())
    row["expires_at"] = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    path.write_text(json.dumps(row))
    before = path.read_bytes()
    with pytest.raises(ValueError):
        bootstrap(secret, state, owner_uid=None)
    assert path.read_bytes() == before


def test_partial_bootstrap_retains_existing_password(tmp_path):
    from app.demo.docker import bootstrap

    secret, state = tmp_path / "db", tmp_path / "state"
    bootstrap(secret, state, owner_uid=None)
    before = (secret / "postgres_password").read_bytes()
    (state / "development_credentials.json").unlink()
    bootstrap(secret, state, owner_uid=None)
    assert (secret / "postgres_password").read_bytes() == before


def test_network_allowlist_matches_exact_address_and_port():
    from app.demo.docker import address_allowed

    allowed = {("172.20.0.2", 5432)}
    assert address_allowed(("172.20.0.2", 5432), allowed)
    assert address_allowed(("127.0.0.1", 8000), allowed)
    assert not address_allowed(("172.20.0.2", 443), allowed)
    assert not address_allowed(("8.8.8.8", 443), allowed)


@pytest.mark.asyncio
async def test_seed_retains_cancelled_and_rejects_item_collision(tmp_path):
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.demo.fixtures import seed
    from app.repositories.models import Base, OrderItemRow, OrderRow

    cfg = {"database_url": f"sqlite+aiosqlite:///{tmp_path}/seed.db"}
    engine = create_async_engine(cfg["database_url"])
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed(cfg)
    async with async_sessionmaker(engine)() as db:
        order = await db.get(OrderRow, "ORD95101")
        order.status = "cancelled"
        await db.commit()
    await seed(cfg)
    async with async_sessionmaker(engine)() as db:
        assert (await db.get(OrderRow, "ORD95101")).status == "cancelled"
        assert len((await db.scalars(select(OrderItemRow))).all()) == 8
        item = (await db.scalars(select(OrderItemRow))).first()
        item.quantity = 9
        await db.commit()
    with pytest.raises(ValueError, match="collision"):
        await seed(cfg)
    await engine.dispose()


@pytest.mark.asyncio
async def test_original_seed_signature_delegates(monkeypatch):
    from app.demo import fixtures
    from research.docs.agent_engineering_upgrade.s1_web_upgrade import demo

    seen = []

    async def seed(cfg):
        seen.append(cfg)

    monkeypatch.setattr(fixtures, "seed", seed)
    await demo.seed({"sentinel": 1})
    assert seen == [{"sentinel": 1}]


def test_credentials_without_password_fail_closed(tmp_path):
    from app.demo.docker import bootstrap

    secret, state = tmp_path / "db", tmp_path / "state"
    bootstrap(secret, state, owner_uid=None)
    (secret / "postgres_password").unlink()
    with pytest.raises(ValueError):
        bootstrap(secret, state, owner_uid=None)
    assert not (secret / "postgres_password").exists()
