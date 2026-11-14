"""Real Dev startup gates use synthetic keys and never send a paid request."""

from pathlib import Path

import pytest


@pytest.fixture
def real_environment(tmp_path, monkeypatch):
    from app.demo.docker import bootstrap

    secret, state, budget = (tmp_path / part for part in ["secret", "state", "budget"])
    bootstrap(secret, state, owner_uid=None)
    budget.mkdir(mode=0o700)
    values = {
        "REAL_AGENT_DEV_ENABLED": "true",
        "REAL_AGENT_MAX_REQUESTS": "10",
        "REAL_AGENT_MAX_TOKENS": "200000",
        "REAL_AGENT_MAX_USD": "2",
        "REAL_AGENT_INPUT_USD_PER_MILLION": "5",
        "REAL_AGENT_OUTPUT_USD_PER_MILLION": "10",
        "DEEPSEEK_API_KEY": "synthetic-only-never-dispatched",
        "DEEPSEEK_MODEL": "deepseek-chat",
        "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
        "EXPERIENCE_MEMORY_MODE": "off",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("DEEPSEEK_API_KEY_FILE", raising=False)
    return secret, state, budget


def load(real_environment):
    from app.demo.real_dev import load_runtime_config

    secret, state, budget = real_environment
    return load_runtime_config(secret, state, budget)


def test_real_dev_disables_automatic_paid_retries(real_environment):
    assert load(real_environment).settings.llm_max_retries == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("authorized", [False, True])
async def test_real_dev_payment_authorization_is_server_only_and_defaults_off(
    real_environment, monkeypatch, authorized
):
    from types import SimpleNamespace

    import httpx

    import app.demo.real_dev as runtime
    from app.providers.paid_budget import AttemptLedger, BudgetBlocked

    if authorized:
        monkeypatch.setenv("REAL_AGENT_PAID_AUTHORIZED", "true")
    else:
        monkeypatch.delenv("REAL_AGENT_PAID_AUTHORIZED", raising=False)
    config = load(real_environment)
    sent = []

    def respond(request):
        sent.append(request)
        return httpx.Response(200, json={"model":"deepseek-chat", "choices":[{"message":{"content":"hello"},"finish_reason":"stop"}], "usage":{"prompt_tokens":2,"completion_tokens":1,"total_tokens":3}})

    async def build(settings, seed=False, *, llm_provider=None):
        async def close():pass
        return SimpleNamespace(llm=llm_provider, engine=SimpleNamespace(dialect=SimpleNamespace(name="postgresql")), redis=object(), vector_store=type("PrivateVectorStore", (), {})(), aclose=close)

    monkeypatch.setattr(runtime, "build_container", build)
    app = runtime.create_application(config, transport=httpx.MockTransport(respond))
    async with app.router.lifespan_context(app):
        if authorized:
            assert (await app.state.container.llm.generate([{"role":"user","content":"hello"}],max_tokens=8)).content == "hello"
        else:
            with pytest.raises(BudgetBlocked):
                await app.state.container.llm.generate([{"role":"user","content":"hello"}],max_tokens=8)
    assert len(sent) == int(authorized)
    assert AttemptLedger(config.budget_path, config.limits).snapshot()["requests"] == int(authorized)


def test_real_dev_defaults_to_explicit_non_thinking_json_mode(real_environment):
    assert getattr(load(real_environment).settings, "deepseek_thinking_mode", None) == "disabled"


def test_real_dev_rejects_invalid_thinking_mode(real_environment, monkeypatch):
    from app.demo.real_dev import RealDevConfigurationError

    monkeypatch.setenv("DEEPSEEK_THINKING_MODE", "invalid")
    with pytest.raises(RealDevConfigurationError, match="Invalid DEEPSEEK_THINKING_MODE"):
        load(real_environment)


@pytest.mark.parametrize("value", [None, "false", "1"])
def test_real_dev_requires_explicit_server_enable(real_environment, monkeypatch, value):
    from app.demo.real_dev import RealDevConfigurationError

    if value is None:
        monkeypatch.delenv("REAL_AGENT_DEV_ENABLED")
    else:
        monkeypatch.setenv("REAL_AGENT_DEV_ENABLED", value)
    with pytest.raises(RealDevConfigurationError, match="REAL_AGENT_DEV_ENABLED"):
        load(real_environment)


def test_real_dev_missing_key_fails_without_offline_fallback(real_environment, monkeypatch):
    from app.demo.real_dev import RealDevConfigurationError

    monkeypatch.delenv("DEEPSEEK_API_KEY")
    with pytest.raises(RealDevConfigurationError, match="DEEPSEEK_API_KEY"):
        load(real_environment)


@pytest.mark.parametrize(
    "name",
    [
        "REAL_AGENT_MAX_REQUESTS",
        "REAL_AGENT_MAX_TOKENS",
        "REAL_AGENT_MAX_USD",
        "REAL_AGENT_INPUT_USD_PER_MILLION",
        "REAL_AGENT_OUTPUT_USD_PER_MILLION",
    ],
)
def test_real_dev_requires_all_budget_bounds(real_environment, monkeypatch, name):
    from app.demo.real_dev import RealDevConfigurationError

    monkeypatch.delenv(name)
    with pytest.raises(RealDevConfigurationError, match=name):
        load(real_environment)


@pytest.mark.parametrize(
    "name,value",
    [
        ("REAL_AGENT_MAX_REQUESTS", "0"),
        ("REAL_AGENT_MAX_TOKENS", "-1"),
        ("REAL_AGENT_MAX_USD", "NaN"),
        ("REAL_AGENT_INPUT_USD_PER_MILLION", "Infinity"),
        ("REAL_AGENT_OUTPUT_USD_PER_MILLION", "0"),
    ],
)
def test_real_dev_rejects_invalid_limits(real_environment, monkeypatch, name, value):
    from app.demo.real_dev import RealDevConfigurationError

    monkeypatch.setenv(name, value)
    with pytest.raises(RealDevConfigurationError):
        load(real_environment)


@pytest.mark.parametrize("mode", ["active", "shadow"])
def test_real_dev_never_activates_experience(real_environment, monkeypatch, mode):
    from app.demo.real_dev import RealDevConfigurationError

    monkeypatch.setenv("EXPERIENCE_MEMORY_MODE", mode)
    with pytest.raises(RealDevConfigurationError, match="EXPERIENCE_MEMORY_MODE"):
        load(real_environment)


def test_real_dev_reads_private_secret_file_without_disclosing_it(real_environment, monkeypatch):
    secret = real_environment[0] / "deepseek-key"
    secret.write_text("synthetic-file-key-not-real\n")
    monkeypatch.delenv("DEEPSEEK_API_KEY")
    monkeypatch.setenv("DEEPSEEK_API_KEY_FILE", str(secret))
    config = load(real_environment)
    assert config.settings.deepseek_api_key.get_secret_value() == "synthetic-file-key-not-real"
    assert "synthetic-file-key-not-real" not in repr(config)
    assert config.settings.auth_mode == "required"
    assert config.settings.knowledge_mode == "private"
    assert config.settings.memory_mode == "M2"
    assert config.settings.rate_limit_per_minute == 60
    assert config.budget_path == real_environment[2] / "budget.sqlite3"
    assert config.limits.max_requests == 10


def test_real_dev_rejects_ambiguous_secret_sources(real_environment, monkeypatch):
    from app.demo.real_dev import RealDevConfigurationError

    secret = real_environment[0] / "deepseek-key"
    secret.write_text("synthetic-ambiguous-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY_FILE", str(secret))
    with pytest.raises(RealDevConfigurationError, match="one"):
        load(real_environment)


def test_real_dev_preserves_existing_proxy_environment(real_environment, monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9876")
    load(real_environment)
    import os

    assert os.environ["HTTPS_PROXY"] == "http://127.0.0.1:9876"


def test_real_dev_denies_endpoint_credentials_and_insecure_http(real_environment, monkeypatch):
    from app.demo.real_dev import RealDevConfigurationError

    for value in ["http://api.deepseek.com", "https://secret:secret@api.deepseek.com"]:
        monkeypatch.setenv("DEEPSEEK_BASE_URL", value)
        with pytest.raises(RealDevConfigurationError):
            load(real_environment)


def test_offline_settings_still_ignore_real_dev_environment(real_environment):
    from app.demo.docker import runtime_settings

    settings = runtime_settings(*real_environment[:2])
    assert not settings.llm_configured
    assert settings.auth_mode == "required"


def test_real_dev_bootstrap_prepares_only_private_budget_directory(tmp_path):
    from app.demo.real_dev import bootstrap_real

    secret, state, budget = (tmp_path / part for part in ["secret", "state", "budget"])
    bootstrap_real(secret, state, budget, owner_uid=None)
    assert budget.is_dir() and budget.stat().st_mode & 0o777 == 0o700
    assert not (budget / "budget.sqlite3").exists()
    assert (state / "development_credentials.json").is_file()


def test_real_dev_startup_uses_same_container_with_budgeted_provider(real_environment, monkeypatch):
    import httpx

    from app.demo.real_dev import create_application
    from app.main import create_app

    config = load(real_environment)
    app = create_application(
        config,
        transport=httpx.MockTransport(
            lambda request: pytest.fail("startup must not send model HTTP")
        ),
    )
    reference = create_app(config.settings)
    assert {route.path for route in app.routes} == {route.path for route in reference.routes}
    assert app.state.settings.llm_configured
    assert app.state.settings.auth_mode == "required"
    assert Path(config.budget_path).parent == real_environment[2]


@pytest.mark.asyncio
async def test_real_dev_lifespan_wires_budgeted_deepseek_without_model_dispatch(
    real_environment, monkeypatch
):
    from types import SimpleNamespace

    import httpx

    import app.demo.real_dev as runtime
    from app.providers.deepseek import DeepSeekProvider
    from app.providers.paid_budget import AttemptLedger

    config = load(real_environment)
    closed = []

    async def build(settings, seed=False, *, llm_provider=None):
        assert settings is config.settings and seed is False
        assert isinstance(llm_provider, DeepSeekProvider)
        assert await llm_provider.ping()  # readiness reads configuration, never POSTs.

        async def close():
            closed.append(True)

        return SimpleNamespace(
            llm=llm_provider,
            engine=SimpleNamespace(dialect=SimpleNamespace(name="postgresql")),
            redis=object(),
            vector_store=type("PrivateVectorStore", (), {})(),
            aclose=close,
        )

    monkeypatch.setattr(runtime, "build_container", build)
    app = runtime.create_application(
        config,
        transport=httpx.MockTransport(
            lambda request: pytest.fail("startup must not dispatch paid HTTP")
        ),
    )
    async with app.router.lifespan_context(app):
        assert isinstance(app.state.container.llm, DeepSeekProvider)
    assert closed == [True]
    assert AttemptLedger(config.budget_path, config.limits).snapshot()["requests"] == 0


def test_real_dev_overlay_uses_separate_resources_port_and_secret_reference(
    tmp_path, real_environment
):
    import json
    import os
    import shutil
    import subprocess

    if shutil.which("docker") is None:
        pytest.skip("Docker Compose CLI unavailable")
    secret = tmp_path / "private-key"
    secret.write_text("synthetic-key-config-only")
    env = dict(os.environ, REAL_AGENT_KEY_FILE=str(secret))
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            "compose.showcase.yml",
            "-f",
            "compose.agent-dev.yml",
            "config",
            "--format",
            "json",
        ],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0
    config = json.loads(result.stdout)
    assert config["name"] == "adaptive-rag-real-agent-dev"
    api = config["services"]["api"]
    assert len(api["ports"]) == 1
    assert api["ports"][0]["published"] == "8001"
    assert api["ports"][0]["host_ip"] == "127.0.0.1"
    assert api["environment"]["DEEPSEEK_API_KEY"] == ""
    assert api["environment"]["EXPERIENCE_MEMORY_MODE"] == "off"
    assert all(
        volume["name"].startswith("adaptive-rag-real-agent-dev_")
        for volume in config["volumes"].values()
    )
    assert secret.read_text() not in result.stdout
    assert api["healthcheck"]["test"] == ["CMD", "python", "-m", "app.demo.real_dev", "health"]


@pytest.mark.asyncio
@pytest.mark.parametrize("unready", ["redis", "vector_store", None])
async def test_real_dev_health_checks_required_dependencies_without_model_calls(
    monkeypatch, unready
):
    import httpx

    import app.demo.docker as offline
    import app.demo.real_dev as runtime

    original_client = httpx.AsyncClient
    paths = []

    def response(request):
        paths.append(request.url.path)
        if request.url.path.endswith("/ready"):
            return httpx.Response(
                200,
                json={
                    "ready": True,
                    "dependencies": [
                        {"name": name, "ready": name != unready}
                        for name in ["database", "redis", "vector_store"]
                    ],
                },
            )
        if request.url.path.endswith("/capabilities"):
            return httpx.Response(
                200,
                json={
                    "llm": "deepseek",
                    "database": "postgresql",
                    "cache": "redis",
                    "vector_store": "PrivateVectorStore",
                },
            )
        if request.url.path.endswith("/auth/me"):
            return httpx.Response(200, json={"subject": "web_demo_a"})
        pytest.fail("Health check must not call chat completions")

    monkeypatch.setattr(
        runtime.httpx,
        "AsyncClient",
        lambda **kwargs: original_client(transport=httpx.MockTransport(response), **kwargs),
    )
    monkeypatch.setattr(
        offline, "read_credentials", lambda: {"tokens": {"a": "synthetic-health-token"}}
    )
    if unready:
        with pytest.raises(runtime.RealDevConfigurationError):
            await runtime.health()
    else:
        await runtime.health()
        assert paths == ["/api/v1/ready", "/api/v1/capabilities", "/api/v1/auth/me"]
