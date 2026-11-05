"""Tool execution node with argument fallback and retries."""

from __future__ import annotations

import hashlib
import json
import time

from app.agents.state import AgentState
from app.config.settings import Settings
from app.core.enums import ToolRisk
from app.core.exceptions import (
    AppError,
    InvalidRequestError,
    ToolExecutionError,
    ToolPermissionError,
)
from app.core.request_scope import get_db_session
from app.observability.execution import record_tool
from app.observability.metrics import TOOL_CALLS
from app.observability.tracing import traced
from app.repositories.idempotency import IdempotencyRepository
from app.schemas.agent import PlanStep, ToolResult
from app.schemas.common import LatencyBreakdown
from app.tools.base import Tool, ToolContext
from app.tools.permissions import WRITE_RISKS, assert_permitted
from app.tools.registry import ToolRegistry

READ_FALLBACKS: dict[str, list[str]] = {
    "get_order": ["search_knowledge"],
    "get_order_items": ["get_order", "search_knowledge"],
    "track_shipment": ["get_order", "search_knowledge"],
    "get_product_detail": ["search_products", "search_knowledge"],
    "search_products": ["search_knowledge"],
    "recommend_products": ["search_products", "search_knowledge"],
    "get_coupon": ["search_knowledge"],
    "get_warranty": ["search_knowledge"],
    "get_refund_status": ["search_knowledge"],
    "check_inventory": ["search_products", "search_knowledge"],
    "mcp_store_hours": ["search_knowledge"],
    "mcp_warehouse_cutoff": ["search_knowledge"],
}


def _fingerprint(tool_name: str, arguments: dict) -> str:
    payload = json.dumps(
        {"tool": tool_name, "arguments": arguments}, sort_keys=True, ensure_ascii=False
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def fallback_arguments(tool_name: str, step: PlanStep, query: str) -> dict:
    if tool_name == "search_knowledge":
        return {"query": query[:200]}
    if tool_name in {"search_products", "recommend_products"}:
        return {"query": (step.arguments.get("query") or query)[:80]}
    return dict(step.arguments)


async def execute_with_fallback(
    tool: Tool,
    step: PlanStep,
    context: ToolContext,
    registry: ToolRegistry,
    query: str,
    *,
    read_cache: dict[str, ToolResult] | None = None,
) -> ToolResult:
    """Execution-layer fallback: a failed read tool tries the next mapped tool."""

    async def observe(candidate: Tool, arguments: dict) -> ToolResult:
        key = _fingerprint(candidate.name, arguments)
        if read_cache is not None and candidate.risk == ToolRisk.READ and key in read_cache:
            return read_cache[key]
        value = await candidate.run(arguments, context)
        if read_cache is not None and candidate.risk == ToolRisk.READ and value.success:
            read_cache[key] = value
        return value

    try:
        result = await observe(tool, step.arguments)
        if result.success:
            return result
        raise ToolExecutionError(result.error or f"{tool.name} returned success=false")
    except (ToolPermissionError, InvalidRequestError):
        # A deterministic business/argument rejection cannot be repaired by
        # asking another tool for the same protected entity.
        raise
    except AppError as exc:
        last_error = str(exc)
        for fallback_name in READ_FALLBACKS.get(tool.name, []):
            if fallback_name not in registry.names():
                continue
            fallback = registry.get(fallback_name)
            try:
                arguments = fallback_arguments(fallback_name, step, query)
                reused = (
                    read_cache is not None
                    and fallback.risk == ToolRisk.READ
                    and _fingerprint(fallback.name, arguments) in read_cache
                )
                fb_result = await observe(fallback, arguments)
                if fb_result.success:
                    merged = {
                        **fb_result.output,
                        "fallback_from": tool.name,
                        "fallback_error": last_error,
                    }
                    if not reused:
                        TOOL_CALLS.labels(tool=fallback_name, status="fallback").inc()
                    return fb_result.model_copy(update={"output": merged})
            except (ToolPermissionError, InvalidRequestError):
                raise
            except AppError:
                continue
        raise


@traced("node.executor", "chain")
async def executor_node(
    state: AgentState,
    *,
    registry: ToolRegistry,
    settings: Settings,
) -> dict:
    plan = state.get("plan")
    if plan is None:
        return {"tool_results": []}
    if state.get("pending_action") and not state.get("confirm_action_id"):
        return {"tool_results": []}

    started = time.perf_counter()
    results: list[ToolResult] = []
    context = ToolContext(
        user_id=state["user_id"],
        session_id=state["session_id"],
        trace_id=state["trace_id"],
        confirmed_action_id=state.get("confirm_action_id"),
        idempotency_key=state.get("idempotency_key"),
    )
    idempotency = IdempotencyRepository(get_db_session())
    calls = 0
    seen_reads: set[str] = set()
    read_cache: dict[str, ToolResult] = {}
    hidden_orders: set[str] = set()
    query = state["user_query"]
    for step in plan.steps:
        if (
            calls >= settings.max_tool_calls
            or (state.get("step_count") or 0) >= settings.max_agent_steps
        ):
            break
        if not step.tool_name:
            continue
        tool = registry.get(step.tool_name)
        read_key = _fingerprint(tool.name, step.arguments)
        order_id = step.arguments.get("order_id")
        if tool.risk != ToolRisk.READ:
            # Even an attempted write is a freshness barrier. Writes retain the
            # existing confirmation/idempotency path and are never deduplicated.
            seen_reads.clear()
            read_cache.clear()
        elif read_key in seen_reads or (isinstance(order_id, str) and order_id in hidden_orders):
            continue
        confirmed = bool(state.get("confirm_action_id"))
        try:
            if tool.risk in WRITE_RISKS:
                assert_permitted(tool, confirmed=confirmed)
                idem_key = context.confirmed_action_id or context.idempotency_key
                if idem_key:
                    fp = _fingerprint(tool.name, step.arguments)
                    existing = await idempotency.get_if_matches(idem_key, fp)
                    if existing is not None:
                        record_tool(tool.name, step.arguments, status="replayed", output=existing)
                        results.append(
                            ToolResult(
                                name=tool.name, success=True, output=existing, risk=tool.risk
                            )
                        )
                        TOOL_CALLS.labels(tool=tool.name, status="idempotent").inc()
                        calls += 1
                        continue
                    result = await tool.run(step.arguments, context)
                    await idempotency.put(idem_key, fp, result.output)
                    TOOL_CALLS.labels(tool=tool.name, status="ok").inc()
                    results.append(result)
                    calls += 1
                    continue
            result = await execute_with_fallback(
                tool, step, context, registry, query, read_cache=read_cache
            )
            if tool.risk == ToolRisk.READ and result.success:
                # Cache only the capability that actually produced evidence;
                # a fallback to order headers does not satisfy shipment events.
                seen_reads.add(
                    _fingerprint(
                        result.name,
                        step.arguments
                        if result.name == tool.name
                        else fallback_arguments(result.name, step, query),
                    )
                )
            TOOL_CALLS.labels(tool=tool.name, status="ok").inc()
            results.append(result)
        except ToolPermissionError as exc:
            if tool.risk == ToolRisk.READ:
                seen_reads.add(read_key)
            record_tool(
                tool.name,
                step.arguments,
                success=False,
                status="denied",
                failure_kind="permission_denied",
            )
            TOOL_CALLS.labels(tool=tool.name, status="denied").inc()
            results.append(
                ToolResult(name=tool.name, success=False, error=str(exc), risk=tool.risk)
            )
        except AppError as exc:
            if tool.risk == ToolRisk.READ and isinstance(exc, InvalidRequestError):
                seen_reads.add(read_key)
                # get_visible_order deliberately hides both missing and foreign
                # orders with this exact contract. Other argument/business
                # errors must not block a different read capability.
                if isinstance(order_id, str) and exc.message == f"order not found: {order_id}":
                    hidden_orders.add(order_id)
            if exc.error_code.value == "IDEMPOTENCY_CONFLICT":
                TOOL_CALLS.labels(tool=tool.name, status="conflict").inc()
            else:
                TOOL_CALLS.labels(tool=tool.name, status="error").inc()
            results.append(
                ToolResult(name=tool.name, success=False, error=str(exc), risk=tool.risk)
            )
        calls += 1
    latency = state.get("latency") or LatencyBreakdown()
    latency.tool_ms = (time.perf_counter() - started) * 1000
    return {
        "tool_results": results,
        "step_count": (state.get("step_count") or 0) + calls,
        "latency": latency,
    }
