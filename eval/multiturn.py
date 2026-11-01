"""Offline multi-turn Agent driver using the real service and independent oracles."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import time
from pathlib import Path

from pydantic import Field

from app.core.exceptions import AppError
from app.observability.execution import capture_tools
from app.observability.tracing import TraceRecorder
from app.schemas.chat import ChatRequest
from eval.contracts import (
    Contract,
    EnvironmentExpectation,
    EvaluationResult,
    ToolCall,
    TrajectorySpec,
)
from eval.environment import BusinessEnvironment
from eval.goal_scoring import score_goal
from eval.tool_scoring import score_tools

DATASET = Path(__file__).with_name("dataset") / "agent_v2.json"


class Turn(Contract):
    message: str = Field(min_length=1)
    user_id: str | None = None
    new_session: bool = False
    confirm: bool = False
    invalid_confirmation: bool = False
    expected_error: str | None = None
    expected_pending: bool | None = None
    expected_refused: bool | None = None
    expected_failures: list[str] = Field(default_factory=list)
    trajectory: TrajectorySpec = Field(default_factory=TrajectorySpec)


class Scenario(Contract):
    id: str
    family: str
    user_goal: str
    user_id: str = "u_demo"
    turns: list[Turn] = Field(min_length=1)
    expected: EnvironmentExpectation = Field(default_factory=EnvironmentExpectation)
    known_limitation: str | None = None


def load_scenarios(path: Path = DATASET):
    raw = path.read_bytes()
    payload = json.loads(raw)
    if payload["schema_version"] != "agent-scenarios-v2.1":
        raise ValueError("Unsupported scenario schema")
    cases = [Scenario.model_validate(row) for row in payload["scenarios"]]
    if len({c.id for c in cases}) != len(cases):
        raise ValueError("Duplicate scenario IDs")
    return cases, hashlib.sha256(raw).hexdigest()


async def run_scenarios(
    cases: list[Scenario], *, dataset_sha256: str, tracing=True, llm_factory=None
):
    results = []
    for case in cases:
        batches = []
        recorder = TraceRecorder(enabled=tracing, sink=batches.append)
        reasons, calls, turns = [], [], []
        started = time.perf_counter()
        # No expected/gold data is passed to the service, provider or prompt.
        async with BusinessEnvironment(
            llm=llm_factory() if llm_factory else None, tracer=recorder
        ) as env:
            initial = await env.snapshot()
            session_id = None
            pending = None
            for index, turn in enumerate(case.turns):
                actor = turn.user_id or case.user_id
                action_id = (
                    "not-issued" if turn.invalid_confirmation else pending if turn.confirm else None
                )
                if turn.confirm and not action_id:
                    reasons.append(f"turn:{index}:missing_confirmation_reference")
                    action_id = "not-issued"
                request = ChatRequest(
                    message=turn.message,
                    user_id=actor,
                    session_id=None if turn.new_session else session_id,
                    confirm_action_id=action_id,
                )
                response = None
                error = None
                with capture_tools() as events:
                    try:
                        response = await env.service.chat(
                            request, trace_id=f"offline_{case.id}_{index}"
                        )
                    except AppError as exc:
                        error = exc.error_code.value
                    except Exception as exc:
                        error = type(exc).__name__
                actual_calls = [ToolCall(**e, turn=index) for e in events]
                calls.extend(actual_calls)
                scores = score_tools(actual_calls, turn.trajectory)
                if error != turn.expected_error:
                    reasons.append(f"turn:{index}:unexpected_error:{error or 'none'}")
                if scores["missing_required_calls"]:
                    reasons.append(f"turn:{index}:missing_tool")
                if (
                    scores["tool_argument_accuracy"] is not None
                    and scores["tool_argument_accuracy"] < 1
                ):
                    reasons.append(f"turn:{index}:wrong_arguments")
                if not scores["trajectory_valid"]:
                    reasons.append(f"turn:{index}:trajectory_invalid")
                if any(
                    not c.success and c.failure_kind not in turn.expected_failures
                    for c in actual_calls
                ):
                    reasons.append(f"turn:{index}:unexpected_tool_failure")
                if any(
                    c.output.get("user_id") is not None and c.output["user_id"] != actor
                    for c in actual_calls
                ):
                    reasons.append(f"turn:{index}:cross_user_tool_output")
                if response is not None:
                    session_id = response.session_id
                    if response.pending_action:
                        pending = response.pending_action.action_id
                    if (
                        turn.expected_pending is not None
                        and bool(response.pending_action) != turn.expected_pending
                    ):
                        reasons.append(f"turn:{index}:pending_mismatch")
                    if (
                        turn.expected_refused is not None
                        and response.refused != turn.expected_refused
                    ):
                        reasons.append(f"turn:{index}:refusal_mismatch")
                elif turn.expected_pending is not None or turn.expected_refused is not None:
                    reasons.append(f"turn:{index}:missing_response")
                turns.append(
                    {
                        "turn": index,
                        "error": error,
                        "root_run_id": response.root_run_id if response else None,
                        "scores": scores,
                        "pending": bool(response and response.pending_action),
                        "refused": bool(response and response.refused),
                    }
                )
            actual = await env.snapshot()
            goal = score_goal(initial, actual, case.expected, calls)
            reasons.extend(goal["reasons"])
            # Unconfirmed write attempts are hard violations, irrespective of the goal.
            writes = {"cancel_order", "create_refund_request", "create_return_request"}
            for call in calls:
                if (
                    call.name in writes
                    and call.status == "executed"
                    and not case.turns[call.turn].confirm
                ):
                    reasons.append(f"turn:{call.turn}:unconfirmed_write")
        success = not reasons
        results.append(
            EvaluationResult(
                case_id=case.id,
                status="PASS" if success else "FAIL",
                reasons=sorted(set(reasons)),
                metrics={
                    "agent_task_success": int(success),
                    "environment_state_correct": goal["environment_state_correct"],
                    "latency_ms": (time.perf_counter() - started) * 1000,
                },
                evidence={
                    "family": case.family,
                    "turns": turns,
                    "tool_calls": [c.model_dump() for c in calls],
                    "initial_order_states": {k: v["status"] for k, v in initial["orders"].items()},
                    "actual_order_states": {k: v["status"] for k, v in actual["orders"].items()},
                    "span_count": sum(len(b) for b in batches),
                    "known_limitation": case.known_limitation,
                },
                dataset_sha256=dataset_sha256,
            )
        )
    return results


def report(results):
    n = len(results)
    return {
        "schema_version": "agent-eval-v2.1",
        "mode": "offline_production_service",
        "model_evaluation": "NOT_RUN",
        "cases": n,
        "passed": sum(r.status == "PASS" for r in results),
        "task_success_rate": sum(r.status == "PASS" for r in results) / n if n else None,
        "environment_state_correct_rate": sum(
            r.metrics["environment_state_correct"] for r in results
        )
        / n
        if n
        else None,
        "results": [r.model_dump() for r in results],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trace-off", action="store_true")
    args = parser.parse_args()
    cases, digest = load_scenarios()
    value = report(
        asyncio.run(run_scenarios(cases, dataset_sha256=digest, tracing=not args.trace_off))
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(
        (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    print(json.dumps({k: v for k, v in value.items() if k != "results"}))


if __name__ == "__main__":
    main()
