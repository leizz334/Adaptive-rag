"""Offline-only tests of experiment isolation, accounting and stop conditions."""

import httpx
import pytest
from pydantic import SecretStr

from app.config.settings import Settings
from app.providers.deepseek import DeepSeekProvider
from research.docs.agent_engineering_upgrade.real_llm_baseline import baseline as b


@pytest.fixture
def setup_probe(tmp_path, monkeypatch):
    monkeypatch.setattr(b, "OUT", tmp_path)
    settings = Settings(
        _env_file=None,
        deepseek_api_key=SecretStr("SYNTHETIC_TEST_ONLY"),
        deepseek_base_url="https://gateway.invalid",
        deepseek_model="configured",
        llm_max_retries=1,
    )
    monkeypatch.setattr(b, "isolated_settings", lambda: settings)
    b.write(
        "experiment_config.json",
        {
            "endpoint": settings.deepseek_base_url,
            "configured_model": "configured",
            "probe_messages": [{"role": "user", "content": "read-only"}],
            "probe_max_tokens": 32,
            "max_http_attempts": 80,
            "max_accounted_tokens": 100000,
        },
    )
    b.write("results.json", {"connectivity": None, "results": []})
    b.write("requests.json", [])
    client_type = httpx.AsyncClient
    calls = []

    def install(response):
        def transport(request):
            calls.append(request)
            return response

        monkeypatch.setattr(
            b.httpx,
            "AsyncClient",
            lambda **kw: client_type(**kw, transport=httpx.MockTransport(transport)),
        )

    async def build(settings, seed):
        class Container:
            llm = DeepSeekProvider(settings)

            async def aclose(self):
                await self.llm.aclose()

        return Container()

    monkeypatch.setattr(b, "build_container", build)
    return install, calls


@pytest.mark.asyncio
async def test_actual_model_usage_and_no_automatic_replay(setup_probe):
    install, calls = setup_probe
    install(
        httpx.Response(
            200,
            json={
                "model": "reported-by-gateway",
                "choices": [{"message": {"content": "BASELINE_OK"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13},
            },
        )
    )
    await b.probe()
    assert b.read("results.json")["connectivity"]["connected"] is True
    assert b.read("requests.json")[0]["model_reported"] == "reported-by-gateway"
    assert b.read("requests.json")[0]["usage"]["total_tokens"] == 13
    assert "SYNTHETIC_TEST_ONLY" not in (b.OUT / "requests.json").read_text()
    with pytest.raises(SystemExit, match="already attempted"):
        await b.probe()
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_http_200_non_json_is_not_model_success(setup_probe):
    install, calls = setup_probe
    install(httpx.Response(200, text="not an API response"))
    await b.probe()
    result = b.read("results.json")
    record = b.read("requests.json")[0]
    assert result["connectivity"]["connected"] is False
    assert record["http_status"] == 200
    assert record["error_chain"][0]["type"] == "JSONDecodeError"
    assert "usage" not in record
    assert result["results"] == []
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_request_budget_blocks_before_transport(setup_probe):
    install, calls = setup_probe
    install(httpx.Response(200, json={}))
    config = b.read("experiment_config.json")
    config["max_http_attempts"] = 0
    b.write("experiment_config.json", config)
    await b.probe()
    assert calls == []
    assert b.read("results.json")["connectivity"]["connected"] is False


@pytest.mark.asyncio
async def test_token_budget_blocks_before_transport(setup_probe):
    install, calls = setup_probe
    install(httpx.Response(200, json={}))
    config = b.read("experiment_config.json")
    config["max_accounted_tokens"] = 1
    b.write("experiment_config.json", config)
    await b.probe()
    assert calls == []
    assert b.read("requests.json") == []
    assert b.read("results.json")["connectivity"]["error_chain"][0]["type"] == "BudgetExceeded"


def test_settings_never_use_production_business_services(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://production.invalid/db")
    monkeypatch.setenv("MCP_ENABLED", "true")
    monkeypatch.setenv("AGENT_TRACING_ENABLED", "true")
    s = b.isolated_settings()
    assert s.database_url == "sqlite+aiosqlite:///:memory:"
    assert not s.agent_tracing_enabled and not s.mcp_enabled
    assert not s.redis_url and not s.qdrant_url and not s.embedding_configured
    assert not s.local_embedding_configured and not s.cross_encoder_configured


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "usage",
    [
        None,
        {"total_tokens": 13},
        {"prompt_tokens": 100001, "completion_tokens": 3, "total_tokens": 100004},
    ],
)
async def test_unknown_invalid_or_over_budget_usage_cannot_pass_gate(setup_probe, usage):
    install, calls = setup_probe
    payload = {"model": "reported", "choices": [{"message": {"content": "BASELINE_OK"}}]}
    if usage is not None:
        payload["usage"] = usage
    install(httpx.Response(200, json=payload))
    await b.probe()
    result = b.read("results.json")
    assert result["status"] == "BLOCKED_ACCOUNTING"
    assert result["connectivity"]["connected"] is False
    assert result["connectivity"].get("usage") is None
    assert len(calls) == 1
