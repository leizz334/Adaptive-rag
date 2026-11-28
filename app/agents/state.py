"""Shared agent state passed between graph nodes."""

from typing import Any, TypedDict

from app.core.enums import QueryComplexity, RetrievalStrategy
from app.memory.context import SelectedContext
from app.schemas.agent import (
    AgentPlan,
    ComplexityResult,
    IntentResult,
    ToolResult,
    WorkflowActionStatus,
    WorkflowStepStatus,
)
from app.schemas.chat import ActionProposal, ChatMessage
from app.schemas.common import LatencyBreakdown, TokenUsage
from app.schemas.goals import TaskGoal
from app.schemas.retrieval import Citation, RetrievedChunk
from app.skills.selector import SkillSelection


class AgentState(TypedDict, total=False):
    """LangGraph state. Partial updates replace listed keys; no infinite append reducer.

    Messages are compressed explicitly in the memory node instead of Annotated[add]
    so the graph cannot silently blow the 128k budget.
    """

    trace_id: str
    session_id: str
    user_id: str
    user_query: str
    resolved_query: str
    selected_context: SelectedContext
    memory_managed: bool
    memory_preferences: dict[str, str]
    messages: list[ChatMessage]
    summary: str
    intent: IntentResult | None
    task_goals: list[TaskGoal]
    skill_selection: SkillSelection
    complexity: ComplexityResult | None
    strategy: RetrievalStrategy | None
    query_complexity: QueryComplexity | None
    rewritten_queries: list[str]
    retrieved_chunks: list[RetrievedChunk]
    generation_chunks: list[RetrievedChunk]
    plan: AgentPlan | None
    tool_results: list[ToolResult]
    tool_result_steps: list[int]
    workflow_step_statuses: dict[int, WorkflowStepStatus]
    workflow_action_status: WorkflowActionStatus | None
    workflow_error: str | None
    pending_action: ActionProposal | None
    confirmed_action: ActionProposal | None
    confirm_action_id: str | None
    idempotency_key: str | None
    final_answer: str | None
    citations: list[Citation]
    refused: bool
    error: str | None
    step_count: int
    react_read_only: bool
    token_usage: TokenUsage
    latency: LatencyBreakdown
    extra: dict[str, Any]
