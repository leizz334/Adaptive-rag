"""Synthetic offline observations of unchanged production nodes and original scorers.

This module patches references only inside a scoped, sequential evaluation. It does
not implement graph logic, provider decisions, or scoring. New traces are source
frozen re-executions, never reconstructed historical traces. Gold is supplied only
to the existing run_scenarios evaluator, never to a service or provider.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import subprocess
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from functools import wraps
from pathlib import Path
from unittest.mock import patch

from pydantic import BaseModel
from sqlalchemy import select

import app.agents.graph as graph
from app.core.exceptions import AppError
from app.providers.fake import OfflineLLMProvider
from app.repositories.models import Base
from app.services.chat_service import ChatService
from eval.environment import BusinessEnvironment
from eval.memory_ablation import ScriptedProvider
from eval.multiturn import load_scenarios, run_scenarios

ROOT = Path(__file__).resolve().parents[4]
ORIGIN = "SOURCEFROZEN_REEXECUTION"
ACTIVE_TURN = ContextVar("p2r_active_turn", default=None)
STATE_FIELDS = frozenset(
    "trace_id session_id user_id user_query resolved_query selected_context messages summary "
    "memory_managed memory_preferences intent complexity strategy query_complexity rewritten_queries "
    "retrieved_chunks plan tool_results pending_action confirmed_action confirm_action_id "
    "idempotency_key final_answer citations refused error step_count token_usage latency".split()
)
EXCLUDED = frozenset(
    "rationale reasoning reasoning_content chain_of_thought authorization api_key "
    "deepseek_api_key embedding_api_key password secret".split()
)
NODES = {
    "guardrail_node": "apply_guardrail",
    "intent_node": "classify_intent",
    "router_node": "route_complexity",
    "retrieval_node": "retrieve_docs",
    "planner_node": "plan_tasks",
    "executor_node": "execute_tools",
    "generate_node": "generate_answer",
    "refuse_node": "refuse_answer",
    "faithfulness_node": "check_faithfulness",
    "memory_node": "compact_memory",
}


def safe_value(value):
    """Serialize approved synthetic state types; never introspect arbitrary objects."""
    if isinstance(value, Enum):
        return safe_value(value.value)
    if value is None or isinstance(value, str | bool | int | float):
        return value
    if isinstance(value, date | datetime):
        return value.isoformat()
    if isinstance(value, BaseModel) and type(value).__module__.startswith("app.schemas."):
        return {
            name: safe_value(getattr(value, name))
            for name in type(value).model_fields
            if name.lower() not in EXCLUDED
        }
    if is_dataclass(value) and type(value).__module__ == "app.memory.context":
        return {field.name: safe_value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("Evidence dictionaries require string keys")
        return {k: safe_value(v) for k, v in value.items() if k.lower() not in EXCLUDED}
    if isinstance(value, list | tuple):
        return [safe_value(item) for item in value]
    raise TypeError(f"Unsupported evidence type: {type(value).__name__}")


def state_value(state):
    return safe_value({key: value for key, value in state.items() if key in STATE_FIELDS})


def error_value(exc):
    return {
        "type": type(exc).__name__,
        "code": exc.error_code.value if isinstance(exc, AppError) else None,
    }


@contextmanager
def offline_network():
    """Block socket connections including DNS and restore them on all exits."""

    def blocked(*args, **kwargs):
        raise AssertionError("Network forbidden in offline runtime evidence")

    with ExitStack() as stack:
        for target in (
            "socket.socket.connect",
            "socket.socket.connect_ex",
            "socket.create_connection",
            "socket.getaddrinfo",
        ):
            stack.enter_context(patch(target, side_effect=blocked))
        yield


def observe_node(name, function):
    @wraps(function)
    async def wrapped(state, *args, **kwargs):
        turn = ACTIVE_TURN.get()
        if turn is None:
            return await function(state, *args, **kwargs)
        record = {"sequence": len(turn["nodes"]), "node": name, "input": state_value(state)}
        turn["nodes"].append(record)
        try:
            output = await function(state, *args, **kwargs)
        except Exception as exc:
            record["error"] = error_value(exc)
            raise
        record["output"] = state_value(output)
        return output

    return wrapped


async def database_value(env):
    # BusinessEnvironment.snapshot remains the exact business oracle input. The
    # additional tables preserve committed sessions/messages/idempotency too.
    result = {"business": await BusinessEnvironment.snapshot(env), "tables": {}}
    async with env.container.session_factory() as db:
        for table in sorted(Base.metadata.tables.values(), key=lambda table: table.name):
            rows = await db.execute(select(table).order_by(*table.primary_key.columns))
            result["tables"][table.name] = [safe_value(dict(row)) for row in rows.mappings()]
    return safe_value(result)


def pending_value(service):
    return {
        key: {
            "session_id": value.session_id,
            "user_id": value.user_id,
            "action": safe_value(value.action),
        }
        for key, value in service._pending_actions.items()
    }


async def evaluate_cases(
    cases, *, dataset_sha256, mode="M2", provider="scripted", llm_factory=None
):
    """Reusable evaluator for synthetic cases. Calls the original scorer unchanged.

    Run sequentially: graph references are patched process-wide during the scope,
    while node callbacks are isolated by ContextVar per actual service turn.
    """
    if mode != "M2" or provider not in {"scripted", "rule", "replay"}:
        raise ValueError(
            "Runtime evidence supports M2 and offline scripted/rule/replay providers only"
        )
    if (provider == "replay") != (llm_factory is not None):
        raise ValueError("An external llm_factory is required exclusively for offline replay")
    all_results, traces = [], []
    initial_state = ChatService._initial_state
    invoke = ChatService._invoke
    chat = ChatService.chat

    @wraps(initial_state)
    async def capture_initial(service, *args, **kwargs):
        value = await initial_state(service, *args, **kwargs)
        if (turn := ACTIVE_TURN.get()) is not None:
            turn["initial_state"] = state_value(value)
        return value

    @wraps(invoke)
    async def capture_invoke(service, state):
        value = await invoke(service, state)
        if (turn := ACTIVE_TURN.get()) is not None:
            turn["final_state"] = state_value(value)
        return value

    with ExitStack() as scope:
        scope.enter_context(offline_network())
        for attribute, node_name in NODES.items():
            scope.enter_context(
                patch.object(graph, attribute, observe_node(node_name, getattr(graph, attribute)))
            )
        scope.enter_context(patch.object(ChatService, "_initial_state", capture_initial))
        scope.enter_context(patch.object(ChatService, "_invoke", capture_invoke))
        for case in cases:
            trace = {"case_id": case.id, "evidence_origin": ORIGIN, "turns": []}
            traces.append(trace)

            class ObservedEnvironment(BusinessEnvironment):
                _trace = trace

                async def __aenter__(self):
                    await super().__aenter__()
                    self.service._p2r_environment = self
                    settings = self.container.settings
                    self._trace["runtime_settings"] = {
                        key: safe_value(getattr(settings, key))
                        for key in type(settings).model_fields
                        if key.startswith(("memory_", "agent_", "retrieval_", "llm_"))
                        and not any(part in key for part in ("key", "url", "path", "model"))
                    }
                    self._trace["runtime_settings"].update(
                        database="isolated_sqlite_in_memory",
                        provider=type(self.service._llm).__name__,
                    )
                    self._trace["database_initial"] = await database_value(self)
                    return self

                async def __aexit__(self, *args):
                    try:
                        self._trace["database_final"] = await database_value(self)
                    finally:
                        await super().__aexit__(*args)

            @wraps(chat)
            async def capture_chat(service, request, *, trace_id, _trace=trace):
                turn = {
                    "turn": len(_trace["turns"]),
                    "trace_id": trace_id,
                    "request": safe_value(request),
                    "nodes": [],
                    "pending_before": pending_value(service),
                }
                _trace["turns"].append(turn)
                token = ACTIVE_TURN.set(turn)
                try:
                    response = await chat(service, request, trace_id=trace_id)
                    turn["response"] = safe_value(response)
                    return response
                except Exception as exc:
                    turn["error"] = error_value(exc)
                    raise
                finally:
                    ACTIVE_TURN.reset(token)
                    turn["pending_after"] = pending_value(service)
                    turn["database_after"] = await database_value(service._p2r_environment)

            providers = []

            def factory(_providers=providers):
                value = (
                    llm_factory()
                    if llm_factory
                    else (ScriptedProvider() if provider == "scripted" else OfflineLLMProvider())
                )
                _providers.append(value)
                return value

            def environment(**kwargs):
                return ObservedEnvironment(memory_mode=mode, **kwargs)

            with (
                patch("eval.multiturn.BusinessEnvironment", environment),
                patch.object(ChatService, "chat", capture_chat),
            ):
                scored = await run_scenarios(
                    [case], dataset_sha256=dataset_sha256, tracing=True, llm_factory=factory
                )
            # Unmodified original EvaluationResult including contract-default
            # model_evaluation=NOT_RUN is retained verbatim under raw results.
            all_results.extend(row.model_dump(mode="json") for row in scored)
            trace["provider_calls"] = providers[0].calls if provider == "scripted" else []
            trace["scorer_result"] = scored[0].model_dump(mode="json")
    return {
        "schema_version": "p2r-runtime-evidence-v1",
        "model_evaluation": "OFFLINE",
        "real_model_evaluation": "NOT_RUN",
        "evidence_origin": ORIGIN,
        "provider": f"OFFLINE_{provider.upper()}",
        "mode": mode,
        "paid_api_calls": 0,
        "paid_tokens": 0,
        "raw_scorer_model_evaluation_note": "NOT_RUN is the original contract default; this run is explicitly OFFLINE",
        "cases": len(all_results),
        "passed": sum(row["status"] == "PASS" for row in all_results),
        "results": all_results,
        "traces": traces,
    }


def hashes(paths):
    return {
        path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(set(paths))
    }


def configuration(dataset, digest, mode, provider):
    return {
        "evidence_origin": ORIGIN,
        "model_evaluation": "OFFLINE",
        "mode": mode,
        "provider": f"OFFLINE_{provider.upper()}",
        "network": "FORBIDDEN",
        "dataset": dataset.resolve().relative_to(ROOT).as_posix()
        if dataset.resolve().is_relative_to(ROOT)
        else dataset.name,
        "dataset_sha256": digest,
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_hashes": hashes((ROOT / "app").rglob("*.py")),
        "prompt_hashes": hashes((ROOT / "app/prompts").rglob("*.py")),
        "scorer_hashes": hashes(
            ROOT / name
            for name in (
                "eval/multiturn.py",
                "eval/contracts.py",
                "eval/tool_scoring.py",
                "eval/goal_scoring.py",
                "eval/environment.py",
                "eval/memory_ablation.py",
            )
        ),
        "harness_hashes": hashes([Path(__file__).resolve()]),
        "database": "New isolated in-memory SQLite database per case; committed snapshots after each chat",
        "capture": "Allowlisted actual node input/output, initial/final state, request/response, pending actions, all database tables",
        "excluded": sorted(EXCLUDED),
        "gold_to_service_or_provider": False,
        "historical_trace_available": False,
        "paid_api_calls": 0,
    }


def write_new(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


async def evaluate_to_directory(
    cases, *, dataset_sha256, output, dataset, mode="M2", provider="scripted"
):
    output.mkdir(parents=True, exist_ok=False)
    config = configuration(dataset, dataset_sha256, mode, provider)
    write_new(output / "experiment_config.json", config)
    value = await evaluate_cases(cases, dataset_sha256=dataset_sha256, mode=mode, provider=provider)
    traces = value.pop("traces")
    (output / "traces").mkdir()
    for index, trace in enumerate(traces):
        # Filenames use validated synthetic case IDs only after removing path characters.
        identifier = "".join(c for c in trace["case_id"] if c.isalnum() or c in "_-")
        write_new(output / "traces" / f"{index:03d}_{identifier}.json", trace)
    write_new(output / "results.json", value)
    after = configuration(dataset, dataset_sha256, mode, provider)
    write_new(
        output / "validation.json",
        {
            "source_unchanged": after["source_hashes"] == config["source_hashes"],
            "prompts_unchanged": after["prompt_hashes"] == config["prompt_hashes"],
            "scorers_unchanged": after["scorer_hashes"] == config["scorer_hashes"],
            "dataset_unchanged": hashlib.sha256(dataset.read_bytes()).hexdigest() == dataset_sha256,
            "case_traces": len(traces),
            "turns": sum(len(t["turns"]) for t in traces),
            "node_records": sum(len(turn["nodes"]) for t in traces for turn in t["turns"]),
            "model_evaluation": "OFFLINE",
            "evidence_origin": ORIGIN,
        },
    )
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--mode", default="M2", choices=["M2"])
    parser.add_argument("--provider", default="scripted", choices=["scripted", "rule"])
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    cases, digest = load_scenarios(args.dataset)
    value = asyncio.run(
        evaluate_to_directory(
            cases,
            dataset_sha256=digest,
            output=args.output,
            dataset=args.dataset,
            mode=args.mode,
            provider=args.provider,
        )
    )
    print(
        json.dumps(
            {k: value[k] for k in ("model_evaluation", "mode", "provider", "cases", "passed")}
        )
    )


if __name__ == "__main__":
    main()
