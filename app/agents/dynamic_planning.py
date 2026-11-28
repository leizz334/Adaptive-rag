"""Native tool-call decoding and the DeepSeek Beta schema boundary."""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from app.providers.base import LLMResponse
from app.schemas.agent import AgentPlan, PlanStep

DynamicPlanningMode = Literal["json", "function_calling"]
DecodeIssue = Literal["call_schema", "arguments_json", "arguments_schema"]


class NativePlanningProvider(Protocol):
    async def generate(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float,
        max_tokens: int,
        tools: list[dict[str, Any]],
        tool_choice: str,
    ) -> LLMResponse: ...


@dataclass(frozen=True)
class NativePlan:
    plan: AgentPlan
    issues: tuple[DecodeIssue, ...]


def _arguments_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate argument key")
        result[key] = value
    return result


def _reject_constant(_value: str) -> Any:
    raise ValueError("invalid JSON constant")


def decode_native_plan(calls: object) -> NativePlan:
    steps: list[PlanStep] = []
    issues: list[DecodeIssue] = []
    if not isinstance(calls, list):
        return NativePlan(AgentPlan(steps=[], rationale="native_function_calls"), ("call_schema",))
    for call in calls:
        if not isinstance(call, dict):
            issues.append("call_schema")
            continue
        function = call.get("function")
        if (
            call.get("type") != "function"
            or not isinstance(call.get("id"), str)
            or not call["id"]
            or not isinstance(function, dict)
            or not isinstance(function.get("name"), str)
            or not function["name"]
            or not isinstance(function.get("arguments"), str)
        ):
            issues.append("call_schema")
            continue
        try:
            arguments = json.loads(
                function["arguments"],
                object_pairs_hook=_arguments_object,
                parse_constant=_reject_constant,
            )
        except (ValueError, RecursionError):
            issues.append("arguments_json")
            continue
        if not isinstance(arguments, dict):
            issues.append("arguments_schema")
            continue
        name = function["name"]
        steps.append(
            PlanStep(
                step_id=len(steps) + 1,
                goal=name,
                tool_name=name,
                arguments=arguments,
                needs_retrieval=name == "search_knowledge",
            )
        )
    return NativePlan(AgentPlan(steps=steps, rationale="native_function_calls"), tuple(issues))


_BETA_IGNORED = {"title", "examples", "minLength", "maxLength", "minItems", "maxItems"}
_BETA_TYPES = {"object", "string", "number", "integer", "boolean", "array"}


def _strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Translate supported portions only; registry validation still enforces the full schema."""
    result = {key: value for key, value in schema.items() if key not in _BETA_IGNORED}
    kind = result.get("type")
    if kind is not None and kind not in _BETA_TYPES:
        raise ValueError("unsupported type in Strict Beta schema")
    if kind == "object":
        props = result.get("properties", {})
        if set(props) != set(result.get("required", ())):
            raise ValueError(
                "optional fields cannot be converted to Strict Beta without changing the contract"
            )
        if isinstance(result.get("additionalProperties"), dict):
            raise ValueError("free-form objects are unsupported in Strict Beta")
        result["properties"] = {key: _strict_schema(value) for key, value in props.items()}
        result["required"] = list(props)
        result["additionalProperties"] = False
    if kind == "array" and "items" in result:
        result["items"] = _strict_schema(result["items"])
    if "anyOf" in result:
        result["anyOf"] = [_strict_schema(option) for option in result["anyOf"]]
    for key in ("$defs", "$def"):
        if key in result:
            result[key] = {name: _strict_schema(value) for name, value in result[key].items()}
    return result


def strict_tool_definitions(tools: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            **tool,
            "function": {
                **tool["function"],
                "strict": True,
                "parameters": _strict_schema(tool["function"]["parameters"]),
            },
        }
        for tool in tools
    ]
