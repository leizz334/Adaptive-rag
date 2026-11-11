"""One real DeepSeek process, owned infrastructure, local synthetic evidence only."""

import argparse
import os
import secrets
from contextlib import aclosing, asynccontextmanager
from dataclasses import asdict

import httpx
from fastapi import Request
from starlette.responses import JSONResponse

from app.config.settings import Settings
from app.main import create_app
from app.observability.execution import capture_tools
from app.observability.tracing import TraceRecorder
from app.providers.deepseek import DeepSeekProvider
from app.services.chat_service import ChatService
from app.services.container import build_container
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

from .common import HERE, RUN, verify_freeze
from .meter import Ledger, MeteredTransport, write


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--label", choices=["health", "pilot", "test"], required=True)
    args = parser.parse_args()
    directory = RUN / ("worker_" + args.label)
    directory.mkdir(exist_ok=False)
    frozen = verify_freeze()
    manifest, cfg = live_config()
    command(manifest, "ps")
    key = Settings().deepseek_api_key
    if not key.get_secret_value():
        raise RuntimeError("DeepSeek key absent")
    settings = isolated_settings(directory).model_copy(
        update=dict(
            database_url=cfg["database_url"],
            redis_url=cfg["redis_url"],
            qdrant_url=cfg["qdrant_url"],
            qdrant_collection=cfg["collection"] + "_c",
            deepseek_api_key=key,
            deepseek_model=frozen["model"],
            deepseek_base_url="https://api.deepseek.com",
            llm_max_retries=1,
            llm_timeout_seconds=45.0,
            auth_mode="required",
            knowledge_dir=str(HERE / "corpus"),
        )
    )
    from pydantic import SecretStr

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
        container = await build_container(settings, seed=False)
        try:
            assert container.engine.dialect.name == "postgresql"
            assert container.redis is not None and await container.redis.ping()
            assert (
                type(container.vector_store).__name__ == "QdrantVectorStore"
                and container.vector_store.ping()
            )
            assert type(container.retriever._cache).__name__ == "RedisRetrievalCache"
            old = container.chat_service
            await container.llm.aclose()
            container.llm = provider
            container.chat_service = ChatService(
                settings=settings,
                llm=provider,
                retriever=container.retriever,
                reranker=old._reranker,
                session_factory=container.session_factory,
                rate_limiter=old._rate_limiter,
                registry=old.registry,
                tracer=TraceRecorder(
                    enabled=True,
                    sink=lambda spans: event(directory, "spans", spans=[asdict(s) for s in spans]),
                ),
            )
            application.state.container = container
            write(
                directory / "startup.json",
                dict(
                    pid=os.getpid(),
                    database="postgresql",
                    redis=True,
                    qdrant=True,
                    cache="RedisRetrievalCache",
                    provider="PRODUCTION_DeepSeekProvider_metered",
                    model=settings.deepseek_model,
                    provider_retries=1,
                    transport_retries=0,
                    concurrency=1,
                    auth="required",
                    memory="M2",
                    embedding="deterministic_hash_NOT_BGE",
                    reranker="lexical_NOT_CROSSENCODER",
                    active=False,
                    external_tracing=False,
                ),
            )
            yield
        finally:
            await container.aclose()
            await client.aclose()
            if container.vector_store._client:
                container.vector_store._client.close()

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

    @app.middleware("http")
    async def scoped(request, call_next):
        name = request.headers.get("x-p4-case", "free-health")
        token = CASE.set(name)
        ledger.group = name
        try:
            return await call_next(request)
        finally:
            CASE.reset(token)

    import uvicorn

    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=args.port, log_level="warning")
    )
    control = os.environ["P4C_CONTROL_TOKEN"]

    @app.post("/__p4c_stop")
    async def stop(request: Request):
        if not secrets.compare_digest(request.headers.get("x-p4-control", ""), control):
            return JSONResponse({"detail": "forbidden"}, status_code=403)
        server.should_exit = True
        return {"stopping": True}

    server.run()


if __name__ == "__main__":
    main()
