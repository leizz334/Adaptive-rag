"""Per-user rate limiting.

Sensitive runtime entrypoints require atomic Redis admission and fail closed.
Explicit fail-open mode is available only to ordinary-read callers, never chat/KB.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class RateLimiter:
    async def allow(self, key: str) -> bool:
        raise NotImplementedError


class InMemoryRateLimiter(RateLimiter):
    def __init__(self, *, limit: int, window_seconds: int = 60) -> None:
        self._limit = limit
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def allow(self, key: str) -> bool:
        now = time.monotonic()
        async with self._lock:
            bucket = self._hits[key]
            cutoff = now - self._window
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self._limit:
                return False
            bucket.append(now)
            return True


class RedisRateLimiter(RateLimiter):
    """Atomic server-clock sliding window; unknown admission denies sensitive work."""

    SCRIPT = """
    local clock = redis.call('TIME')
    local now = tonumber(clock[1]) * 1000000 + tonumber(clock[2])
    local window = tonumber(ARGV[1]) * 1000000
    redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - window)
    if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[2]) then return 0 end
    redis.call('ZADD', KEYS[1], now, ARGV[3])
    redis.call('EXPIRE', KEYS[1], tonumber(ARGV[1]))
    return 1
    """

    def __init__(
        self,
        redis,
        *,
        limit: int,
        window_seconds: int = 60,
        fail_closed: bool = False,
        timeout_seconds: float = 0.25,
    ) -> None:
        if limit < 1 or window_seconds < 1 or timeout_seconds <= 0:
            raise ValueError("positive rate admission bounds required")
        self._redis, self._limit, self._window = redis, limit, window_seconds
        self._fail_closed, self._timeout = fail_closed, timeout_seconds

    async def allow(self, key: str) -> bool:
        from app.core.exceptions import RateLimitUnavailableError

        try:
            if self._redis is None:
                raise ConnectionError("distributed quota unavailable")
            namespace = "closed" if self._fail_closed else "ordinary_read"
            result = await asyncio.wait_for(
                self._redis.eval(
                    self.SCRIPT,
                    1,
                    f"rl:{namespace}:v1:{key}",
                    self._window,
                    self._limit,
                    uuid.uuid4().hex,
                ),
                self._timeout,
            )
            if type(result) is not int or result not in {0, 1}:
                raise ValueError("invalid quota response")
            return result == 1
        except Exception as exc:
            if self._fail_closed:
                logger.warning("rate_limiter_redis_failed_closed")
                raise RateLimitUnavailableError() from exc
            logger.warning("ordinary_read_rate_limiter_failed_open")
            return True
