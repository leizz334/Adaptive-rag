"""Real DeepSeek isolated experiment worker; production Experience remains off."""

import argparse
import asyncio
import json
import os
import secrets
from contextlib import aclosing, asynccontextmanager
from contextvars import ContextVar
from dataclasses import asdict
from datetime import UTC, datetime

import httpx
from fastapi import Request
from pydantic import SecretStr
from sqlalchemy import event as sql_event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.responses import JSONResponse

from app.config import Settings
from app.experience.contracts import EvidenceRef
from app.experience.isolated import prepare_planner
from app.experience.shadow import EvidenceResolver
from app.experience.storage import ExperienceRepository
from app.main import create_app
from app.observability.execution import capture_tools
from app.observability.tracing import TraceRecorder
from app.prompts.planner import PLANNER_SYSTEM
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

from .common import HERE, RUN, STATE, read, save, scope_for, verify_freeze
from .meter import Ledger, MeteredTransport, SafetyStop

CURRENT = ContextVar("ex_current", default=None)


class ExperienceLLM:
    def __init__(self, provider, repository, registry, permits, resolver, directory):
        (
            self.provider,
            self.repository,
            self.registry,
            self.permits,
            self.resolver,
            self.directory,
        ) = provider, repository, registry, permits, resolver, directory

    async def generate(self, messages, **kwargs):
        context = CURRENT.get()
        if context is None:
            raise SafetyStop("no paid request context")
        if context["arm"] == "E2" and not context.get("eligible_checked"):
            from app.experience.isolated import select_isolated

            admitted = await select_isolated(
                self.repository,
                scope_for(context["session"]),
                context["query"],
                self.registry,
                self.permits,
                resolver=self.resolver,
                isolated=True,
            )
            if not admitted:
                raise SafetyStop("E2 has no qualified experience; no paid dispatch")
            context["eligible_checked"] = True
        prefix = PLANNER_SYSTEM.split("{tools}")[0]
        if (
            messages
            and messages[0].get("role") == "system"
            and messages[0].get("content", "").startswith(prefix)
        ):
            transformed, candidates = await prepare_planner(
                messages,
                arm=context["arm"],
                repository=self.repository,
                scope=scope_for(context["session"]),
                query=context["query"],
                registry=self.registry,
                permits=self.permits,
                resolver=self.resolver,
                isolated=True,
            )
            if context["arm"] == "E2" and not candidates:
                raise SafetyStop("E2 Planner has no qualified experience; no paid dispatch")
            from app.experience.compatibility import digest

            captured = event(
                self.directory,
                "experience_planner",
                arm=context["arm"],
                selected=[
                    {"id": c.experience_id, "family": c.family, "fingerprint": c.fingerprint}
                    for c in candidates
                ],
                injected=len(candidates) if context["arm"] == "E2" else 0,
                before_sha256=digest(messages),
                after_sha256=digest(transformed),
                catalog_unchanged=messages[0] == transformed[0],
            )
            if not captured:
                raise SafetyStop("experience evidence sink failed; no paid Planner dispatch")
            messages = transformed
        return await self.provider.generate(messages, **kwargs)

    async def ping(self):
        return await self.provider.ping()

    async def aclose(self):
        await self.provider.aclose()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--stage", choices=["development", "independent"], required=True)
    args = parser.parse_args()
    directory = RUN / ("worker_" + args.stage)
    directory.mkdir(exist_ok=False)
    verify_freeze()
    manifest, cfg = live_config()
    command(manifest, "ps")
    if not (HERE / "evidence/admission_review.json").exists():
        raise SafetyStop("independent admission review missing")
    if (
        datetime.now(UTC).date().isoformat()
        != read(HERE / "evidence/ex1_provider_preflight.json")["price_verified_utc_date"]
    ):
        raise SafetyStop("price admission date stale")
    key = Settings().deepseek_api_key
    if not key.get_secret_value():
        raise SafetyStop("key absent")
    settings = isolated_settings(directory).model_copy(
        update={
            "database_url": cfg["database_url"],
            "redis_url": cfg["redis_url"],
            "qdrant_url": cfg["qdrant_url"],
            "qdrant_collection": cfg["collection"] + "_ex",
            "knowledge_dir": str(HERE / "corpus"),
            "knowledge_mode": "public",
            "deepseek_api_key": key,
            "deepseek_base_url": "https://api.deepseek.com",
            "deepseek_model": "deepseek-flash",
            "llm_max_retries": 1,
            "llm_timeout_seconds": 45.0,
            "auth_mode": "required",
            "memory_mode": "M2",
            "memory_recent_messages": 8,
            "agent_tracing_enabled": False,
            "mcp_enabled": False,
        }
    )
    registry_value = json.loads(credential_fixture())
    for c in registry_value["credentials"]:
        if c["subject"] == "u_demo":
            c["subject"] = "s1ex_probe_user"
    settings.auth_credentials = SecretStr(json.dumps(registry_value))
    configure_environment(settings)
    ledger = Ledger(RUN)
    ledger.fingerprint = verify_freeze
    client = httpx.AsyncClient(
        base_url="https://api.deepseek.com",
        timeout=45,
        trust_env=False,
        transport=MeteredTransport(ledger),
    )
    provider = DeepSeekProvider(settings, client=client)
    app = create_app(settings)
    lock = asyncio.Lock()

    @asynccontextmanager
    async def lifespan(application):
        container = await build_container(settings)
        assert (
            container.engine.dialect.name == "postgresql"
            and container.redis is not None
            and await container.redis.ping()
        )
        assert (
            type(container.vector_store).__name__ == "QdrantVectorStore"
            and container.vector_store.ping()
        )
        exp_engine = create_async_engine(
            "sqlite+aiosqlite:///" + str(HERE / ".private/experience.sqlite3")
        )

        @sql_event.listens_for(exp_engine.sync_engine, "connect")
        def readonly(connection, record):
            cursor = connection.cursor()
            cursor.execute("PRAGMA query_only=ON")
            cursor.close()

        repository = ExperienceRepository(
            async_sessionmaker(exp_engine, expire_on_commit=False), resolver=EvidenceResolver(STATE)
        )
        permits = {k: EvidenceRef.model_validate(v) for k, v in read(HERE / "permits.json").items()}
        await container.llm.aclose()
        wrapper = ExperienceLLM(
            provider,
            repository,
            container.chat_service.registry,
            permits,
            EvidenceResolver(STATE),
            directory,
        )
        old = container.chat_service
        container.llm = wrapper
        container.chat_service = ChatService(
            settings=settings,
            llm=wrapper,
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
            {
                "database": "postgresql",
                "redis": True,
                "qdrant": True,
                "provider": "DeepSeekProvider",
                "experience": "isolated_Planner_only",
                "mode": "off_in_production",
                "stage": args.stage,
                "retry": 0,
                "max_lessons": 2,
                "read_only_experience_repository": True,
            },
        )
        try:
            yield
        finally:
            await container.aclose()
            await client.aclose()
            await exp_engine.dispose()
            if container.vector_store._client:
                container.vector_store._client.close()

    app.router.lifespan_context = lifespan
    original_chat, original_stream = ChatService.chat, ChatService.stream

    async def chat(service, payload, *, trace_id):
        async with lock:
            ledger.group = CURRENT.get()["group"]
            with capture_tools() as tools:
                try:
                    return await original_chat(service, payload, trace_id=trace_id)
                finally:
                    event(directory, "tools", trace_id=trace_id, calls=tools)

    async def stream(service, payload, *, trace_id):
        async with lock:
            ledger.group = CURRENT.get()["group"]
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
    control = os.environ["EX_CONTROL_TOKEN"]
    tasks = {t["id"]: t for t in read(HERE / "public_tasks.json")}

    @app.middleware("http")
    async def scope(request, call_next):
        if request.url.path not in ["/api/v1/chat", "/api/v1/chat/stream"]:
            return await call_next(request)
        if not secrets.compare_digest(request.headers.get("x-ex-control", ""), control):
            return JSONResponse({"detail": "isolated control required"}, status_code=403)
        from app.core.exceptions import AppError

        try:
            principal = app.state.authenticator.authenticate(
                request.headers.getlist("authorization")
            )
        except AppError as exc:
            return JSONResponse(
                {"error_code": exc.error_code.value, "message": exc.message},
                status_code=exc.http_status,
            )
        if principal is None or principal.subject != "s1ex_probe_user":
            return JSONResponse({"detail": "verified experiment subject required"}, status_code=403)
        case = request.headers.get("x-ex-case", "")
        arm = request.headers.get("x-ex-arm", "")
        if case not in tasks or arm not in ["E0", "E1", "E2"] or tasks[case]["split"] != args.stage:
            return JSONResponse({"detail": "unfrozen task"}, status_code=403)
        payload = await request.json()
        task = tasks[case]
        if (
            payload.get("session_id") != task["sessions"][arm]
            or payload.get("message") != task["query"]
        ):
            return JSONResponse({"detail": "frozen query/session mismatch"}, status_code=403)
        group = case + "_" + arm
        marker = RUN / "http_started" / f"{group}.json"
        marker.parent.mkdir(exist_ok=True)
        try:
            with marker.open("x") as f:
                f.write(json.dumps({"group": group, "status": "STARTED"}))
                f.flush()
                os.fsync(f.fileno())
        except FileExistsError:
            return JSONResponse({"detail": "consumed;no replay"}, status_code=409)
        token = CURRENT.set(
            {"group": group, "arm": arm, "query": task["query"], "session": task["sessions"][arm]}
        )
        case_token = CASE.set(group)
        try:
            return await call_next(request)
        finally:
            CURRENT.reset(token)
            CASE.reset(case_token)

    import uvicorn

    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=args.port, log_level="warning")
    )

    @app.post("/__ex_stop")
    async def stop(request: Request):
        if not secrets.compare_digest(request.headers.get("x-ex-control", ""), control):
            return JSONResponse({"detail": "forbidden"}, status_code=403)
        server.should_exit = True
        return {"stopping": True}

    server.run()


if __name__ == "__main__":
    main()
