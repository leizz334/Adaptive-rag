"""B2 real Docker-service acceptance. Windows skips are BLOCKED, never PASS."""

import asyncio
import os
import platform
import subprocess
import sys
import uuid

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.exceptions import RetrievalError
from app.infra.rate_limit import RedisRateLimiter
from app.main import create_app  # noqa: F401 -- bootstrap the existing application import graph
from app.repositories.idempotency import IdempotencyRepository
from app.repositories.models import Base
from app.retrieval.cache import RedisRetrievalCache, cache_key
from app.retrieval.vector import QdrantVectorStore, VectorRecord
from app.schemas.retrieval import RetrievedChunk
from research.docs.agent_engineering_upgrade.p4_dependency_integration.sandbox import (
    command,
    live_config,
)

pytestmark = pytest.mark.skipif(
    platform.system() != "Linux" or os.environ.get("P4B_RUN_LIVE") != "1",
    reason="BLOCKED_WAITING_UBUNTU_REAL_DOCKER: explicit owned manifest required",
)


@pytest.fixture(scope="module")
def config():
    path, cfg = live_config()
    command(path, "ps")  # Ownership check before any database mutation.
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "research.docs.agent_engineering_upgrade.p4_dependency_integration.migrate",
            "--roundtrip",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, "Migration roundtrip failed; inspect local stderr safely"
    return path, cfg


@pytest.fixture
async def engine(config):
    eng = create_async_engine(config[1]["database_url"], pool_pre_ping=True)
    async with eng.begin() as connection:
        assert connection.dialect.name == "postgresql"
        await connection.execute(
            text("CREATE TABLE IF NOT EXISTS p4b_probe (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        )
    yield eng
    await eng.dispose()


@pytest.fixture
async def redis(config):
    from redis.asyncio import Redis

    client = Redis.from_url(config[1]["redis_url"], decode_responses=True)
    assert await client.ping()
    yield client
    await client.aclose()


@pytest.fixture
def vector(config):
    store = QdrantVectorStore(config[1]["qdrant_url"], config[1]["collection"] + "_probe", 2)
    assert store.ping(), "Qdrant unavailable; no memory fallback allowed"
    yield store
    if store._client is not None:
        store._client.close()


def chunk(identifier="p4b_policy"):
    return RetrievedChunk(
        chunk_id=identifier,
        document_id="p4b_doc",
        title="合成政策",
        content="合成政策证据",
        score=1,
        policy_version="p4b_v1",
    )


async def test_postgresql_migrations_match_metadata(engine):
    async with engine.connect() as connection:
        names = await connection.run_sync(lambda c: inspect(c).get_table_names())
        assert set(Base.metadata.tables) <= set(names)
        for table in Base.metadata.tables.values():
            columns = await connection.run_sync(lambda c, t=table: inspect(c).get_columns(t.name))
            assert {c.name for c in table.columns} == {c["name"] for c in columns}
        assert await connection.scalar(text("SELECT version_num FROM alembic_version"))


async def test_postgresql_commit_visible_from_independent_connection(engine):
    key = uuid.uuid4().hex
    async with engine.begin() as connection:
        await connection.execute(text("INSERT INTO p4b_probe VALUES (:k,'committed')"), {"k": key})
    async with engine.connect() as other:
        assert (
            await other.scalar(text("SELECT value FROM p4b_probe WHERE key=:k"), {"k": key})
            == "committed"
        )


async def test_postgresql_transaction_rollback(engine):
    key = uuid.uuid4().hex
    with pytest.raises(RuntimeError, match="intentional rollback"):
        async with engine.begin() as connection:
            await connection.execute(
                text("INSERT INTO p4b_probe VALUES (:k,'not_committed')"), {"k": key}
            )
            raise RuntimeError("intentional rollback")
    async with engine.connect() as connection:
        assert (
            await connection.scalar(text("SELECT COUNT(*) FROM p4b_probe WHERE key=:k"), {"k": key})
            == 0
        )


async def test_postgresql_concurrent_idempotency(engine):
    """Expected contract; race failures must be retained/fixed in B2, not xfailed."""
    factory = async_sessionmaker(engine)
    key = "p4b_" + uuid.uuid4().hex
    barrier = asyncio.Event()
    arrived = 0

    async def writer():
        nonlocal arrived
        async with factory() as session:
            repository = IdempotencyRepository(session)
            arrived += 1
            if arrived == 2:
                barrier.set()
            await asyncio.wait_for(barrier.wait(), 10)
            await repository.put(key, "same_fingerprint", {"synthetic": True})
            await session.commit()

    results = await asyncio.gather(writer(), writer(), return_exceptions=True)
    assert not [
        r for r in results if isinstance(r, BaseException)
    ], "Concurrent identical idempotency put failed"
    async with factory() as session:
        assert await IdempotencyRepository(session).get_if_matches(key, "same_fingerprint") == {
            "synthetic": True
        }


async def test_redis_cache_ttl_and_order_bypass(redis):
    cache = RedisRetrievalCache(redis, ttl_seconds=1)
    query = "p4b_policy_" + uuid.uuid4().hex
    await cache.set(query, 1, [chunk()])
    assert (await cache.get(query, 1))[0].content == chunk().content
    assert 0 <= await redis.ttl(cache_key(query, 1)) <= 1
    await cache.set("订单 ORD-P4B 查询", 1, [chunk()])
    assert await cache.get("订单 ORD-P4B 查询", 1) is None
    await asyncio.sleep(1.2)
    assert await cache.get(query, 1) is None


async def test_redis_rate_limit_and_expiry(redis):
    key = "p4b_" + uuid.uuid4().hex
    limiter = RedisRateLimiter(redis, limit=2, window_seconds=1)
    assert await limiter.allow(key)
    assert await limiter.allow(key)
    assert not await limiter.allow(key)
    await asyncio.sleep(1.2)
    assert await limiter.allow(key)


def test_qdrant_adapter_retrieval_and_upsert(vector):
    vector.upsert(
        [VectorRecord(chunk("p4b_a"), [1.0, 0.0]), VectorRecord(chunk("p4b_b"), [0.0, 1.0])]
    )
    hits = vector.search([1.0, 0.0], top_k=1)
    assert hits[0].chunk_id == "p4b_a"
    vector.upsert([VectorRecord(chunk("p4b_a"), [1.0, 0.0])])
    assert vector._client.count(vector._collection, exact=True).count == 2


def test_qdrant_filter_and_payload_index(vector):
    """Native Qdrant filter contract, distinct from unfiltered public-corpus app adapter."""
    from qdrant_client import models

    vector.upsert([VectorRecord(chunk("p4b_a"), [1.0, 0.0])])
    vector._client.create_payload_index(
        vector._collection,
        "policy_version",
        field_schema=models.PayloadSchemaType.KEYWORD,
        wait=True,
    )
    hits = vector._client.search(
        vector._collection,
        query_vector=[1.0, 0.0],
        query_filter=models.Filter(
            must=[
                models.FieldCondition(key="policy_version", match=models.MatchValue(value="p4b_v1"))
            ]
        ),
        limit=5,
    )
    assert hits and all(h.payload["policy_version"] == "p4b_v1" for h in hits)
    excluded = vector._client.search(
        vector._collection,
        query_vector=[1.0, 0.0],
        query_filter=models.Filter(
            must=[
                models.FieldCondition(key="policy_version", match=models.MatchValue(value="absent"))
            ]
        ),
        limit=5,
    )
    assert excluded == []


def test_qdrant_dimension_error_is_classified(vector):
    vector.ensure_collection()
    with pytest.raises(RetrievalError):
        vector.search([1.0, 0.0, 0.0], top_k=1)


async def wait_for(probe):
    for _ in range(60):
        try:
            value = probe()
            if hasattr(value, "__await__"):
                value = await value
            if value:
                return
        except Exception:
            pass
        await asyncio.sleep(1)
    pytest.fail("Owned dependency did not recover in 60s")


async def test_postgresql_restart_persistence(config, engine):
    path, _ = config
    key = uuid.uuid4().hex
    async with engine.begin() as c:
        await c.execute(text("INSERT INTO p4b_probe VALUES (:k,'survives')"), {"k": key})
    command(path, "restart", "postgres")

    async def probe():
        async with engine.connect() as c:
            return (
                await c.scalar(text("SELECT value FROM p4b_probe WHERE key=:k"), {"k": key})
                == "survives"
            )

    await wait_for(probe)


async def test_redis_outage_fail_open_and_recovery(config, redis):
    path, _ = config
    key = "p4b_" + uuid.uuid4().hex
    await redis.set(key, "survives")
    command(path, "stop", "redis")
    try:
        assert await RedisRetrievalCache(redis, ttl_seconds=1).get("p4b_no_service", 1) is None
        assert await RedisRateLimiter(redis, limit=1).allow(
            key
        )  # Existing documented fail-open, not auth.
    finally:
        command(path, "start", "redis")
    await wait_for(redis.ping)
    assert await redis.get(key) == "survives"


async def test_qdrant_outage_and_persistence(config, vector):
    path, _ = config
    vector.upsert([VectorRecord(chunk("p4b_a"), [1.0, 0.0])])
    command(path, "stop", "qdrant")
    try:
        with pytest.raises(RetrievalError):
            vector.search([1.0, 0.0], top_k=1)
    finally:
        command(path, "start", "qdrant")
    await wait_for(vector.ping)
    assert vector.search([1.0, 0.0], top_k=1)[0].chunk_id == "p4b_a"


async def test_postgresql_idempotency_conflict_preserves_first_response(engine):
    from app.core.exceptions import AppError

    factory = async_sessionmaker(engine)
    key = "p4b_" + uuid.uuid4().hex
    async with factory() as session:
        repo = IdempotencyRepository(session)
        await repo.put(key, "first", {"value": "original"})
        await session.commit()
    async with factory() as session:
        repo = IdempotencyRepository(session)
        await repo.put(key, "first", {"value": "replacement"})
        assert await repo.get_if_matches(key, "first") == {"value": "original"}
        with pytest.raises(AppError) as error:
            await repo.put(key, "different", {"value": "bad"})
        assert error.value.http_status == 409
        await session.rollback()
    async with factory() as session:
        assert await IdempotencyRepository(session).get_if_matches(key, "first") == {
            "value": "original"
        }
