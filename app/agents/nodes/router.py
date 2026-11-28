"""Intent and complexity routing nodes."""

from __future__ import annotations

import time
from dataclasses import replace

from app.agents.goals import GOAL_INTENTS, resolve_goals
from app.agents.nodes.intent import IntentClassifier
from app.agents.state import AgentState
from app.core.enums import IntentLabel, QueryComplexity, RetrievalStrategy
from app.memory.context import node_context, node_query, user_orders
from app.observability.tracing import traced
from app.retrieval.adaptive import AdaptiveRouter
from app.schemas.agent import ComplexityResult
from app.schemas.common import LatencyBreakdown
from app.schemas.goals import GoalKind, TaskGoal
from app.skills.registry import SkillRegistry
from app.skills.selector import SkillRuntimeMode, affirmative_action, select_skill


def _latency(state: AgentState) -> LatencyBreakdown:
    return state.get("latency") or LatencyBreakdown()


def _verified_order_scope(query: str, goals: list[TaskGoal]) -> bool:
    current = set(user_orders(query))
    active = [goal for goal in goals if not goal.negated]
    order_goals = [goal for goal in active if goal.entity_type == "order"]
    return (
        len(current) > 1
        and bool(order_goals)
        and all(
            not goal.conditions
            and (goal.operation == "read" or (goal.kind == GoalKind.UNKNOWN and goal.independent))
            for goal in active
        )
        and all(
            goal.entity_id in current
            and goal.entity_source == "current_user"
            and goal.entity_scope in {"local", "distributive"}
            for goal in order_goals
        )
    )


def _verified_conditional_scope(
    query: str, selected_goal: TaskGoal, independent: tuple[TaskGoal, ...]
) -> bool:
    current = set(user_orders(query))
    order_goals = [goal for goal in (selected_goal, *independent) if goal.entity_type == "order"]
    return (
        len(current) > 1
        and {goal.entity_id for goal in order_goals} == current
        and all(
            goal.entity_source == "current_user" and goal.entity_scope in {"local", "distributive"}
            for goal in order_goals
        )
    )


_PROTECTED_INTENTS = {IntentLabel.OUT_OF_SCOPE, IntentLabel.HUMAN_HANDOFF, IntentLabel.COMPLAINT}
_ACTION_INTENTS = {
    GoalKind.CANCEL: IntentLabel.CANCEL_ORDER,
    GoalKind.RETURN_REQUEST: IntentLabel.RETURN_EXCHANGE,
    GoalKind.REFUND_REQUEST: IntentLabel.REFUND,
}


def _task_intent(query: str, goals: list[TaskGoal]) -> IntentLabel | None:
    action = [
        goal for goal in goals if goal.kind in _ACTION_INTENTS and affirmative_action(query, goal)
    ]
    if len(action) == 1:
        return _ACTION_INTENTS[action[0].kind]
    kinds = {goal.kind for goal in goals if not goal.negated} - {GoalKind.UNKNOWN}
    return IntentLabel.FAQ_POLICY if kinds == {GoalKind.POLICY} else None


@traced("node.intent", "chain")
async def intent_node(
    state: AgentState,
    classifier: IntentClassifier,
    *,
    skills: SkillRegistry | None = None,
    skill_mode: SkillRuntimeMode = "conditional",
) -> dict:
    started = time.perf_counter()
    intent_context = node_context(state, "intent")
    intent = (
        await classifier.classify(node_query(state), context=intent_context)
        if intent_context
        else await classifier.classify(node_query(state))
    )
    context = state.get("selected_context")
    goals = resolve_goals(
        state["user_query"],
        context,
        intent.goal_signals,
        dependency_hints=intent.dependency_hints,
    )
    grounded_intent = _task_intent(state["user_query"], goals)
    if grounded_intent and intent.label not in _PROTECTED_INTENTS:
        intent = intent.model_copy(
            update={
                "label": grounded_intent,
                "rationale": f"{intent.rationale};grounded_request_type",
            }
        )
    active = [goal for goal in goals if not goal.negated and not goal.conditions]
    labels = [
        GOAL_INTENTS[goal.kind] for goal in active if goal.entity_id and goal.kind in GOAL_INTENTS
    ]
    if (
        labels
        and intent.label not in _PROTECTED_INTENTS
        and not any(goal.operation == "write" for goal in active)
        and (intent.label not in labels or (len(set(labels)) > 1 and intent.label != labels[0]))
        and not (active[0].kind.value == "policy" and intent.label == IntentLabel.FAQ_POLICY)
    ):
        intent = intent.model_copy(
            update={"label": labels[0], "rationale": f"{intent.rationale};grounded_task_goal"}
        )
    latency = _latency(state)
    latency.intent_ms = (time.perf_counter() - started) * 1000
    result = {"intent": intent, "task_goals": goals, "latency": latency}
    conditional_scope = False
    if skills is not None and (
        not (context and context.needs_clarification) or len(user_orders(state["user_query"])) > 1
    ):
        selection = select_skill(
            skills,
            state["user_query"],
            intent.label.value,
            goals,
            intent.skill_hints,
            mode=skill_mode,
        )
        result["skill_selection"] = selection
        if selected_goal := selection.conditional_goal:
            conditional_scope = _verified_conditional_scope(
                state["user_query"], selected_goal, selection.independent_goals
            )
            result["task_goals"] = [
                selected_goal
                if goal.kind == selected_goal.kind
                and goal.request_text == selected_goal.request_text
                else goal
                for goal in goals
            ]
    if (
        context
        and context.needs_clarification
        and intent.label
        not in {IntentLabel.OUT_OF_SCOPE, IntentLabel.HUMAN_HANDOFF, IntentLabel.COMPLAINT}
        and (_verified_order_scope(state["user_query"], goals) or conditional_scope)
    ):
        result["selected_context"] = replace(context, needs_clarification=False)
    return result


@traced("node.router", "chain")
async def router_node(state: AgentState, router: AdaptiveRouter) -> dict:
    started = time.perf_counter()
    intent = state["intent"]
    assert intent is not None
    context = state.get("selected_context")
    ambiguous = bool(context and context.needs_clarification)
    if state.get("confirmed_action"):
        complexity = ComplexityResult(
            complexity=QueryComplexity.TOOL_REQUIRED,
            strategy=RetrievalStrategy.AGENT,
            confidence=1.0,
            rationale="confirmed_action",
        )
    elif ambiguous and intent.label != IntentLabel.OUT_OF_SCOPE:
        complexity = ComplexityResult(
            complexity=QueryComplexity.SIMPLE,
            strategy=RetrievalStrategy.DIRECT,
            confidence=1.0,
            rationale="entity_ambiguity",
        )
    else:
        complexity = await router.route(node_query(state), intent)
        if (
            complexity.strategy != RetrievalStrategy.REFUSE
            and intent.label == IntentLabel.FAQ_POLICY
            and _task_intent(state["user_query"], state.get("task_goals", []))
            == IntentLabel.FAQ_POLICY
        ):
            complexity = ComplexityResult(
                complexity=QueryComplexity.SINGLE_HOP,
                strategy=RetrievalStrategy.SINGLE,
                confidence=complexity.confidence,
                rationale="grounded_policy",
            )
    skill = state.get("skill_selection")
    if (
        not ambiguous
        and complexity.strategy not in {RetrievalStrategy.REFUSE, RetrievalStrategy.AGENT}
        and (
            bool(skill and skill.requires_agent)
            or any(
                goal.operation == "read"
                and goal.entity_id
                and not goal.negated
                and not goal.conditions
                for goal in state.get("task_goals", [])
            )
        )
    ):
        complexity = ComplexityResult(
            complexity=QueryComplexity.TOOL_REQUIRED,
            strategy=RetrievalStrategy.AGENT,
            confidence=complexity.confidence,
            rationale="grounded_skill" if skill and skill.requires_agent else "grounded_task_goal",
        )
    latency = _latency(state)
    latency.routing_ms = (time.perf_counter() - started) * 1000
    return {
        "complexity": complexity,
        "strategy": complexity.strategy,
        "query_complexity": complexity.complexity,
        "latency": latency,
    }
