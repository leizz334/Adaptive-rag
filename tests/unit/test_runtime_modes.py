"""Public mode metadata stays keyless and never opens business-API CORS."""

from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from app.config.settings import Settings
from app.main import create_app
from app.providers.deepseek import DeepSeekProvider
from app.providers.fake import OfflineLLMProvider


@pytest.fixture
async def apps():
    owned = []

    def build(mode="offline", status=None):
        settings = Settings(
            _env_file=None,
            app_env="testing",
            deepseek_api_key="synthetic-not-real" if mode == "deepseek" else "",
        )
        app = create_app(settings)
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        client = httpx.AsyncClient(
            base_url="https://api.deepseek.com",
            transport=httpx.MockTransport(
                lambda r: pytest.fail("metadata must never dispatch model HTTP")
            ),
        )
        llm = (
            DeepSeekProvider(settings, client=client)
            if mode == "deepseek"
            else OfflineLLMProvider()
        )

        async def ping():
            return True

        app.state.container = SimpleNamespace(
            settings=settings,
            llm=llm,
            engine=engine,
            redis=SimpleNamespace(ping=ping),
            vector_store=SimpleNamespace(ping=lambda: True),
        )
        if status is not None:
            app.state.real_agent_admission = lambda: status
        app.state.verification_only = False
        owned.append((engine, client))
        return app

    yield build
    for engine, client in owned:
        await client.aclose()
        await engine.dispose()


async def get(app, path="/api/v1/runtime-status", origin=None):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8000"
    ) as client:
        return await client.get(path, headers={"Origin": origin} if origin else {})


async def test_offline_mode_is_public_and_reports_no_credentials(apps):
    response = await get(apps())
    assert response.status_code == 200
    assert response.json() == {
        "mode": "offline",
        "available": True,
        "reason": "ready",
        "message": "Offline 服务可用。",
        "verification_only": False,
    }
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "reason", ["payment_not_authorized", "budget_not_ready", "budget_exhausted"]
)
async def test_deepseek_unavailable_reason_is_explicit_and_contains_no_secret(apps, reason):
    response = await get(apps("deepseek", {"available": False, "reason": reason}))
    assert response.status_code == 200 and response.json()["available"] is False
    assert response.json()["mode"] == "deepseek" and response.json()["reason"] == reason
    assert "synthetic-not-real" not in response.text and "budget.sqlite" not in response.text


async def test_ungated_generic_deepseek_is_not_advertised_as_real_dev(apps):
    response = await get(apps("deepseek"))
    assert response.json()["available"] is False
    assert response.json()["reason"] == "unsupported_deployment"


@pytest.mark.parametrize(
    "origin",
    [
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8001",
        "http://localhost:8000",
        "http://localhost:8001",
    ],
)
async def test_only_public_mode_get_has_narrow_noncredentialed_cors(apps, origin):
    app = apps()
    public = await get(app, origin=origin)
    assert public.headers.get("access-control-allow-origin") == origin
    assert "access-control-allow-credentials" not in public.headers
    business = await get(app, "/api/v1/auth/me", origin=origin)
    assert business.status_code == 401
    assert "access-control-allow-origin" not in business.headers


async def test_untrusted_origin_receives_no_cors_permission(apps):
    response = await get(apps(), origin="https://untrusted.example")
    assert "access-control-allow-origin" not in response.headers


async def test_dependency_failure_is_not_advertised_available(apps):
    app = apps()

    async def fail():
        raise RuntimeError("private connection details")

    app.state.container.redis.ping = fail
    response = await get(app)
    assert response.json()["available"] is False
    assert response.json()["reason"] == "dependencies_unavailable"
    assert "private connection details" not in response.text
