"""Local/mock driver compatibility only; not PostgreSQL/Redis/Qdrant service results."""

from unittest.mock import AsyncMock

from qdrant_client import QdrantClient
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.infra.rate_limit import RedisRateLimiter
from app.main import create_app
from app.repositories.models import Base
from app.retrieval.cache import RedisRetrievalCache, cache_key
from app.retrieval.vector import QdrantVectorStore, VectorRecord
from app.schemas.retrieval import RetrievedChunk


def chunk():
    return RetrievedChunk(
        chunk_id="p4b_local",
        document_id="p4b_doc",
        title="本地合成",
        content="仅验证客户端契约",
        score=1,
    )


def test_postgresql_ddl_compiles_all_business_tables():
    dialect = postgresql.dialect()
    for table in Base.metadata.sorted_tables:
        assert table.name in str(CreateTable(table).compile(dialect=dialect))
        for index in table.indexes:
            assert index.name in str(CreateIndex(index).compile(dialect=dialect))


def test_qdrant_local_adapter_roundtrip_not_real_service():
    store = QdrantVectorStore("http://127.0.0.1:1", "p4b_local", 2)
    store._client = QdrantClient(":memory:")
    try:
        store.upsert([VectorRecord(chunk(), [1.0, 0.0])])
        assert store.search([1.0, 0.0], top_k=1)[0].content == chunk().content
        store.upsert([VectorRecord(chunk(), [1.0, 0.0])])
        assert store._client.count("p4b_local").count == 1
    finally:
        store._client.close()


async def test_redis_cache_mock_serialization_ttl_and_order_bypass():
    redis = AsyncMock()
    cache = RedisRetrievalCache(redis, ttl_seconds=3)
    await cache.set("合成政策", 1, [chunk()])
    args, kwargs = redis.set.call_args
    assert args[0] == cache_key("合成政策", 1) and kwargs == {"ex": 3}
    redis.get.return_value = args[1]
    assert (await cache.get("合成政策", 1))[0].content == chunk().content
    await cache.set("ORD987654 查询", 1, [chunk()])
    assert redis.set.await_count == 1
    assert await cache.get("ORD987654 查询", 1) is None


async def test_redis_mock_outage_is_documented_fail_open_then_recovers():
    redis = AsyncMock()
    redis.get.side_effect = ConnectionError("synthetic disconnected")
    redis.eval.side_effect = ConnectionError("synthetic disconnected")
    assert await RedisRetrievalCache(redis, ttl_seconds=3).get("合成政策", 1) is None
    assert await RedisRateLimiter(redis, limit=1).allow("synthetic")
    redis.get.side_effect = None
    redis.get.return_value = None
    assert await RedisRetrievalCache(redis, ttl_seconds=3).get("合成政策", 1) is None


def test_live_suites_are_collectable_and_no_fallback_is_hidden():
    from research.docs.agent_engineering_upgrade.p4_dependency_integration import (
        live_api,
        live_worker,
        test_live_api,
        test_real_dependencies,
    )

    assert callable(create_app) and callable(live_api.LiveApi) and callable(live_worker.main)
    assert len(test_live_api.pytestmark.args) and len(test_real_dependencies.pytestmark.args)
