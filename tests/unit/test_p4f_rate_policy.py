"""No fallback may admit a sensitive operation when global quota is unknown."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from app.infra.rate_limit import RedisRateLimiter


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [ConnectionError, TimeoutError])
async def test_sensitive_quota_errors_are_explicit_denial(failure):
    redis = AsyncMock()
    redis.eval.side_effect = failure("synthetic outage")
    limiter = RedisRateLimiter(redis, limit=2, fail_closed=True, timeout_seconds=0.02)
    with pytest.raises(Exception) as exc:
        await limiter.allow("synthetic_subject")
    assert getattr(exc.value, "http_status", None) == 503


@pytest.mark.asyncio
async def test_sensitive_quota_wait_is_bounded():
    async def blocked(*args):
        await asyncio.sleep(2)

    redis = AsyncMock()
    redis.eval.side_effect = blocked
    limiter = RedisRateLimiter(redis, limit=2, fail_closed=True, timeout_seconds=0.01)
    with pytest.raises(Exception) as exc:
        await limiter.allow("synthetic_subject")
    assert getattr(exc.value, "http_status", None) == 503


@pytest.mark.asyncio
async def test_remote_embedding_credentials_cannot_use_local_quota(monkeypatch):
    from pydantic import SecretStr

    from app.config.settings import Settings
    from app.main import create_app  # noqa: F401
    from app.services import container as module

    settings = Settings(
        _env_file=None,
        app_env="testing",
        redis_url="",
        deepseek_api_key=SecretStr(""),
        embedding_api_key=SecretStr("synthetic_embedding_key"),
        embedding_base_url="https://invalid.example",
    )
    monkeypatch.setattr(
        module, "build_infrastructure", AsyncMock(return_value=(object(), object(), None))
    )
    monkeypatch.setattr(module, "build_retrieval", AsyncMock(return_value=(object(), None, None)))
    runtime = await module.build_container(settings)
    with pytest.raises(Exception) as exc:
        await runtime.chat_service._enforce_rate_limit("synthetic_subject")
    assert getattr(exc.value, "http_status", None) == 503


@pytest.mark.asyncio
async def test_remote_embedding_bootstrap_requires_redis_admission(monkeypatch):
    from pydantic import SecretStr

    from app.config.settings import Settings
    from app.main import create_app  # noqa: F401
    from app.services import container as module

    settings = Settings(
        _env_file=None,
        app_env="testing",
        embedding_api_key=SecretStr("synthetic_embedding_key"),
        embedding_base_url="https://invalid.example",
    )

    def forbidden(_):
        raise AssertionError("must not initialize paid embedding before admission")

    monkeypatch.setattr(module, "build_embedding_provider", forbidden)
    with pytest.raises(Exception) as exc:
        await module.build_retrieval(settings, None)
    assert getattr(exc.value, "http_status", None) == 503
