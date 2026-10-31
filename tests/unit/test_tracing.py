import asyncio
import json

import pytest

from app.observability.langsmith_exporter import run_payload
from app.observability.tracing import TraceRecorder, span, traced


@traced("work", "chain")
async def work():
    await asyncio.sleep(0)
    with span("child", "tool", arguments={"password": "CANARY_SECRET"}, count=2):
        await asyncio.to_thread(lambda: None)


async def test_concurrent_roots_and_privacy():
    records = []
    recorder = TraceRecorder(enabled=True, sink=records.append)

    async def one(identity):
        with recorder.turn(trace_id="ORD10001", session_id=identity, user_id="13800138000"):
            await work()

    await asyncio.gather(one("private-a"), one("private-b"))
    assert len(records) == 2
    for spans in records:
        root = next(s for s in spans if s.parent_id is None)
        worker = next(s for s in spans if s.name == "work")
        child = next(s for s in spans if s.name == "child")
        assert worker.parent_id == root.id
        assert child.parent_id == worker.id
        assert len({s.root_id for s in spans}) == 1
        serialized = json.dumps([run_payload(s) for s in spans], default=str)
        assert not any(
            raw in serialized
            for raw in ["ORD10001", "13800138000", "private-a", "private-b", "CANARY_SECRET"]
        )
    assert records[0][0].root_id != records[1][0].root_id


async def test_disabled_and_export_failure_do_not_change_result():
    records = []
    with TraceRecorder(enabled=False, sink=records.append).turn(trace_id="t"):
        await work()
    assert records == []

    def broken(_):
        raise RuntimeError("CANARY_SECRET")

    recorder = TraceRecorder(enabled=True, sink=broken)
    with recorder.turn(trace_id="t"):
        await work()
    assert recorder.export_errors == 1


async def test_generator_close_and_span_bound():
    records = []
    recorder = TraceRecorder(enabled=True, sink=records.append, max_spans=3)

    @traced("streaming", "chain")
    async def streaming():
        yield 1
        yield 2

    with recorder.turn(trace_id="t"):
        source = streaming()
        assert await anext(source) == 1
        await source.aclose()
        for _ in range(20):
            with span("bounded", "tool"):
                pass
    assert len(records[0]) <= 3
    assert next(s for s in records[0] if s.name == "streaming").status == "cancelled"
    assert recorder.dropped_spans > 0


async def test_error_records_type_not_exception_content():
    records = []
    with (
        pytest.raises(ValueError),
        TraceRecorder(enabled=True, sink=records.append).turn(trace_id="t"),
    ):
        with span("broken", "tool"):
            raise ValueError("CANARY_SECRET")
    assert all(s.status == "error" for s in records[0])
    assert "CANARY_SECRET" not in json.dumps([run_payload(s) for s in records[0]], default=str)
