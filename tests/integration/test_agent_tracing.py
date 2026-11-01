import json

import httpx
import pytest

from app.config.settings import Settings
from app.observability.langsmith_exporter import LangSmithExporter, run_payload
from app.observability.tracing import TraceRecorder
from app.providers.deepseek import DeepSeekProvider
from app.schemas.chat import ChatRequest
from app.services.container import build_container


async def test_service_graph_sse_privacy_and_disabled_parity():
    settings = Settings(
        _env_file=None,
        app_env="testing",
        database_url="sqlite+aiosqlite:///:memory:",
        deepseek_api_key="",
        embedding_api_key="",
        redis_url="",
        qdrant_url="",
        agent_tracing_enabled=False,
    )
    container = await build_container(settings, seed=True)
    records = []
    try:
        service = container.chat_service
        off = await service.chat(ChatRequest(message="你好", user_id="u_demo"), trace_id="t")
        service._tracer = TraceRecorder(enabled=True, sink=records.append)
        on = await service.chat(ChatRequest(message="你好", user_id="u_demo"), trace_id="ORD10001")
        assert off.answer == on.answer
        names = {s.name for s in records[0]}
        assert {
            "chat.turn",
            "session.load",
            "node.guardrail",
            "node.intent",
            "node.router",
            "node.generate",
            "node.memory",
            "session.persist",
            "transaction.commit",
        } <= names
        events = [e async for e in service.stream(ChatRequest(message="你好"), trace_id="stream")]
        assert events[-1]["event"] == "done"
        assert len(records) == 2
        assert all(s.end_time and s.status != "running" for s in records[1])
        stream = service.stream(ChatRequest(message="你好"), trace_id="cancel")
        await anext(stream)
        await stream.aclose()
        assert records[-1][0].status == "cancelled"
        serialized = json.dumps([run_payload(s) for batch in records for s in batch], default=str)
        assert "ORD10001" not in serialized and "u_demo" not in serialized
    finally:
        await container.aclose()


async def test_http_attempt_and_usage_without_raw_messages():
    def response(request):
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "CANARY_RESPONSE"}}],
                "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10},
            },
        )

    settings = Settings(_env_file=None, deepseek_api_key="CANARY_KEY")
    records = []
    async with httpx.AsyncClient(
        base_url="https://offline.invalid", transport=httpx.MockTransport(response)
    ) as client:
        provider = DeepSeekProvider(settings, client=client)
        with TraceRecorder(enabled=True, sink=records.append).turn(trace_id="t"):
            result = await provider.generate([{"role": "user", "content": "CANARY_INPUT"}])
        assert result.usage.total_tokens == 10
    assert [s.name for s in records[0]] == ["chat.turn", "llm.deepseek", "llm.http_attempt"]
    assert records[0][1].metadata["total_tokens"] == 10
    assert "total_tokens" not in records[0][2].metadata
    serialized = json.dumps([run_payload(s) for s in records[0]], default=str)
    assert not any(x in serialized for x in ["CANARY_KEY", "CANARY_INPUT", "CANARY_RESPONSE"])


def test_langsmith_explicit_credentials_and_offline_payload():
    with pytest.raises(ValueError):
        LangSmithExporter(Settings(_env_file=None, agent_langsmith_api_key=""))

    class Client:
        def __init__(self):
            self.rows = []

        def create_run(self, **payload):
            self.rows.append(payload)

    client = Client()
    exporter = LangSmithExporter(
        Settings(_env_file=None, agent_langsmith_api_key="synthetic"), client=client
    )
    recorder = TraceRecorder(enabled=True, sink=exporter)
    with recorder.turn(trace_id="private", session_id="private"):
        pass
    exporter.close()
    assert len(client.rows) == 1
    assert client.rows[0]["inputs"] == {} and client.rows[0]["outputs"] == {}
    assert client.rows[0]["parent_run_id"] is None


def test_real_langsmith_sdk_serializes_to_offline_transport_only():
    import requests
    from langsmith import Client
    from requests.adapters import BaseAdapter

    captured = []

    class OfflineTransport(BaseAdapter):
        def send(self, request, **kwargs):
            captured.append(request)
            response = requests.Response()
            response.status_code = 200
            response._content = b"{}"
            response.request = request
            return response

        def close(self):
            pass

    session = requests.Session()
    session.mount("https://", OfflineTransport())
    session.mount("http://", OfflineTransport())
    sdk = Client(
        api_url="https://offline.invalid",
        api_key="synthetic",
        session=session,
        auto_batch_tracing=False,
        hide_inputs=True,
        hide_outputs=True,
        omit_traced_runtime_info=True,
    )
    # Client installs a more-specific retry adapter; replace that exact prefix.
    session.mount("https://offline.invalid/", OfflineTransport())
    settings = Settings(_env_file=None, agent_langsmith_api_key="synthetic")
    exporter = LangSmithExporter(settings, client=sdk)
    with TraceRecorder(enabled=True, sink=exporter).turn(trace_id="CANARY_SECRET"):
        pass
    exporter.close()
    assert exporter.errors == 0
    posts = [r for r in captured if r.method == "POST"]
    assert len(posts) == 1
    body = json.loads(posts[0].body)
    assert body["name"] == "chat.turn"
    assert body["inputs"] == {} and body["outputs"] == {}
    assert "CANARY_SECRET" not in json.dumps(body)
