"""B3 real PostgreSQL/Redis/Qdrant + HTTP/SSE. Controlled LLM, not DeepSeek."""

import asyncio
import json
import os
import platform
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.repositories.models import OrderRow
from app.services.seed import seed_demo_data
from research.docs.agent_engineering_upgrade.p4_api_e2e.test_real_http import (
    calls,
    graph_observed,
    has_tool,
)
from research.docs.agent_engineering_upgrade.p4_dependency_integration.live_api import (
    LiveApi,
    assert_confirmation_effects,
    snapshot,
)
from research.docs.agent_engineering_upgrade.p4_dependency_integration.manage import save

pytestmark = pytest.mark.skipif(
    platform.system() != "Linux" or os.environ.get("P4B_RUN_LIVE") != "1",
    reason="BLOCKED_WAITING_UBUNTU_REAL_DEPENDENCIES_HTTP",
)


@pytest.fixture(scope="module")
def api():
    run = LiveApi(
        os.environ.get("P4B_API_RUN_ID") or datetime.now(UTC).strftime("ubuntu_api_%Y%m%d_%H%M%S")
    )

    async def seed():
        engine = create_async_engine(run.cfg["database_url"])
        try:
            async with async_sessionmaker(engine)() as session:
                await seed_demo_data(session)
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(seed())
    try:
        run.start(2)
        yield run
    finally:
        run.stop()


def chat(api, case, text, **fields):
    row = api.request(case, dict(message=text, **fields), expected=200)
    assert row["body"]["answer"]
    graph_observed(row)
    assert any(
        m["content"] == row["body"]["answer"] and m["session_id"] == row["body"]["session_id"]
        for m in row["database_after"]["messages"]
    )
    return row


def readonly(row):
    tables = (
        "orders",
        "order_items",
        "products",
        "refunds",
        "returns",
        "audit_logs",
        "idempotency_keys",
    )
    # SQL row order is deliberately not used as business equality.
    for table in tables:
        assert sorted(map(str, row["database_before"][table])) == sorted(
            map(str, row["database_after"][table])
        )


@pytest.mark.parametrize("path", ["health", "ready", "capabilities"])
def test_actual_backend_health(api, path):
    row = api.request("health_" + path, method="GET", path="/api/v1/" + path, expected=200)
    readonly(row)


def test_authenticated_owner_and_session_isolation(api):
    first = chat(api, "own_order", "查询 ORD10001 的状态和金额")
    assert has_tool(first, "get_order", order_id="ORD10001")
    readonly(first)
    denied = api.request(
        "other_session",
        dict(message="继续", session_id=first["body"]["session_id"]),
        identity="other",
        worker=1,
        expected=400,
    )
    assert denied["body"]["error_code"] == "INVALID_REQUEST"
    assert denied["body"]["message"] == "session not found"
    readonly(denied)
    assert not calls(denied)
    spoof = api.request(
        "spoof", dict(message="查询 ORD10001", user_id="u_demo"), identity="other", expected=403
    )
    assert not calls(spoof)
    other = api.request(
        "other_owner", dict(message="查询 ORD10001"), identity="other", expected=200
    )
    readonly(other)
    assert "299.00" not in other["body"]["answer"]
    api.request("unauthenticated", dict(message="你好"), identity=None, expected=401)


def test_shared_postgresql_memory_across_api_processes(api):
    first = chat(api, "memory_first", "查询 ORD10001")
    row = api.request(
        "memory_second_worker",
        dict(message="它的总金额是多少", session_id=first["body"]["session_id"]),
        worker=1,
        expected=200,
    )
    assert has_tool(row, "get_order", order_id="ORD10001")
    assert "299.00" in row["body"]["answer"]
    readonly(row)


@pytest.mark.parametrize(
    "case,message,tool",
    [
        ("rag", "七天无理由退货政策是什么", None),
        ("compound", "查询 ORD10001 的物流和总金额", "track_shipment"),
        ("refund", "查询 ORD10002 的退款状态", "get_refund_status"),
        ("product", "查询 SKU-HEADSET 的库存", "check_inventory"),
    ],
)
def test_rag_and_business_workflows(api, case, message, tool):
    async def cache_state(clear=False):
        from redis.asyncio import Redis

        client = Redis.from_url(api.cfg["redis_url"], decode_responses=True)
        try:
            keys = [key async for key in client.scan_iter(match="ret:*")]
            if clear and keys:
                await client.delete(*keys)  # Dedicated owned DB13 and public-policy namespace only.
                keys = []
            return {key: await client.ttl(key) for key in keys}
        finally:
            await client.aclose()

    if case == "rag":
        asyncio.run(cache_state(clear=True))
    row = chat(api, case, message)
    readonly(row)
    if tool:
        assert has_tool(row, tool)
        if case == "product":
            assert "42" in row["body"]["answer"]
    else:
        assert row["body"]["citations"]
        spans = graph_observed(row)
        cache = asyncio.run(cache_state())
        proof = dict(
            vector_spans=[s for s in spans if s["name"] == "retrieval.vector"],
            redis_cache_ttls=cache,
        )
        save(api.directory / "rag_backend_participation.json", proof)
        assert any(
            s["status"] == "ok" for s in proof["vector_spans"]
        ), "BM25-only degradation cannot count as real vector retrieval"
        assert cache and any(
            ttl > 0 for ttl in cache.values()
        ), "Memory cache/no Redis write cannot count as Redis integration"
    if case == "compound":
        assert "299.00" in row["body"]["answer"] and has_tool(row, "get_order")


def test_real_dependency_sse(api):
    row = api.request(
        "sse", dict(message="查询 ORD10001 的状态和金额"), path="/api/v1/chat/stream", expected=200
    )
    items = [
        json.loads(line[5:])
        for line in row["text"].splitlines()
        if line.startswith("data:") and line[5:].strip().startswith("{")
    ]
    assert items[0]["event"] == "started" and items[-1]["event"] == "done"
    final = next(x["data"] for x in items if x["event"] == "answer")
    assert "".join(x["text"] for x in items if x["event"] == "token") == final["answer"]
    assert "299.00" in final["answer"] and has_tool(row, "get_order")
    assert any(
        m["content"] == final["answer"] and m["session_id"] == final["session_id"]
        for m in row["database_after"]["messages"]
    )
    readonly(row)


@pytest.mark.parametrize("fault", ["generate_error", "judge_length", "generate_timeout"])
def test_model_fault_does_not_change_business_state(api, fault):
    row = api.request(fault, dict(message="查询 ORD10001 的状态和金额"), fault=fault, expected=200)
    assert "299.00" in row["body"]["answer"] and "未配置" not in row["body"]["answer"]
    readonly(row)


def new_paid_order(api):
    identifier = "ORD" + str(int(uuid.uuid4().hex[:10], 16))

    async def insert():
        engine = create_async_engine(api.cfg["database_url"])
        try:
            async with async_sessionmaker(engine)() as session:
                session.add(
                    OrderRow(order_id=identifier, user_id="u_demo", status="paid", total_cents=7900)
                )
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(insert())
    return identifier


def test_hitl_confirmation_and_sequential_idempotency(api):
    identifier = new_paid_order(api)
    proposal = chat(api, "hitl_proposal", "取消 " + identifier)
    readonly(proposal)
    action = proposal["body"]["pending_action"]
    assert action and action["tool_name"] == "cancel_order"
    payload = dict(
        message="确认取消",
        session_id=proposal["body"]["session_id"],
        confirm_action_id=action["action_id"],
        idempotency_key="p4b_" + uuid.uuid4().hex,
    )
    confirmed = api.request("hitl_confirm", payload, expected=200)
    assert has_tool(confirmed, "cancel_order", order_id=identifier)
    repeated = api.request("hitl_repeat", payload, expected=200)
    readonly(repeated)
    assert (
        next(o for o in repeated["database_after"]["orders"] if o["order_id"] == identifier)[
            "status"
        ]
        == "cancelled"
    )


def test_confirmation_concurrency_across_processes(api):
    """A real acceptance probe, deliberately not xfailed for memory-only pending state."""
    identifier = new_paid_order(api)
    proposal = chat(api, "concurrent_proposal", "取消 " + identifier)
    action = proposal["body"]["pending_action"]
    payload = dict(
        message="确认取消",
        session_id=proposal["body"]["session_id"],
        confirm_action_id=action["action_id"],
        idempotency_key="p4b_" + uuid.uuid4().hex,
    )

    # Capture HTTP responses without concurrently racing the evidence writer/snapshot helper.
    record = dict(http=[], database_before=None, database_after=None, capture_errors=[])

    def send(worker):
        import httpx

        from research.docs.agent_engineering_upgrade.p4_dependency_integration.worker import TOKENS

        with httpx.Client(timeout=20, trust_env=False) as client:
            trace = "p4b_" + uuid.uuid4().hex
            try:
                response = client.post(
                    api.processes[worker]["url"] + "/api/v1/chat",
                    json=payload,
                    headers={
                        "authorization": "Bearer " + TOKENS["user"],
                        "x-p4-case": "concurrent_confirm",
                        "x-trace-id": trace,
                    },
                )
                try:
                    body = response.json()
                    parse_error = None
                except ValueError:
                    body, parse_error = None, "INVALID_RESPONSE_JSON"
                return dict(
                    worker=worker,
                    trace_id=trace,
                    status=response.status_code,
                    body=body,
                    parse_error=parse_error,
                )
            except httpx.TransportError as exc:
                return dict(
                    worker=worker, trace_id=trace, status=None, transport_error=type(exc).__name__
                )

    try:
        record["database_before"] = asyncio.run(snapshot(api.cfg))
        with ThreadPoolExecutor(max_workers=2) as pool:
            record["http"] = list(pool.map(send, (0, 1)))
    except Exception as exc:
        record["capture_errors"].append(type(exc).__name__)
        raise
    finally:
        try:
            record["database_after"] = asyncio.run(snapshot(api.cfg))
        except Exception as exc:
            record["capture_errors"].append(type(exc).__name__)
        save(
            api.directory / "concurrent_confirmation.json",
            json.loads(json.dumps(record, default=str)),
        )
    rows = record["http"]
    assert not record["capture_errors"] and all(not r.get("parse_error") for r in rows)
    assert all(
        r["status"] == 200 for r in rows
    ), "Cross-process pending/confirmation consistency failed; preserve and diagnose in B3"
    assert_confirmation_effects(
        record["database_before"],
        record["database_after"],
        identifier,
        action["action_id"],
        {r["trace_id"] for r in rows},
    )


def test_pending_confirmation_survives_all_worker_restarts(api):
    identifier = new_paid_order(api)
    proposal = chat(api, "restart_proposal", "取消 " + identifier)
    action = proposal["body"]["pending_action"]
    before = asyncio.run(snapshot(api.cfg))
    api.stop()
    save(
        api.directory / "owned_cleanup_before_restart.json",
        json.loads((api.directory / "owned_cleanup.json").read_text()),
    )
    api.processes = []
    api.start(2)
    confirmed = api.request(
        "restart_confirm",
        dict(
            message="确认取消",
            session_id=proposal["body"]["session_id"],
            confirm_action_id=action["action_id"],
        ),
        worker=1,
        expected=200,
    )
    assert_confirmation_effects(
        before,
        confirmed["database_after"],
        identifier,
        action["action_id"],
        {confirmed["trace_id"]},
    )
    readonly(
        api.request(
            "restart_replay",
            dict(
                message="确认取消",
                session_id=proposal["body"]["session_id"],
                confirm_action_id=action["action_id"],
            ),
            expected=200,
        )
    )


def test_expired_or_foreign_durable_confirmation_fails_closed(api):
    from datetime import timedelta

    from app.repositories.models import PendingConfirmationRow

    identifier = new_paid_order(api)
    proposal = chat(api, "expiry_proposal", "取消 " + identifier)
    action = proposal["body"]["pending_action"]
    payload = dict(
        message="确认取消",
        session_id=proposal["body"]["session_id"],
        confirm_action_id=action["action_id"],
    )
    denied = api.request("foreign_confirmation", payload, identity="other", worker=1, expected=400)
    assert not calls(denied)
    readonly(denied)

    async def expire():
        engine = create_async_engine(api.cfg["database_url"])
        try:
            async with async_sessionmaker(engine)() as db:
                row = await db.get(PendingConfirmationRow, action["action_id"])
                row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
                await db.commit()
        finally:
            await engine.dispose()

    asyncio.run(expire())
    denied = api.request("expired_confirmation", payload, worker=1, expected=400)
    assert not calls(denied)
    readonly(denied)


@pytest.mark.parametrize(
    "service,dependency", [("postgres", "database"), ("redis", "redis"), ("qdrant", "vector_store")]
)
def test_actual_api_dependency_outage_and_recovery(api, service, dependency):
    import time

    import httpx

    from research.docs.agent_engineering_upgrade.p4_dependency_integration.sandbox import command
    from research.docs.agent_engineering_upgrade.p4_dependency_integration.worker import TOKENS

    async def clear_policy_cache():
        from redis.asyncio import Redis

        client = Redis.from_url(api.cfg["redis_url"])
        try:
            keys = [key async for key in client.scan_iter(match="ret:*")]
            if keys:
                await client.delete(*keys)
        finally:
            await client.aclose()

    if service == "qdrant":
        asyncio.run(clear_policy_cache())
    identifier = new_paid_order(api)
    proposal = chat(api, service + "_outage_proposal", "取消 " + identifier)
    payload = dict(
        message="确认取消",
        session_id=proposal["body"]["session_id"],
        confirm_action_id=proposal["body"]["pending_action"]["action_id"],
    )
    record = dict(
        service=service, before=asyncio.run(snapshot(api.cfg)), http=[], after=None, recovered=None
    )
    url = api.processes[0]["url"]

    def request(path, body=None):
        with httpx.Client(timeout=20, trust_env=False) as client:
            r = client.request(
                "GET" if body is None else "POST",
                url + path,
                json=body,
                headers={
                    "authorization": "Bearer " + TOKENS["user"],
                    "x-p4-case": service + "_outage",
                },
            )
            row = dict(path=path, status=r.status_code, text=r.text)
            record["http"].append(row)
            return r

    try:
        command(api.manifest, "stop", service)
        ready = request("/api/v1/ready").json()
        assert next(d for d in ready["dependencies"] if d["name"] == dependency)["ready"] is False
        assert ready["ready"] is (service != "postgres")
        assert request("/api/v1/health").status_code == 200
        if service == "postgres":
            failed = request("/api/v1/chat", payload)
            assert failed.status_code == 500 and failed.json()["error_code"] == "INTERNAL_ERROR"
            streamed = request("/api/v1/chat/stream", payload)
            events = [
                json.loads(line[5:])
                for line in streamed.text.splitlines()
                if line.startswith("data:")
            ]
            assert any(e["event"] == "error" for e in events)
            assert not any(e["event"] == "answer" for e in events)
        elif service == "redis":
            row = api.request(
                service + "_outage_read", dict(message="七天无理由退货政策是什么"), expected=503
            )
            assert row["body"]["error_code"] == "RATE_LIMIT_UNAVAILABLE"
            assert not calls(row)
            readonly(row)
        else:
            # Public-corpus vector outage may degrade to public lexical evidence.
            row = api.request(
                service + "_outage_read", dict(message="七天无理由退货政策是什么"), expected=200
            )
            readonly(row)
            assert row["body"]["answer"] and row["body"]["citations"]
            if service == "qdrant":
                spans = graph_observed(row)
                assert any(
                    s["name"] == "retrieval.vector" and s["status"] == "error" and s["error_type"]
                    for s in spans
                )
    finally:
        command(api.manifest, "start", service)
        for _ in range(100):
            try:
                with httpx.Client(timeout=3, trust_env=False) as client:
                    response = client.get(url + "/api/v1/ready").json()
                if next(d for d in response["dependencies"] if d["name"] == dependency)["ready"]:
                    record["recovered"] = response
                    break
            except Exception:
                pass
            time.sleep(0.1)
        record["after"] = asyncio.run(snapshot(api.cfg))
        save(
            api.directory / (service + "_outage_recovery.json"),
            json.loads(json.dumps(record, default=str)),
        )
    assert record["recovered"] is not None
    readonly(dict(database_before=record["before"], database_after=record["after"]))
    confirmed = api.request(service + "_recovered_confirmation", payload, worker=1, expected=200)
    assert has_tool(confirmed, "cancel_order", order_id=identifier)
    assert_confirmation_effects(
        record["before"],
        confirmed["database_after"],
        identifier,
        payload["confirm_action_id"],
        {confirmed["trace_id"]},
    )

    if service == "qdrant":
        asyncio.run(clear_policy_cache())
        recovered = chat(api, "qdrant_recovered_cold_rag", "七天无理由退货政策是什么")
        readonly(recovered)
        assert recovered["body"]["citations"]
        assert any(
            s["name"] == "retrieval.vector" and s["status"] == "ok"
            for s in graph_observed(recovered)
        )
