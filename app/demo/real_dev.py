"""Explicit server-only Real Agent Dev; configuration checks never invoke the model."""

from __future__ import annotations

import argparse
import os
import re
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from pydantic import SecretStr

from app.config.settings import Settings
from app.demo.docker import SECRET_DIR, STATE_DIR, bootstrap, runtime_settings
from app.main import create_app
from app.providers.deepseek import DeepSeekProvider
from app.providers.paid_budget import (
    AttemptLedger,
    BudgetedTransport,
    BudgetLimits,
    _request_reservation,
)
from app.services.container import build_container

BUDGET_DIR = Path("/var/lib/real-agent")


class RealDevConfigurationError(ValueError):
    """Safe configuration diagnostics contain names, never configuration values."""


@dataclass(frozen=True)
class RuntimeConfig:
    settings: Settings = field(repr=False)
    limits: BudgetLimits
    budget_path: Path


def _positive(name: str, *, integer: bool = False):
    value = os.environ.get(name, "")
    try:
        number = Decimal(value)
        if not number.is_finite() or number <= 0:
            raise InvalidOperation()
        if integer and (number != number.to_integral_value() or not value.isdecimal()):
            raise InvalidOperation()
        return int(number) if integer else number
    except (InvalidOperation, ValueError, OverflowError):
        raise RealDevConfigurationError(
            f"Real Agent Dev requires a positive finite {name}"
        ) from None


def _key() -> SecretStr:
    direct = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    filename = os.environ.get("DEEPSEEK_API_KEY_FILE", "").strip()
    if bool(direct) == bool(filename):
        raise RealDevConfigurationError("Set exactly one DEEPSEEK_API_KEY or DEEPSEEK_API_KEY_FILE")
    if filename:
        path = Path(filename)
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 4096:
                raise OSError()
            direct = path.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError):
            raise RealDevConfigurationError(
                "DEEPSEEK_API_KEY_FILE is not a readable private key file"
            ) from None
    if not 8 <= len(direct) <= 512 or any(char.isspace() for char in direct):
        raise RealDevConfigurationError("Invalid DEEPSEEK_API_KEY format")
    return SecretStr(direct)


def load_runtime_config(
    secret_dir=SECRET_DIR, state_dir=STATE_DIR, budget_dir=BUDGET_DIR
) -> RuntimeConfig:
    if os.environ.get("REAL_AGENT_DEV_ENABLED", "").lower() != "true":
        raise RealDevConfigurationError("REAL_AGENT_DEV_ENABLED=true is required")
    if os.environ.get("EXPERIENCE_MEMORY_MODE", "off").lower() != "off":
        raise RealDevConfigurationError("Real Agent Dev requires EXPERIENCE_MEMORY_MODE=off")
    key = _key()
    endpoint = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    url = urlsplit(endpoint)
    if (
        url.scheme != "https"
        or not url.hostname
        or url.username
        or url.password
        or url.query
        or url.fragment
    ):
        raise RealDevConfigurationError(
            "DEEPSEEK_BASE_URL must be an HTTPS endpoint without credentials"
        )
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", model):
        raise RealDevConfigurationError("Invalid DEEPSEEK_MODEL")
    thinking_mode = os.environ.get("DEEPSEEK_THINKING_MODE", "disabled")
    if thinking_mode not in {"enabled", "disabled"}:
        raise RealDevConfigurationError("Invalid DEEPSEEK_THINKING_MODE")
    limits = BudgetLimits(
        max_requests=_positive("REAL_AGENT_MAX_REQUESTS", integer=True),
        max_tokens=_positive("REAL_AGENT_MAX_TOKENS", integer=True),
        max_usd=_positive("REAL_AGENT_MAX_USD"),
        input_usd_per_million=_positive("REAL_AGENT_INPUT_USD_PER_MILLION"),
        output_usd_per_million=_positive("REAL_AGENT_OUTPUT_USD_PER_MILLION"),
        model=model,
    )
    budget_dir = Path(budget_dir)
    if not budget_dir.is_absolute() or budget_dir.is_symlink() or not budget_dir.is_dir():
        raise RealDevConfigurationError(
            "A dedicated persistent Real Agent budget directory is required"
        )
    settings = runtime_settings(secret_dir, state_dir, scrub_proxy=False).model_copy(
        update=dict(
            deepseek_api_key=key,
            deepseek_base_url=endpoint,
            deepseek_model=model,
            deepseek_thinking_mode=thinking_mode,
            llm_max_retries=1,
            rate_limit_per_minute=60,
        )
    )
    return RuntimeConfig(settings, limits, budget_dir / "budget.sqlite3")


def bootstrap_real(
    secret_dir=SECRET_DIR, state_dir=STATE_DIR, budget_dir=BUDGET_DIR, *, owner_uid=1000
):
    budget_dir = Path(budget_dir)
    if budget_dir.is_symlink():
        raise RealDevConfigurationError("Invalid Real Agent budget directory")
    bootstrap(secret_dir, state_dir, owner_uid=owner_uid)
    budget_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    budget_dir.chmod(0o700)
    if owner_uid is not None:
        os.chown(budget_dir, owner_uid, owner_uid)


def create_application(config: RuntimeConfig, *, transport: httpx.AsyncBaseTransport | None = None):
    app = create_app(config.settings)
    paid_authorized = os.environ.get("REAL_AGENT_PAID_AUTHORIZED", "false").lower() == "true"
    app.state.verification_only = isinstance(transport, httpx.MockTransport)

    @asynccontextmanager
    async def lifespan(application):
        ledger = AttemptLedger(config.budget_path, config.limits)
        ledger.ensure_ready()
        guarded = BudgetedTransport(
            ledger,
            transport,
            allowed_base_url=config.settings.deepseek_base_url,
            dispatch_enabled=paid_authorized,
        )
        from app.core.constants import PROMPT_VERSION_INTENT
        from app.prompts.intent import INTENT_SYSTEM, INTENT_USER

        minimum_payload = dict(
            model=config.settings.deepseek_model,
            messages=[
                {"role": "system", "content": INTENT_SYSTEM},
                {
                    "role": "user",
                    "content": INTENT_USER.format(query="", prompt_version=PROMPT_VERSION_INTENT),
                },
            ],
            temperature=0.0,
            max_tokens=256,
            response_format={"type": "json_object"},
        )
        if config.settings.deepseek_thinking_mode is not None:
            minimum_payload["thinking"] = {"type": config.settings.deepseek_thinking_mode}
        encoded = httpx.Request(
            "POST", "https://api.deepseek.com/chat/completions", json=minimum_payload
        ).content
        minimum_tokens, minimum_usd = _request_reservation(encoded, config.limits)

        def admission_status():
            if not paid_authorized:
                return {"available": False, "reason": "payment_not_authorized"}
            try:
                snapshot = ledger.snapshot()
                if snapshot["pending"] or snapshot["uncertain"]:
                    return {"available": False, "reason": "budget_not_ready"}
                exhausted = (
                    snapshot["requests"] >= config.limits.max_requests
                    or snapshot["tokens"] + minimum_tokens > config.limits.max_tokens
                    or Decimal(snapshot["usd"]) + minimum_usd > config.limits.max_usd
                )
                return {
                    "available": not exhausted,
                    "reason": "budget_exhausted" if exhausted else "ready",
                }
            except Exception:
                return {"available": False, "reason": "budget_not_ready"}

        app.state.real_agent_admission = admission_status
        async with httpx.AsyncClient(
            base_url=config.settings.deepseek_base_url,
            transport=guarded,
            follow_redirects=False,
            timeout=httpx.Timeout(
                connect=3, read=config.settings.llm_timeout_seconds, write=10, pool=5
            ),
        ) as client:
            provider = DeepSeekProvider(config.settings, client=client)
            container = await build_container(config.settings, seed=False, llm_provider=provider)
            try:
                if (
                    container.engine.dialect.name != "postgresql"
                    or container.redis is None
                    or type(container.vector_store).__name__ != "PrivateVectorStore"
                ):
                    raise RealDevConfigurationError(
                        "Required private Real Agent backends are unavailable"
                    )
                application.state.container = container
                yield
            finally:
                await container.aclose()

    app.router.lifespan_context = lifespan
    return app


async def health():
    from app.demo.docker import read_credentials

    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:8000", timeout=2, trust_env=False
    ) as client:
        ready = await client.get("/api/v1/ready")
        caps = await client.get("/api/v1/capabilities")
        readiness = ready.json()
        dependencies = {item["name"]: item["ready"] for item in readiness.get("dependencies", [])}
        expected = {
            "llm": "deepseek",
            "database": "postgresql",
            "cache": "redis",
            "vector_store": "PrivateVectorStore",
        }
        if (
            ready.status_code != 200
            or not readiness.get("ready")
            or not all(dependencies.get(name) for name in ["database", "redis", "vector_store"])
            or caps.status_code != 200
            or any(caps.json().get(name) != value for name, value in expected.items())
        ):
            raise RealDevConfigurationError("Real Agent Dev is not ready")
        token = read_credentials()["tokens"]["a"]
        identity = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + token})
        if identity.status_code != 200 or identity.json().get("subject") != "web_demo_a":
            raise RealDevConfigurationError("Real Agent Dev authentication unavailable")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["bootstrap", "serve", "health", "validate"])
    action = parser.parse_args().action
    try:
        if action == "bootstrap":
            bootstrap_real()
        elif action == "health":
            import asyncio

            asyncio.run(health())
        else:
            config = load_runtime_config()
            if action == "validate":
                AttemptLedger(config.budget_path, config.limits).ensure_ready()
                print("REAL_AGENT_DEV_CONFIG=PASS; no model request performed")
            else:
                import uvicorn

                uvicorn.run(
                    create_application(config),
                    host="0.0.0.0",
                    port=8000,
                    access_log=False,
                    log_level="warning",
                )
    except RealDevConfigurationError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from None
    except Exception:
        print(
            "Real Agent Dev startup or budget check failed; no automatic Offline fallback",
            file=sys.stderr,
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
