import json

import pytest

from app.agents.goals import resolve_goals
from app.agents.nodes.planner import Planner, planner_node
from app.observability.execution import capture_tools
from app.providers.base import LLMResponse
from app.repositories.models import OrderRow
from app.schemas.agent import IntentResult
from app.schemas.chat import ChatRequest
from app.schemas.goals import SkillHint
from app.skills.registry import SkillRegistry
from app.skills.selector import select_skill
from eval.environment import BusinessEnvironment


class ProposalProvider:
    def __init__(self, proposal):
        self.requests = []
        self.proposal = proposal

    async def generate(self, messages, **options):
        self.requests.append((messages, options))
        if "tools" in options:
            return LLMResponse(
                "",
                tool_calls=[
                    {
                        "id": "demo",
                        "type": "function",
                        "function": {
                            "name": self.proposal["tool_name"],
                            "arguments": json.dumps(self.proposal["arguments"]),
                        },
                    }
                ],
            )
        return LLMResponse(json.dumps({"steps": [self.proposal]}))


@pytest.mark.parametrize("mode", ["json", "function_calling"])
async def test_resource_is_loaded_only_for_activated_instruction_skill(mode):
    async with BusinessEnvironment() as env:
        package = SkillRegistry()
        text = "能按使用需求推荐给我一款安静的耳机吗？也说说你筛选的依据。"
        goals = resolve_goals(text)
        hint = SkillHint(name="product-recommend", quote="说说你筛选的依据", needs_reference=True)
        skill = select_skill(package, text, "recommendation", goals, [hint], mode="conditional")
        assert skill.name == "product-recommend"
        provider = ProposalProvider(
            {
                "step_id": 1,
                "goal": "suggest",
                "tool_name": "recommend_products",
                "arguments": {"category": "数码"},
            }
        )
        planner = Planner(provider, env.service.registry, mode=mode, skills=package)
        result = await planner.create_plan(
            text, "recommendation", "", task_goals=goals, skill_selection=skill
        )
        assert result.planning_strategy == "dynamic"
        assert result.skill_name == "product-recommend" and result.skill_mode == "instructions"
        assert result.planner_model_mode == mode and result.planner_llm_calls == 1
        prompt = provider.requests[0][0][0]["content"]
        resource = package.load_resource("product-recommend", "references/catalog-evidence.md")
        assert resource in prompt
        assert package.load_instructions("order-cancellation") not in prompt


async def test_dynamic_plan_cannot_flatten_authored_conditions_or_set_workflow_authority():
    async with BusinessEnvironment() as env:
        provider = ProposalProvider(
            {
                "step_id": 2,
                "goal": "read",
                "tool_name": "get_order_items",
                "arguments": {"order_id": "ORD10001"},
                "depends_on": [1],
                "condition": {"source_step_id": 1},
            }
        )
        plan = await Planner(provider, env.service.registry, skills=SkillRegistry()).create_plan(
            "核对一下", "order_inquiry", ""
        )
        assert all(step.tool_name != "get_order_items" for step in plan.steps)
        assert plan.workflow_action is None


async def test_instruction_skill_cannot_change_write_entity():
    async with BusinessEnvironment() as env:
        query = "取消订单 ORD10003"
        goals = resolve_goals(query)
        packages = SkillRegistry()
        selected = select_skill(packages, query, "cancel_order", goals, mode="instructions")
        assert selected.name == "order-cancellation"
        wrong = {
            "step_id": 1,
            "goal": "cancel",
            "tool_name": "cancel_order",
            "arguments": {"order_id": "ORD10001"},
        }
        planner = Planner(ProposalProvider(wrong), env.service.registry, skills=packages)
        state = {
            "user_query": query,
            "intent": IntentResult(label="cancel_order", confidence=1, prompt_version="test"),
            "task_goals": goals,
            "skill_selection": selected,
        }
        result = await planner_node(state, planner)
        assert result.get("pending_action") is None
        assert result["plan"].steps == []


@pytest.mark.parametrize(
    "query",
    [
        "ORD10003 还能不能取消订单？",
        "别帮我取消订单 ORD10003。",
        "取消订单 ORD10003-WRONG",
        "帮我给 ORD10001 的耳机申请退货，原因是声音异常。",
    ],
)
async def test_unsupported_or_uncertain_approval_never_gets_a_ticket(query):
    async with BusinessEnvironment(memory_mode="M2") as env:
        before = await env.snapshot()
        result = await env.service.chat(
            ChatRequest(message=query, user_id="u_demo"), trace_id="p4-safe"
        )
        assert result.pending_action is None
        assert await env.snapshot() == before


async def test_invalid_approval_workflow_clarifies_without_dynamic_write(monkeypatch):
    async with BusinessEnvironment() as env:
        package = SkillRegistry()
        monkeypatch.setattr(package, "load_workflow", lambda _name: {"version": 1, "steps": []})
        query = "取消订单 ORD10003"
        goals = resolve_goals(query)
        selection = select_skill(package, query, "cancel_order", goals, mode="conditional")
        assert selection.use_workflow
        provider = ProposalProvider(
            {
                "step_id": 1,
                "goal": "cancel",
                "tool_name": "cancel_order",
                "arguments": {"order_id": "ORD10003"},
            }
        )
        plan = await Planner(provider, env.service.registry, skills=package).create_plan(
            query,
            "cancel_order",
            "",
            task_goals=goals,
            skill_selection=selection,
        )
        assert plan.planning_strategy == "clarify" and not plan.steps
        assert provider.requests == [] and plan.workflow_action is None


async def test_order_cancellation_preflight_and_confirmed_execution_are_separate():
    async with BusinessEnvironment(memory_mode="M2") as env:
        before = await env.snapshot()
        with capture_tools() as trace:
            result = await env.service.chat(
                ChatRequest(message="取消订单 ORD10003", user_id="u_demo"), trace_id="p4-cancel"
            )
        assert [event["name"] for event in trace] == ["get_order"]
        assert result.pending_action is not None
        assert result.pending_action.tool_name == "cancel_order"
        assert await env.snapshot() == before
        with capture_tools() as trace:
            confirmed = await env.service.chat(
                ChatRequest(
                    user_id="u_demo",
                    session_id=result.session_id,
                    message="确认取消",
                    confirm_action_id=result.pending_action.action_id,
                ),
                trace_id="p4-confirm",
            )
        assert confirmed.pending_action is None
        assert [event["name"] for event in trace] == ["cancel_order"]
        assert (await env.snapshot())["orders"]["ORD10003"]["status"] == "cancelled"


@pytest.mark.parametrize(("order_id", "allowed"), [("ORD10001", True), ("ORD10003", False)])
async def test_condition_uses_current_result_on_normal_graph_path(order_id, allowed):
    async with BusinessEnvironment(memory_mode="M2") as env:
        if not allowed:
            await _make_unpaid(env, order_id)
        query = f"如果订单 {order_id} 已经付款，就帮我查询商品明细。"
        with capture_tools() as trace:
            result = await env.service.chat(
                ChatRequest(message=query, user_id="u_demo"), trace_id="p4-condition"
            )
        assert [event["name"] for event in trace] == (
            ["get_order", "get_order_items"] if allowed else ["get_order"]
        )
        assert ("Pro" in result.answer) if allowed else ("尚未付款" in result.answer)


async def test_explicit_independent_order_still_reads_when_condition_is_false():
    async with BusinessEnvironment(memory_mode="M2") as env:
        await _make_unpaid(env, "ORD10003")
        query = "如果订单 ORD10003 已经付款，就帮我查询商品明细。另外请查 ORD10001 的实付金额。"
        with capture_tools() as trace:
            result = await env.service.chat(
                ChatRequest(message=query, user_id="u_demo"), trace_id="p4-independent"
            )
        assert [(event["name"], event["arguments"]["order_id"]) for event in trace] == [
            ("get_order", "ORD10003"),
            ("get_order", "ORD10001"),
        ]
        assert (
            "尚未付款" in result.answer
            and "ORD10001" in result.answer
            and "299.00" in result.answer
        )


async def _make_unpaid(env, order_id):
    await env.change_order_states({order_id: "created"})
    async with env.container.session_factory() as db:
        order = await db.get(OrderRow, order_id)
        order.paid_at = None
        await db.commit()
