"""Compile bounded, packaged workflows into the ordinary AgentPlan representation."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.agent import AgentPlan, PlanCondition, PlanStep, WorkflowAction
from app.skills.schemas import SkillMetadata
from app.skills.selector import SkillSelection
from app.tools.goal_contract import BoundRead, call_covers_goal, evaluate_read_contract
from app.tools.registry import ToolRegistry

Slot = Literal["order_id", "reason"]


class StepDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: int = Field(gt=0, strict=True)
    goal: str = Field(min_length=1, max_length=160)
    tool_name: str = Field(min_length=1, max_length=64)
    arguments: dict[str, Slot]
    depends_on: tuple[int, ...] = ()
    condition: PlanCondition | None = None


class ActionDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(min_length=1, max_length=64)
    arguments: dict[str, Slot]
    source_step_id: int = Field(gt=0, strict=True)


class WorkflowDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1]
    steps: list[StepDefinition] = Field(min_length=1, max_length=6)
    action: ActionDefinition | None = None


def compile_workflow(
    definition: WorkflowDefinition,
    skill: SkillMetadata,
    selection: SkillSelection,
    registry: ToolRegistry,
) -> AgentPlan:
    slots = {"order_id": selection.order_id, "reason": selection.reason}

    def arguments(values: dict[str, Slot]) -> dict[str, str]:
        if any(not slots[slot] for slot in values.values()):
            raise ValueError("Workflow argument lacks a grounded slot")
        return {key: value for key, slot in values.items() if (value := slots[slot]) is not None}

    if any(step.tool_name not in skill.tools for step in definition.steps):
        raise ValueError("Workflow tool outside the skill declaration")
    steps = [
        PlanStep(
            step_id=step.step_id,
            goal=step.goal,
            tool_name=step.tool_name,
            arguments=arguments(step.arguments),
            depends_on=step.depends_on,
            condition=step.condition,
        )
        for step in definition.steps
    ]
    approval = None
    activation = skill.extensions.get("adaptive-activation")
    if activation == "action":
        action = definition.action
        if action is None or action.tool_name not in skill.tools or selection.conditional_goal:
            raise ValueError("Workflow approval is inconsistent with the activated skill")
        if any(step.condition is not None for step in steps):
            raise ValueError("Conditional approval is outside the supported workflow scope")
        approval = WorkflowAction(
            tool_name=action.tool_name,
            arguments=arguments(action.arguments),
            source_step_id=action.source_step_id,
        )
        # The proposal's operation must be the operation established by TaskGoal.
        goal_tools = {"cancel": "cancel_order", "return_request": "create_return_request"}
        if {goal_tools.get(kind.value) for kind in skill.goals} != {approval.tool_name}:
            raise ValueError("Workflow approval tool disagrees with its goal")
    elif activation == "condition":
        goal = selection.conditional_goal
        gated = [step for step in steps if step.condition is not None]
        if definition.action or not goal or len(gated) != 1:
            raise ValueError("Workflow cannot implement the validated dependency")
        dependent = gated[0]
        if not call_covers_goal(
            BoundRead(dependent.tool_name or "", dependent.arguments),
            goal.model_copy(update={"conditions": ()}),
        ):
            raise ValueError("Dependent workflow step does not cover its TaskGoal")
    else:
        raise ValueError("Workflow requires an approved activation type")

    if selection.independent_goals:
        contract = evaluate_read_contract(selection.independent_goals, registry)
        if contract.mode != "full" or not contract.calls:
            raise ValueError("Independent workflow reads require a complete read contract")
        ordered = max(step.step_id for step in steps) + 1
        for call in contract.calls:
            if any(
                step.tool_name == call.name
                and step.arguments == call.arguments
                and not (step.condition or step.depends_on)
                for step in steps
            ):
                continue
            steps.append(
                PlanStep(
                    step_id=ordered,
                    goal="独立的已验证读取目标",
                    tool_name=call.name,
                    arguments=call.arguments,
                )
            )
            ordered += 1
    return AgentPlan(
        steps=steps,
        rationale="skill_workflow",
        read_contract_mode="full",
        read_contract_applied=True,
        planning_strategy="skill",
        planning_reason="skill_workflow",
        skill_name=skill.name,
        skill_mode="workflow",
        workflow_action=approval,
    )
