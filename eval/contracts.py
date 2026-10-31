"""Versioned, local evaluation contracts. Gold is never a model input."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ToolCall(Contract):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    status: Literal["executed", "denied", "replayed"] = "executed"
    success: bool = True
    failure_kind: str | None = None
    turn: int = 0


class ToolExpectation(Contract):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class TrajectorySpec(Contract):
    required: list[ToolExpectation] = Field(default_factory=list)
    allowed: list[str] = Field(default_factory=list)
    valid_paths: list[list[str]] = Field(default_factory=list)
    before: list[tuple[str, str]] = Field(default_factory=list)
    max_calls: dict[str, int] = Field(default_factory=dict)


class EnvironmentExpectation(Contract):
    orders: dict[str, str] = Field(default_factory=dict)
    allowed_mutations: list[str] = Field(default_factory=list)
    refunds: int = 0
    returns: int = 0
    audit_actions: list[str] = Field(default_factory=list)


class EvaluationResult(Contract):
    schema_version: str = "agent-eval-v2.1"
    case_id: str
    status: Literal["PASS", "FAIL", "ERROR", "NOT_RUN"]
    metrics: dict[str, float | None] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)
    dataset_sha256: str = ""
    model_evaluation: str = "NOT_RUN"
