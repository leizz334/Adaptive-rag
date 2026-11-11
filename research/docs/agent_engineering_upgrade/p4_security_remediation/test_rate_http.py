"""Actual Redis outage, timeout and two-process quota attacks, no paid provider."""

import asyncio
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from research.docs.agent_engineering_upgrade.p4_dependency_integration.live_api import snapshot
from research.docs.agent_engineering_upgrade.p4_dependency_integration.sandbox import command
from research.docs.agent_engineering_upgrade.p4_dependency_integration.worker import TOKENS
from research.docs.agent_engineering_upgrade.p4_security_remediation.runtime import Runtime, save

pytestmark = pytest.mark.skipif(
    os.environ.get("P4B_RUN_LIVE") != "1", reason="owned real Redis required"
)


def wait_redis(api):
    async def probe():
        from redis.asyncio import Redis

        client = Redis.from_url(api.cfg["redis_url"])
        try:
            for _ in range(100):
                try:
                    if await client.ping():
                        return
                except Exception:
                    pass
                await asyncio.sleep(0.1)
            raise TimeoutError("owned Redis recovery")
        finally:
            await client.aclose()

    asyncio.run(probe())


def test_redis_outage_denies_sensitive_operations_before_writes():
    api = Runtime()
    try:
        api.start()
        before = asyncio.run(snapshot(api.cfg))
        command(api.manifest, "stop", "redis")
        try:
            api.request(
                "POST",
                "/knowledge/documents/redis_outage",
                {"title": "synthetic", "content": "must not commit"},
                expected=503,
            )
            api.request("POST", "/chat", {"message": "请取消订单 ORD94071"}, expected=503, worker=1)
            stream = api.request(
                "POST", "/chat/stream", {"message": "退货政策"}, expected=200, worker=1
            )
            events = [
                json.loads(line[5:])
                for line in stream.text.splitlines()
                if line.startswith("data:")
            ]
            assert any(
                e["event"] == "error" and e["error_code"] == "RATE_LIMIT_UNAVAILABLE"
                for e in events
            )
            assert not any(e["event"] == "answer" for e in events)
            assert api.request("GET", "/health", expected=200).json()["status"] == "ok"
            api.request("POST", "/chat", {"message": "你好"}, subject=None, expected=401)
        finally:
            after = asyncio.run(snapshot(api.cfg))
            save(api.directory / "redis_outage_sql.json", {"before": before, "after": after})
            command(api.manifest, "start", "redis")
            wait_redis(api)
        assert before == after
        api.request(
            "POST",
            "/knowledge/documents/recovered",
            {"title": "synthetic", "content": "恢复后可写合成文档"},
            expected=200,
            worker=1,
        )
    finally:
        api.stop()


def test_real_redis_timeout_denies_and_recovers():
    api = Runtime(count=1)
    try:
        api.start()
        before = asyncio.run(snapshot(api.cfg))

        async def pause():
            from redis.asyncio import Redis

            client = Redis.from_url(api.cfg["redis_url"])
            try:
                await client.execute_command("CLIENT", "PAUSE", 1200, "ALL")
            finally:
                await client.aclose()

        asyncio.run(pause())
        started = time.monotonic()
        row = api.request(
            "POST",
            "/knowledge/documents/timeout",
            {"title": "synthetic", "content": "must not write"},
            expected=503,
        )
        assert row.json()["error_code"] == "RATE_LIMIT_UNAVAILABLE"
        assert time.monotonic() - started < 2
        wait_redis(api)
        assert before == asyncio.run(snapshot(api.cfg))
        api.request(
            "POST",
            "/knowledge/documents/recovered_timeout",
            {"title": "synthetic", "content": "恢复后独立新操作"},
            expected=200,
        )
    finally:
        api.stop()


def test_two_processes_share_one_atomic_quota():
    api = Runtime(limit=4)
    try:
        api.start()

        def one(index):
            with httpx.Client(timeout=15, trust_env=False) as client:
                r = client.post(
                    api.processes[index % 2]["url"] + "/api/v1/chat",
                    json={"message": "你好"},
                    headers={"authorization": "Bearer " + TOKENS["user"]},
                )
                return {"status": r.status_code, "body": r.json(), "worker": index % 2}

        with ThreadPoolExecutor(max_workers=6) as pool:
            rows = list(pool.map(one, range(12)))
        save(api.directory / "quota_competition.json", {"limit": 4, "requests": 12, "rows": rows})
        assert sum(r["status"] == 200 for r in rows) == 4
        assert sum(r["status"] == 429 for r in rows) == 8
        api.request("GET", "/health", expected=200)
        api.request("GET", "/ready", expected=200)
    finally:
        api.stop()


def test_startup_outage_keeps_distributed_client_and_recovers():
    api = Runtime(limit=2)
    try:
        command(api.manifest, "stop", "redis")
        try:
            api.start()
            api.request("POST", "/knowledge/search", {"query": "policy"}, expected=503)
            api.request("GET", "/health", expected=200, worker=1)
        finally:
            command(api.manifest, "start", "redis")
            wait_redis(api)
        for worker in [0, 1]:
            api.request("POST", "/chat", {"message": "你好"}, expected=200, worker=worker)
        api.request("POST", "/chat", {"message": "你好"}, expected=429)
    finally:
        api.stop()
