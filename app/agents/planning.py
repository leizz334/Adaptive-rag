"""Select a planning strategy using verified task and tool scope."""

from collections.abc import Sequence
from dataclasses import dataclass

from app.schemas.agent import AgentPlan, PlanningReason, PlanningStrategy
from app.schemas.goals import GoalKind, TaskGoal
from app.tools.goal_contract import ReadContract, call_covers_goal

_TRUSTED_ENTITY_SOURCES = {"current_user", "session_user", "session_summary_user_entity"}


@dataclass(frozen=True)
class PlanningDecision:
    strategy: PlanningStrategy
    reason: PlanningReason


def select_planning_strategy(
    goals: Sequence[TaskGoal],
    contract: ReadContract,
    *,
    direct_enabled: bool = True,
    workflow_validated: bool = False,
) -> PlanningDecision:
    decision = _select_standard_strategy(goals, contract, direct_enabled=direct_enabled)
    if workflow_validated and decision.strategy != "direct":
        return PlanningDecision("skill", "skill_workflow")
    return decision


def _select_standard_strategy(
    goals: Sequence[TaskGoal], contract: ReadContract, *, direct_enabled: bool
) -> PlanningDecision:
    active = [goal for goal in goals if not goal.negated]
    if contract.mode == "partial" and contract.calls:
        reason: PlanningReason = (
            "unsupported_fields"
            if any(goal.unavailable_fields for goal in active)
            else "unresolved_goal"
        )
        return PlanningDecision("partial", reason)
    if contract.mode == "clarify" or contract.calls == []:
        if any(goal.conditions for goal in active):
            return PlanningDecision("clarify", "conditional_dependency")
        if any(goal.entity_type != "none" and not goal.entity_id for goal in active):
            return PlanningDecision("clarify", "entity_ambiguity")
        if any(goal.unavailable_fields for goal in active):
            return PlanningDecision("clarify", "unsupported_fields")
        return PlanningDecision("clarify", "unresolved_goal")
    if not active:
        return PlanningDecision("dynamic", "no_business_goals")
    if any(goal.operation == "write" for goal in goals):
        return PlanningDecision("dynamic", "non_read_goals")
    if any(goal.conditions for goal in active):
        return PlanningDecision("dynamic", "conditional_dependency")
    if any(goal.kind == GoalKind.POLICY for goal in active):
        return PlanningDecision("dynamic", "policy_retrieval")
    if any(goal.kind == GoalKind.UNKNOWN or goal.operation != "read" for goal in active):
        return PlanningDecision("dynamic", "unresolved_goal")
    if any(
        goal.entity_type == "none" or not goal.entity_id or goal.clarification for goal in active
    ):
        return PlanningDecision("dynamic", "entity_ambiguity")
    if any(goal.entity_source not in _TRUSTED_ENTITY_SOURCES for goal in active):
        return PlanningDecision("dynamic", "untrusted_entity")
    if any(goal.unavailable_fields for goal in active):
        return PlanningDecision("dynamic", "unsupported_fields")
    calls = contract.calls or ()
    if contract.mode != "full" or not all(
        any(call_covers_goal(call, goal) for call in calls) for goal in active
    ):
        return PlanningDecision("dynamic", "contract_validation_failed")
    if not direct_enabled:
        return PlanningDecision("dynamic", "direct_disabled")
    return PlanningDecision("direct", "complete_read_contract")


def planning_metadata(
    plan: AgentPlan,
    decision: PlanningDecision,
    goals: Sequence[TaskGoal],
    contract: ReadContract,
    *,
    llm_calls: int,
) -> AgentPlan:
    active = [goal for goal in goals if not goal.negated]
    calls = contract.calls or ()
    covered = sum(any(call_covers_goal(call, goal) for call in calls) for goal in active)
    return plan.model_copy(
        update={
            "planning_strategy": decision.strategy,
            "planning_reason": decision.reason,
            "planner_llm_calls": llm_calls,
            "planning_required_goals": len(active),
            "planning_covered_goals": covered,
            "planning_deduplicated_calls": max(0, covered - len(calls)),
        }
    )
