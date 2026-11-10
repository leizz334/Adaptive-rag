"""Research-only real Uvicorn worker. No production import or paid model path."""

import argparse
import asyncio
import json
import os
import re
import socket
from contextvars import ContextVar
from dataclasses import asdict
from datetime import UTC, datetime
from functools import wraps
from pathlib import Path

from app.config.settings import Settings, clear_settings_cache
from app.core.exceptions import LLMProviderError, LLMTruncationError, ToolExecutionError
from app.observability.execution import capture_tools, record_tool
from app.observability.tracing import TraceRecorder
from app.prompts.answer import ANSWER_SYSTEM
from app.prompts.faithfulness import FAITHFULNESS_SYSTEM
from app.providers.base import LLMResponse
from app.services.chat_service import ChatService
from app.tools.base import Tool
from eval.memory_ablation import ScriptedProvider
from research.docs.agent_engineering_upgrade.p4_api_e2e.manage import HERE, ROOT, save

FAULT = ContextVar("p4_fault", default="none")
CASE = ContextVar("p4_case", default="unlabelled")
CAPTURE_ERRORS = {}


def loopback_address(address):
    return isinstance(address, tuple) and bool(address) and address[0] in {"127.0.0.1", "::1"}


def event(directory, kind, **fields):
    try:
        if FAULT.get() == "trace_error":
            raise OSError("synthetic evidence sink failure")
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / "events.jsonl").open("a", encoding="utf8") as stream:
            stream.write(
                json.dumps(
                    dict(kind=kind, case=CASE.get(), time=datetime.now(UTC).isoformat(), **fields),
                    ensure_ascii=False,
                    default=str,
                )
                + "\n"
            )
        return True
    except Exception:
        key = (
            CASE.get() if CASE.get() in CAPTURE_ERRORS or len(CAPTURE_ERRORS) < 256 else "overflow"
        )
        CAPTURE_ERRORS[key] = CAPTURE_ERRORS.get(key, 0) + 1
        return False


def isolated_settings(directory):
    return Settings(
        _env_file=None,
        app_env="testing",
        memory_mode="M2",
        database_url="sqlite+aiosqlite:///" + (directory.resolve() / "app.sqlite3").as_posix(),
        deepseek_api_key="",
        embedding_api_key="",
        embedding_base_url="",
        redis_url="",
        qdrant_url="",
        local_embedding_enabled=False,
        local_embedding_force=False,
        cross_encoder_enabled=False,
        cross_encoder_force=False,
        unstructured_enabled=False,
        unstructured_force=False,
        mcp_enabled=False,
        mcp_remote_url="",
        agent_tracing_enabled=True,
        agent_tracing_backend="local",
        admin_api_token="p4-synthetic-admin",
        rate_limit_per_minute=10000,
        knowledge_dir=str(ROOT / "knowledge"),
    )


class ControlledLLM:
    def __init__(self, directory):
        self.directory = directory
        self.base = ScriptedProvider()

    async def ping(self):
        return True

    async def generate(self, messages, **kwargs):
        stage = (
            "generate"
            if messages[0]["content"] == ANSWER_SYSTEM
            else "judge"
            if messages[0]["content"] == FAITHFULNESS_SYSTEM
            else "decision"
        )
        event(self.directory, "model_started", stage=stage, fault=FAULT.get())
        try:
            if FAULT.get() == "slow":
                await asyncio.sleep(3)
            if FAULT.get() == "runtime_error":
                raise RuntimeError("synthetic runtime failure")
            if FAULT.get() == "generate_error" and stage == "generate":
                raise LLMProviderError("synthetic generate transport failure")
            if FAULT.get() == "generate_timeout" and stage == "generate":
                raise LLMProviderError("synthetic generate timeout", timeout=True)
            if FAULT.get() == "judge_length" and stage == "judge":
                raise LLMTruncationError()
            if stage == "generate":
                user = messages[-1]["content"]
                evidence = user.split("检索证据：\n", 1)[1].split("\n\n工具结果：", 1)[0]
                tools_text = user.split("工具结果：\n", 1)[1].split("\n\n输出 JSON", 1)[0]
                if tools_text != "(无)":
                    from app.agents.answer_evidence import safe_answer
                    from app.schemas.agent import ToolResult

                    results = [ToolResult.model_validate(x) for x in json.loads(tools_text)]
                    answer = safe_answer(results)
                    chunks = [
                        chunk
                        for result in results
                        if result.success
                        and not result.truncated
                        and result.name == "search_knowledge"
                        for chunk in result.output.get("chunks", [])
                        if isinstance(chunk, dict) and isinstance(chunk.get("content"), str)
                    ]
                    if chunks:
                        answer += "\n政策检索原文（仅政策证据，不是当前订单事实）：\n" + "\n".join(
                            c["content"] for c in chunks[:4]
                        )
                elif evidence != "(无检索结果)":
                    answer = evidence
                else:
                    answer = "您好，请告诉我需要查询的订单或政策。"
                citation_ids = re.findall(r"(?m)^\[([^\]]+)\]", evidence)
                return LLMResponse(
                    json.dumps(
                        dict(answer=answer, citation_chunk_ids=citation_ids, refused=False),
                        ensure_ascii=False,
                    ),
                    model="controlled-http-fixture",
                    finish_reason="stop",
                )
            return await self.base.generate(messages, **kwargs)
        except BaseException as exc:
            event(self.directory, "model_error", stage=stage, error_type=type(exc).__name__)
            raise
        finally:
            event(self.directory, "model_finished", stage=stage)


def configure_environment(settings):
    # Explicitly neutralize every Settings field, including ambient .env-independent keys.
    for name in Settings.model_fields:
        os.environ.pop(name.upper(), None)
    for name in ("LANGCHAIN_TRACING", "LANGCHAIN_TRACING_V2", "LANGSMITH_TRACING"):
        os.environ[name] = "false"
    os.environ["EXPERIENCE_MEMORY_MODE"] = "off"
    for key, value in settings.model_dump().items():
        if hasattr(value, "get_secret_value"):
            value = value.get_secret_value()
        os.environ[key.upper()] = str(value).lower() if isinstance(value, bool) else str(value)
    clear_settings_cache()


def create_worker(directory, stop_token, server_holder):
    from fastapi import Request
    from starlette.responses import JSONResponse

    import app.main as main_module

    settings = isolated_settings(directory)
    configure_environment(settings)
    original_build = main_module.build_container
    original_chat, original_stream = ChatService.chat, ChatService.stream
    original_run = Tool.run

    @wraps(original_chat)
    async def observed_chat(service, request, *, trace_id):
        with capture_tools() as tools:
            try:
                response = await original_chat(service, request, trace_id=trace_id)
                event(
                    directory,
                    "service_response",
                    trace_id=trace_id,
                    response=response.model_dump(mode="json"),
                )
                return response
            except BaseException as exc:
                event(directory, "service_error", trace_id=trace_id, error_type=type(exc).__name__)
                raise
            finally:
                event(directory, "tools", trace_id=trace_id, calls=tools)

    @wraps(original_stream)
    async def observed_stream(service, request, *, trace_id):
        from contextlib import aclosing

        with capture_tools() as tools:
            try:
                async with aclosing(original_stream(service, request, trace_id=trace_id)) as stream:
                    async for item in stream:
                        event(directory, "stream_event", trace_id=trace_id, payload=item)
                        yield item
            except BaseException as exc:
                event(directory, "service_error", trace_id=trace_id, error_type=type(exc).__name__)
                raise
            finally:
                event(directory, "tools", trace_id=trace_id, calls=tools)
                event(directory, "stream_closed", trace_id=trace_id)

    @wraps(original_run)
    async def controlled_tool(tool, arguments, context):
        if FAULT.get() == "tool_error" and tool.name == "get_order":
            record_tool(
                tool.name, arguments, success=False, failure_kind="synthetic_execution_error"
            )
            raise ToolExecutionError("synthetic tool failure")
        return await original_run(tool, arguments, context)

    async def build(settings):
        expected = isolated_settings(directory)
        if (
            settings.database_url != expected.database_url
            or settings.llm_configured
            or not settings.use_sqlite
        ):
            raise RuntimeError("Worker refused unexpected settings/database/provider")
        container = await original_build(settings, seed=True)
        original = container.chat_service
        fixture = ControlledLLM(directory)
        recorder = TraceRecorder(
            enabled=True,
            sink=lambda spans: event(directory, "spans", spans=[asdict(s) for s in spans]),
        )
        service = ChatService(
            settings=settings,
            llm=fixture,
            retriever=container.retriever,
            reranker=original._reranker,
            session_factory=container.session_factory,
            rate_limiter=original._rate_limiter,
            registry=original.registry,
            tracer=recorder,
        )
        container.llm, container.chat_service = fixture, service
        save(
            directory / "startup.json",
            dict(
                pid=os.getpid(),
                ppid=os.getppid(),
                python=os.sys.executable,
                database_url=settings.database_url,
                actual_engine_url=str(container.engine.url),
                provider=type(container.llm).__name__,
                model="controlled-http-fixture",
                original_provider=type(original._llm).__name__,
                retriever=type(container.retriever).__name__,
                vector_store=type(container.vector_store).__name__,
                reranker=type(original._reranker._provider).__name__,
                memory="M2",
                redis=False,
                qdrant=False,
                local_embedding=False,
                paid_api=False,
                external_tracing=False,
                experience_mode="off",
                backend_fallbacks="Explicit synthetic hashing/lexical/in-memory retrieval; no real dense/reranker service",
            ),
        )
        return container

    ChatService.chat, ChatService.stream, Tool.run = observed_chat, observed_stream, controlled_tool
    main_module.build_container = build
    app = main_module.create_app(settings)

    @app.middleware("http")
    async def test_context(request: Request, call_next):
        case = request.headers.get("x-p4-case", "unlabelled")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", case):
            return JSONResponse(dict(error="invalid synthetic case label"), status_code=400)
        a, b = CASE.set(case), FAULT.set(request.headers.get("x-p4-fault", "none"))
        try:
            response = await call_next(request)
            event(
                directory,
                "http",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
            )
            response.headers["x-p4-capture-status"] = "ERROR" if CAPTURE_ERRORS.get(case) else "OK"
            return response
        finally:
            CASE.reset(a)
            FAULT.reset(b)

    @app.post("/__p4/stop", include_in_schema=False)
    async def stop(request: Request):
        import hmac

        if not hmac.compare_digest(request.headers.get("x-p4-owner", ""), stop_token):
            return JSONResponse(dict(error="denied"), status_code=403)
        server_holder["server"].should_exit = True
        return dict(stopping_owned_process=os.getpid())

    return app


def main():
    import uvicorn

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    directory = args.run_dir.resolve()
    if (
        not directory.is_relative_to((HERE / "runs").resolve())
        or (directory / "app.sqlite3").exists()
    ):
        raise ValueError("Fresh owned phase directory required; never reuse business DB")
    original_connect, original_connect_ex = socket.socket.connect, socket.socket.connect_ex

    def denied(sock, address):
        if loopback_address(address):
            return original_connect(sock, address)
        event(directory, "outbound_denied")
        raise RuntimeError("Outbound sockets forbidden in mock-model HTTP E2E worker")

    def denied_ex(sock, address):
        if loopback_address(address):
            return original_connect_ex(sock, address)
        event(directory, "outbound_denied")
        raise RuntimeError("Outbound sockets forbidden in mock-model HTTP E2E worker")

    socket.socket.connect = denied
    socket.socket.connect_ex = denied_ex
    holder = {}
    app = create_worker(directory, os.environ.pop("P4_CONTROL_TOKEN"), holder)
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=args.port, log_level="warning", access_log=False)
    )
    holder["server"] = server
    try:
        server.run()
    finally:
        save(
            directory / "shutdown.json",
            dict(pid=os.getpid(), owned_worker_finished=True, capture_errors=CAPTURE_ERRORS),
        )


if __name__ == "__main__":
    main()
