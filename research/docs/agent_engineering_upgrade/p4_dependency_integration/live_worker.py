"""B3-only actual dependency Uvicorn worker with bounded synthetic model and local trace."""

import argparse
import os
import secrets
import socket
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from fastapi import Request
from starlette.responses import JSONResponse

from app.main import create_app
from app.observability.execution import capture_tools
from app.observability.tracing import TraceRecorder
from app.services.chat_service import ChatService
from app.services.container import build_container
from research.docs.agent_engineering_upgrade.p4_api_e2e.worker import (
    CASE,
    FAULT,
    ControlledLLM,
    configure_environment,
    event,
    isolated_settings,
)

from .manage import HERE, save
from .sandbox import command, live_config
from .worker import credential_fixture


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    directory = args.run_dir.resolve()
    if not directory.is_relative_to((HERE / "runs").resolve()) or not directory.is_dir():
        raise ValueError("owned run directory required")
    manifest, cfg = live_config()
    command(manifest, "ps")
    settings = isolated_settings(directory).model_copy(
        update=dict(
            database_url=cfg["database_url"],
            redis_url=cfg["redis_url"],
            qdrant_url=cfg["qdrant_url"],
            qdrant_collection=cfg["collection"] + "_api",
            auth_mode="required",
        )
    )
    from pydantic import SecretStr

    settings.auth_credentials = SecretStr(credential_fixture())
    configure_environment(settings)
    # Even an accidental provider switch cannot contact a paid/external endpoint.
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def check(address):
        if not isinstance(address, tuple) or address[0] not in {"127.0.0.1", "::1"}:
            raise OSError("integration worker forbids external network")

    def connect(sock, address):
        check(address)
        return original_connect(sock, address)

    def connect_ex(sock, address):
        check(address)
        return original_connect_ex(sock, address)

    socket.socket.connect, socket.socket.connect_ex = connect, connect_ex
    app = create_app(settings)

    @asynccontextmanager
    async def lifespan(application):
        container = await build_container(settings, seed=False)
        try:
            if (
                container.engine.dialect.name != "postgresql"
                or container.redis is None
                or type(container.vector_store).__name__ != "QdrantVectorStore"
                or type(container.retriever._cache).__name__ != "RedisRetrievalCache"
            ):
                raise RuntimeError("real dependency missing or silently degraded")
            assert await container.redis.ping() and container.vector_store.ping()
            old = container.chat_service
            llm = ControlledLLM(directory)
            container.llm = llm
            container.chat_service = ChatService(
                settings=settings,
                llm=llm,
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
            save(
                directory / "startup.json",
                dict(
                    pid=os.getpid(),
                    database="postgresql",
                    redis="Redis",
                    vector="QdrantVectorStore",
                    cache="RedisRetrievalCache",
                    auth="required_production_verifier",
                    memory="M2",
                    provider="CONTROLLED_MOCK_NOT_DEEPSEEK",
                    paid_requests=0,
                    active=False,
                    project=cfg["project"],
                ),
            )
            yield
        finally:
            await container.aclose()
            if container.vector_store._client:
                container.vector_store._client.close()

    app.router.lifespan_context = lifespan

    # Streaming middleware alone cannot safely retain ContextVars through body streaming;
    # wrappers live inside the actual ChatService iteration instead.
    original_chat, original_stream = ChatService.chat, ChatService.stream

    async def chat(service, payload, *, trace_id):
        with capture_tools() as tools:
            try:
                response = await original_chat(service, payload, trace_id=trace_id)
                event(
                    directory,
                    "service_response",
                    trace_id=trace_id,
                    response=response.model_dump(mode="json"),
                )
                return response
            finally:
                event(directory, "tools", trace_id=trace_id, calls=tools)

    async def stream(service, payload, *, trace_id):
        from contextlib import aclosing

        with capture_tools() as tools:
            try:
                async with aclosing(
                    original_stream(service, payload, trace_id=trace_id)
                ) as iterator:
                    async for value in iterator:
                        event(directory, "stream_event", trace_id=trace_id, payload=value)
                        yield value
            finally:
                event(directory, "tools", trace_id=trace_id, calls=tools)
                event(directory, "stream_closed", trace_id=trace_id)

    ChatService.chat, ChatService.stream = chat, stream

    @app.middleware("http")
    async def faults(request, call_next):
        case = CASE.set(request.headers.get("x-p4-case", "unlabelled"))
        fault = FAULT.set(request.headers.get("x-p4-fault", "none"))
        try:
            return await call_next(request)
        finally:
            FAULT.reset(fault)
            CASE.reset(case)

    import uvicorn

    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=args.port, log_level="warning")
    )
    control = os.environ["P4_CONTROL_TOKEN"]

    @app.post("/__p4b_owned_stop")
    async def stop(request: Request):
        if not secrets.compare_digest(request.headers.get("x-p4-control", ""), control):
            return JSONResponse({"detail": "forbidden"}, status_code=403)
        server.should_exit = True
        return {"stopping": True}

    server.run()


if __name__ == "__main__":
    main()
