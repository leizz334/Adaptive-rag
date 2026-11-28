"""Bounded metadata-only tracing; no serialization of State or model inputs."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import inspect
import logging
import math
import re
import secrets
import time
from contextlib import aclosing, contextmanager, suppress
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from functools import wraps
from typing import get_args
from uuid import uuid4

from anyio import CancelScope

from app.schemas.agent import (
    PlanningReason,
    PlanningStrategy,
    SkillMode,
    WorkflowActionStatus,
    WorkflowStepStatus,
)
from app.schemas.goals import GoalKind

logger = logging.getLogger(__name__)
_active: ContextVar = ContextVar("agent_trace", default=None)
_parent: ContextVar = ContextVar("agent_span", default=None)
_salt = secrets.token_bytes(32)
_NUMERIC = {
    "count",
    "top_k",
    "top_n",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "attempt",
    "cache_hit",
    "usage_known",
    "committed",
    "success",
    "planner_llm_calls",
    "planning_required_goals",
    "planning_covered_goals",
    "planning_deduplicated_calls",
    "planned_tool_count",
    "tool_attempt_count",
    "successful_tool_count",
    "observed_goal_count",
    "missing_goal_count",
    "unavailable_field_count",
    "skill_metadata_count",
    "skill_context_chars",
    "skill_resource_chars",
    "skill_invalid_count",
    "workflow_step_id",
    "workflow_source_step_id",
    "context_tokens",
    "context_candidates",
    "context_dropped",
    "react_round",
}
_TRACE_LABELS = {
    "planning_strategy": frozenset(get_args(PlanningStrategy)),
    "planning_reason": frozenset(get_args(PlanningReason)),
    "skill_mode": frozenset(get_args(SkillMode)),
    "skill_selection_reason": frozenset(
        {
            "no_match",
            "conflict",
            "grounded_goal",
            "grounded_action",
            "grounded_dependency",
            "model_candidate",
            "needs_clarification",
            "load_failed",
            "invalid_workflow",
            "direct_precedence",
            "workflow_disabled",
        }
    ),
    "planner_model_mode": frozenset({"json", "function_calling", "none"}),
    "workflow_step_status": frozenset(get_args(WorkflowStepStatus)),
    "workflow_condition_outcome": frozenset({"true", "false", "unknown", "unavailable"}),
    "workflow_action_status": frozenset(get_args(WorkflowActionStatus)),
    "workflow_error": frozenset({"invalid_plan"}),
    "context_node": frozenset({"intent", "planner", "executor", "answer"}),
    "react_stop_reason": frozenset(
        {
            "evidence_complete",
            "unverified_catalog",
            "tool_budget",
            "repeated_call",
            "invalid_next_step",
            "tool_failed",
            "no_progress",
            "round_limit",
        }
    ),
}
_SKILL_NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_SKILL_RESOURCE = re.compile(r"(?:references|assets)(?:/[a-zA-Z0-9][a-zA-Z0-9_.-]{0,80}){1,4}\Z")
_GOAL_KINDS = frozenset(goal.value for goal in GoalKind)
_TOOL_NAMES = frozenset(
    {
        "get_order",
        "get_order_items",
        "track_shipment",
        "get_refund_status",
        "check_inventory",
        "get_product_detail",
        "search_knowledge",
        "cancel_order",
        "create_return_request",
        "create_refund_request",
        "search_products",
        "recommend_products",
        "get_coupon",
        "get_warranty",
        "escalate_to_human",
        "mcp_store_hours",
        "mcp_warehouse_cutoff",
        "mcp_remote_echo",
    }
)
_TRACE_LISTS = {
    "goal_kinds": _GOAL_KINDS,
    "missing_evidence_kinds": _GOAL_KINDS,
    "planned_tools": _TOOL_NAMES,
    "executed_tools": _TOOL_NAMES,
    "context_sections": frozenset(
        {"entity", "task", "history", "plan", "permissions", "tool_evidence"}
    ),
}


def reference(value: str) -> str:
    return hmac.new(_salt, value.encode(), hashlib.sha256).hexdigest()[:24]


def _is_skill_name(value: object) -> bool:
    return type(value) is str and len(value) <= 64 and bool(_SKILL_NAME.fullmatch(value))


def safe_metadata(metadata: dict) -> dict:
    result = {}
    for key, value in metadata.items():
        if key in _NUMERIC and type(value) in (int, float, bool) and math.isfinite(value):
            result[key] = value
        elif key in _TRACE_LABELS and type(value) is str and value in _TRACE_LABELS[key]:
            result[key] = value
        elif key == "skill_name" and _is_skill_name(value):
            result[key] = value
        elif key in {"skill_candidates", "skill_eligible", "skill_names"} and isinstance(
            value, list | tuple
        ):
            result[key] = [item for item in value[:48] if _is_skill_name(item)]
        elif (
            key in {"skill_resource", "skill_resource_path"}
            and type(value) is str
            and len(value) <= 160
            and _SKILL_RESOURCE.fullmatch(value)
        ):
            result[key] = value
        elif key in _TRACE_LISTS and isinstance(value, list | tuple):
            result[key] = [
                item for item in value[:48] if type(item) is str and item in _TRACE_LISTS[key]
            ]
        elif (
            key in {"app_trace_ref", "session_ref", "user_ref", "request_ref"}
            and isinstance(value, str)
            and re.fullmatch(r"[a-f0-9]{24}", value)
        ):
            result[key] = value
    return result


@dataclass
class Span:
    name: str
    kind: str
    id: str
    root_id: str
    parent_id: str | None
    start_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    end_time: datetime | None = None
    latency_ms: float = 0
    status: str = "running"
    error_type: str | None = None
    metadata: dict = field(default_factory=dict)


def _local_sink(spans):
    for item in spans:
        payload = asdict(item)
        payload["metadata"] = safe_metadata(item.metadata)
        logger.info("agent_span", extra={"agent_span": payload})


class TraceRecorder:
    def __init__(self, *, enabled=False, sink=None, max_spans=256):
        self.enabled = enabled
        self.sink = sink or _local_sink
        self.max_spans = max(1, max_spans)
        self.export_errors = 0
        self.dropped_spans = 0

    @classmethod
    def from_settings(cls, settings):
        sink = None
        if settings.agent_tracing_enabled and settings.agent_tracing_backend == "langsmith":
            from app.observability.langsmith_exporter import LangSmithExporter

            sink = LangSmithExporter(settings)
        return cls(
            enabled=settings.agent_tracing_enabled,
            sink=sink,
            max_spans=settings.agent_trace_max_spans,
        )

    @contextmanager
    def turn(self, *, trace_id, session_id="", user_id="", request_id=""):
        if not self.enabled:
            token = _active.set(None)
            try:
                yield None
            finally:
                _active.reset(token)
            return
        run = {"recorder": self, "spans": [], "root": str(uuid4())}
        token = _active.set(run)
        parent = _parent.set(None)
        try:
            with span("chat.turn", "chain") as root:
                if root:
                    root.metadata.update(
                        {
                            k + "_ref": reference(v)
                            for k, v in {
                                "app_trace": trace_id,
                                "session": session_id,
                                "user": user_id,
                                "request": request_id,
                            }.items()
                            if v
                        }
                    )
                yield root
        finally:
            _parent.reset(parent)
            _active.reset(token)
            try:
                self.sink(run["spans"])
            except Exception:
                self.export_errors += 1
                logger.warning("agent_trace_export_failed")

    def close(self):
        close = getattr(self.sink, "close", None)
        if close:
            close()


@contextmanager
def span(name: str, kind: str = "chain", **metadata):
    run = _active.get()
    if run is None:
        yield None
        return
    if len(run["spans"]) >= run["recorder"].max_spans:
        run["recorder"].dropped_spans += 1
        yield None
        return
    item = Span(name, kind, str(uuid4()), run["root"], _parent.get())
    item.metadata = safe_metadata(metadata)
    if kind == "llm":
        item.metadata["usage_known"] = False
    run["spans"].append(item)
    token = _parent.set(item.id)
    start = time.perf_counter()
    try:
        yield item
        item.status = "ok"
    except (asyncio.CancelledError, GeneratorExit):
        item.status = "cancelled"
        raise
    except BaseException as exc:
        item.status = "error"
        item.error_type = type(exc).__name__
        raise
    finally:
        item.end_time = datetime.now(UTC)
        item.latency_ms = (time.perf_counter() - start) * 1000
        _parent.reset(token)


def traced(name: str, kind: str = "chain"):
    def decorate(fn):
        if inspect.isasyncgenfunction(fn):

            @wraps(fn)
            async def stream(*args, **kwargs):
                with span(name, kind):
                    source = fn(*args, **kwargs)
                    try:
                        async for value in source:
                            yield value
                    finally:
                        await source.aclose()

            return stream
        if inspect.iscoroutinefunction(fn):

            @wraps(fn)
            async def call(*args, **kwargs):
                with span(name, kind, **{k: v for k, v in kwargs.items() if k in _NUMERIC}) as item:
                    result = await fn(*args, **kwargs)
                    if item and isinstance(result, list):
                        item.metadata["count"] = len(result)
                    usage = getattr(result, "usage", None)
                    if item and item.kind == "llm" and usage is not None:
                        item.metadata.update(
                            usage_known=True,
                            prompt_tokens=usage.prompt_tokens,
                            completion_tokens=usage.completion_tokens,
                            total_tokens=usage.total_tokens,
                        )
                    return result

            return call

        @wraps(fn)
        def sync(*args, **kwargs):
            with span(name, kind):
                return fn(*args, **kwargs)

        return sync

    return decorate


def trace_turn(fn):
    def scope(service, args, kwargs):
        from app.observability.logging import request_id_var

        request = args[0] if args else kwargs["request"]
        return service._tracer.turn(
            trace_id=kwargs.get("trace_id", ""),
            session_id=request.session_id or "",
            user_id=request.user_id,
            request_id=request_id_var.get(),
        )

    if inspect.isasyncgenfunction(fn):

        @wraps(fn)
        async def stream(self, *args, **kwargs):
            # ContextVar tokens belong to the producer task, never the task
            # consuming/yielding the HTTP body (which may change on disconnect).
            queue: asyncio.Queue = asyncio.Queue(maxsize=1)
            delivered = asyncio.Event()
            errors = []

            async def produce():
                try:
                    with scope(self, args, kwargs) as root:
                        async with aclosing(fn(self, *args, **kwargs)) as source:
                            async for value in source:
                                if root:
                                    value["root_run_id"] = root.id
                                    if value.get("event") == "answer":
                                        value["data"]["root_run_id"] = root.id
                                        root.metadata["session_ref"] = reference(
                                            value["data"]["session_id"]
                                        )
                                await queue.put(value)
                        await queue.put(None)
                        await delivered.wait()
                except asyncio.CancelledError:
                    raise
                except BaseException as exc:
                    errors.append(exc)
                    await queue.put(None)

            task = asyncio.create_task(produce())
            try:
                while True:
                    value = await queue.get()
                    if value is None:
                        delivered.set()
                        await task
                        if errors:
                            raise errors[0]
                        break
                    yield value
            finally:
                with CancelScope(shield=True):
                    if not task.done():
                        task.cancel()
                    with suppress(asyncio.CancelledError):
                        await task

        return stream

    @wraps(fn)
    async def call(self, *args, **kwargs):
        with scope(self, args, kwargs) as root:
            result = await fn(self, *args, **kwargs)
            if root:
                result.root_run_id = root.id
                root.metadata["session_ref"] = reference(result.session_id)
            return result

    return call
