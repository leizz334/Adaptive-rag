"""Agent planning, intent, complexity and tool-result schemas."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.core.enums import IntentLabel, QueryComplexity, RetrievalStrategy, ToolRisk
from app.schemas.goals import DependencyHint, GoalSignal, SkillHint

ReadContractMode = Literal["legacy", "full", "partial", "clarify"]
PlanningStrategy = Literal["direct", "skill", "dynamic", "partial", "clarify", "confirmed"]
PlanningReason = Literal[
    "no_business_goals",
    "complete_read_contract",
    "direct_disabled",
    "policy_retrieval",
    "untrusted_entity",
    "unresolved_goal",
    "entity_ambiguity",
    "conditional_dependency",
    "unsupported_fields",
    "non_read_goals",
    "no_verified_read",
    "contract_validation_failed",
    "confirmed_action",
    "skill_workflow",
    "skill_clarification",
]
SkillMode = Literal["instructions", "workflow"]
WorkflowStepStatus = Literal[
    "executed",
    "failed",
    "condition_false",
    "condition_unknown",
    "prerequisite_failed",
    "prerequisite_skipped",
    "limit_reached",
]
WorkflowActionStatus = Literal["ready", "ineligible", "unverified", "failed"]


class IntentResult(BaseModel):
    label: IntentLabel
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = ""
    prompt_version: str
    goal_signals: list[GoalSignal] = Field(default_factory=list, max_length=8)
    skill_hints: list[SkillHint] = Field(default_factory=list, max_length=4)
    dependency_hints: list[DependencyHint] = Field(default_factory=list, max_length=3)

    @field_validator("dependency_hints", mode="before")
    @classmethod
    def discard_unusable_dependencies(cls, value: object) -> list[DependencyHint]:
        hints = []
        for item in value[:3] if isinstance(value, list) else []:
            try:
                hints.append(DependencyHint.model_validate(item))
            except ValidationError:
                continue
        return hints

    @field_validator("goal_signals", mode="before")
    @classmethod
    def discard_unusable_goal_hints(cls, value: object) -> list[GoalSignal]:
        """Malformed hints do not invalidate the existing classification result."""
        signals = []
        for item in value[:8] if isinstance(value, list) else []:
            try:
                signals.append(GoalSignal.model_validate(item))
            except ValidationError:
                continue
        return signals

    @field_validator("skill_hints", mode="before")
    @classmethod
    def discard_unusable_skill_hints(cls, value: object) -> list[SkillHint]:
        hints = []
        for item in value[:4] if isinstance(value, list) else []:
            try:
                hints.append(SkillHint.model_validate(item))
            except ValidationError:
                continue
        return hints


class ComplexityResult(BaseModel):
    complexity: QueryComplexity
    strategy: RetrievalStrategy
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = ""


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    name: str
    success: bool
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    risk: ToolRisk = ToolRisk.READ
    truncated: bool = False


class PlanCondition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_step_id: int = Field(gt=0, strict=True)
    field: Literal["paid_at"] = "paid_at"
    op: Literal["is_paid"] = "is_paid"


class WorkflowAction(BaseModel):
    """A candidate for user confirmation backed by a same-order preflight read."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tool_name: str
    arguments: dict[str, Any]
    source_step_id: int = Field(gt=0, strict=True)


class PlanStep(BaseModel):
    step_id: int
    goal: str
    tool_name: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    needs_retrieval: bool = False
    depends_on: tuple[int, ...] = ()
    condition: PlanCondition | None = None


class AgentPlan(BaseModel):
    steps: list[PlanStep]
    rationale: str = ""
    read_contract_applied: bool = False
    read_contract_mode: ReadContractMode = "legacy"
    planning_strategy: PlanningStrategy = "dynamic"
    planning_reason: PlanningReason = "no_business_goals"
    planner_llm_calls: int = 0
    planner_model_mode: Literal["json", "function_calling", "none"] = "none"
    planning_required_goals: int = 0
    planning_covered_goals: int = 0
    planning_deduplicated_calls: int = 0
    skill_name: str | None = None
    skill_mode: SkillMode | None = None
    skill_clarification: Literal["order_id", "return_reason", "return_scope"] | None = None
    workflow_action: WorkflowAction | None = None
