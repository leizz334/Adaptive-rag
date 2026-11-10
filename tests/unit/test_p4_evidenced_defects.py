import json
from types import SimpleNamespace

import pytest

from app.agents.goals import read_tools
from app.config.settings import Settings


@pytest.mark.parametrize("query", ["核对 ORD90876 的退款状态", "查看订单 ORD73519 售后退款状态"])
def test_refund_status_request_requires_refund_observation(query):
    assert "get_refund_status" in read_tools(query)


async def test_explicit_app_settings_reach_lifespan_without_global_resolution(monkeypatch):
    import app.main as main

    explicit = Settings(
        _env_file=None, app_env="testing", database_url="sqlite+aiosqlite:///:memory:"
    )
    observed = []

    class Container:
        async def aclose(self):
            observed.append("closed")

    async def build(settings):
        observed.append(settings)
        return Container()

    monkeypatch.setattr(main, "build_container", build)
    app = main.create_app(explicit)

    def forbidden():
        raise AssertionError("Explicit app must not load global/.env settings")

    monkeypatch.setattr(main, "get_settings", forbidden)
    async with app.router.lifespan_context(app):
        assert observed == [explicit]
    assert observed[-1] == "closed"


@pytest.mark.parametrize("kind", ["runtime", "timeout"])
async def test_stream_late_error_has_safe_error_done_and_closes_iterator(kind):
    from app.api.routes.chat import chat_stream
    from app.core.exceptions import LLMProviderError
    from app.schemas.chat import ChatRequest

    closed = []

    class Service:
        async def stream(self, *args, **kwargs):
            try:
                yield dict(event="started", trace_id="synthetic")
                if kind == "timeout":
                    raise LLMProviderError("controlled timeout", timeout=True)
                raise RuntimeError("SYNTHETIC_PRIVATE_ERROR_DETAIL")
            finally:
                closed.append(True)

    response = await chat_stream(
        ChatRequest(message="你好"),
        SimpleNamespace(state=SimpleNamespace(trace_id="synthetic")),
        SimpleNamespace(chat_service=Service()),
    )
    items = [json.loads(event.data) async for event in response.body_iterator]
    assert items[-1]["event"] == "done" and closed == [True]
    error = next(item for item in items if item["event"] == "error")
    assert error["error_code"] == ("LLM_TIMEOUT" if kind == "timeout" else "INTERNAL_ERROR")
    assert "SYNTHETIC_PRIVATE_ERROR_DETAIL" not in json.dumps(items)
