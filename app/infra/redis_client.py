"""Redis connection helper with graceful degradation."""

from __future__ import annotations

import logging

from app.config.settings import Settings

logger = logging.getLogger(__name__)


async def connect_redis(settings: Settings):
    """Return an async Redis client or None.

    Redis is used for rate limiting, short-TTL retrieval cache, and optional
    distributed idempotency. Sensitive API admission fails closed on outages.
    Keep the configured client on failed startup ping so it can reconnect later.
    """
    if not settings.redis_configured:
        return None
    client = None
    try:
        from redis.asyncio import Redis

        client = Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=1.0,
            socket_timeout=1.0,
            decode_responses=True,
        )
        await client.ping()
        return client
    except Exception:
        logger.warning("redis_unavailable_sensitive_admission_closed")
        return client
