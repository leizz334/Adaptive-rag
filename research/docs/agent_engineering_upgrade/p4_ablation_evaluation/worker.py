"""Owned real-dependency Uvicorn worker with frozen research-only arm selection."""

import argparse
import os
import secrets
from contextlib import aclosing, asynccontextmanager
from dataclasses import asdict

import httpx
from fastapi import Request
from pydantic import SecretStr
from starlette.responses import JSONResponse

from app.config.settings import Settings
from app.infra.rate_limit import RedisRateLimiter
from app.main import create_app
from app.observability.execution import capture_tools
from app.observability.tracing import TraceRecorder
from app.providers.deepseek import DeepSeekProvider
from app.services.chat_service import ChatService
from app.services.container import AppContainer, build_infrastructure
from app.tools.factory import build_tool_registry
from research.docs.agent_engineering_upgrade.p4_api_e2e.worker import (
    CASE,
    configure_environment,
    event,
    isolated_settings,
)
from research.docs.agent_engineering_upgrade.p4_dependency_integration.sandbox import (
    command,
    live_config,
)
from research.docs.agent_engineering_upgrade.p4_dependency_integration.worker import (
    credential_fixture,
)

from .common import ARM, RUN, verify_freeze
from .meter import Ledger, MeteredTransport, write
from .retrieval import build


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--stage", choices=["baseline", "pairs"], required=True)
    args = parser.parse_args()
    directory = RUN / ("worker_" + args.stage)
    directory.mkdir(exist_ok=False)
    verify_freeze()
    manifest, cfg = live_config()
    command(manifest, "ps")
    key = Settings().deepseek_api_key
    if not key.get_secret_value():
        raise RuntimeError("key absent")
    settings = isolated_settings(directory).model_copy(
        update=dict(
            database_url=cfg["database_url"],
            redis_url=cfg["redis_url"],
            qdrant_url=cfg["qdrant_url"],
            deepseek_api_key=key,
            deepseek_base_url="https://api.deepseek.com",
            deepseek_model="deepseek-flash",
            llm_max_retries=1,
            llm_timeout_seconds=45.0,
            auth_mode="required",
            memory_mode="M2",
            memory_recent_messages=4,
            retrieval_top_k_simple=3,
            retrieval_top_k_complex=3,
            rerank_top_n=3,
        )
    )
    settings.auth_credentials = SecretStr(credential_fixture())
    configure_environment(settings)
    ledger = Ledger(RUN)
    ledger.fingerprint = verify_freeze
    client = httpx.AsyncClient(
        base_url="https://api.deepseek.com",
        timeout=45,
        transport=MeteredTransport(ledger),
        trust_env=False,
    )
    provider = DeepSeekProvider(settings, client=client)
    app = create_app(settings)

    @asynccontextmanager
    async def lifespan(application):
        engine, factory, redis = await build_infrastructure(settings)
        assert engine.dialect.name == "postgresql" and redis is not None and await redis.ping()
        retriever, reranker, store, modelmetrics = await build(cfg, real=args.stage == "pairs")
        service = ChatService(
            settings=settings,
            llm=provider,
            retriever=retriever,
            reranker=reranker,
            session_factory=factory,
            rate_limiter=RedisRateLimiter(redis, limit=10000),
            registry=build_tool_registry(retriever),
            tracer=TraceRecorder(
                enabled=True,
                sink=lambda spans: event(directory, "spans", spans=[asdict(s) for s in spans]),
            ),
        )
        container = AppContainer(
            settings, provider, service, engine, factory, retriever, redis=redis, vector_store=store
        )
        application.state.container = container
        write(
            directory / "startup.json",
            dict(
                database="postgresql",
                redis=True,
                qdrant=True,
                provider="DeepSeekProvider",
                model="deepseek-flash",
                thinking=False,
                retries=0,
                model_metrics=modelmetrics,
                stage=args.stage,
                active=False,
                models_required=args.stage == "pairs",
            ),
        )
        try:
            yield
        finally:
            await container.aclose()
            await client.aclose()
            if store._client:
                store._client.close()

    app.router.lifespan_context = lifespan
    original_chat, original_stream = ChatService.chat, ChatService.stream

    async def chat(service, payload, *, trace_id):
        with capture_tools() as tools:
            try:
                return await original_chat(service, payload, trace_id=trace_id)
            finally:
                event(directory, "tools", trace_id=trace_id, calls=tools)

    async def stream(service, payload, *, trace_id):
        with capture_tools() as tools:
            try:
                async with aclosing(
                    original_stream(service, payload, trace_id=trace_id)
                ) as iterator:
                    async for item in iterator:
                        yield item
            finally:
                event(directory, "tools", trace_id=trace_id, calls=tools)

    ChatService.chat, ChatService.stream = chat, stream
    control = os.environ["P4D_CONTROL_TOKEN"]

    @app.middleware("http")
    async def arm_scope(request, call_next):
        if request.url.path.startswith("/api/v1/chat") and not secrets.compare_digest(
            request.headers.get("x-p4-control", ""), control
        ):
            return JSONResponse({"error": "missing experiment controller"}, status_code=403)
        arm = request.headers.get("x-p4-arm", "BASE")
        group = request.headers.get("x-p4-case", "baseline")
        if arm not in ["BASE", "M0", "M1", "M2", "BM25", "DENSE", "HYBRID", "RERANK"]:
            return JSONResponse({"error": "invalid arm"}, status_code=400)
        token = ARM.set(arm)
        case = CASE.set(group)
        settings.memory_mode = arm if arm in ["M0", "M1", "M2"] else "M2"
        ledger.group = group
        try:
            return await call_next(request)
        finally:
            CASE.reset(case)
            ARM.reset(token)

    import uvicorn

    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=args.port, log_level="warning")
    )

    @app.post("/__p4d_stop")
    async def stop(request: Request):
        if not secrets.compare_digest(request.headers.get("x-p4-control", ""), control):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        server.should_exit = True
        return {"stopping": True}

    server.run()


if __name__ == "__main__":
    main()
