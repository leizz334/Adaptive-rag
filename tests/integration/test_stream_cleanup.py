import asyncio
from types import SimpleNamespace

from app.api.routes.chat import chat_stream
from app.observability.tracing import TraceRecorder
from app.schemas.chat import ChatRequest
from eval.environment import BusinessEnvironment


async def test_route_iterator_close_finalizes_owned_trace_without_context_leak():
    records = []
    async with BusinessEnvironment(tracer=TraceRecorder(enabled=True, sink=records.append)) as env:
        response = await chat_stream(
            ChatRequest(message="你好"),
            SimpleNamespace(state=SimpleNamespace(trace_id="t")),
            env.container,
        )
        await anext(response.body_iterator)
        await response.body_iterator.aclose()
        assert len(records) == 1
        assert records[0][0].status == "cancelled"
        assert all(s.status != "running" for s in records[0])


async def test_asgi_disconnect_closes_body_iterator_and_graph(monkeypatch):
    from sse_starlette.sse import AppStatus

    # sse-starlette caches an asyncio event globally; isolate the test loop.
    monkeypatch.setattr(AppStatus, "should_exit_event", None)
    records = []
    async with BusinessEnvironment(tracer=TraceRecorder(enabled=True, sink=records.append)) as env:
        response = await chat_stream(
            ChatRequest(message="你好"),
            SimpleNamespace(state=SimpleNamespace(trace_id="t")),
            env.container,
        )
        disconnected = asyncio.Event()

        async def receive():
            await disconnected.wait()
            return {"type": "http.disconnect"}

        async def send(message):
            if message["type"] == "http.response.body":
                disconnected.set()
                await asyncio.sleep(0.05)

        await response({"type": "http", "asgi": {"version": "3.0"}}, receive, send)
        assert response.body_iterator.ag_frame is None
        assert len(records) == 1
        assert records[0][0].status == "cancelled"
