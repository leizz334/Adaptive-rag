import pytest

from app.agents.graph import build_graph
from app.agents.react import execute_with_replanning
from app.config.settings import Settings
from app.core.request_scope import request_session
from app.observability.execution import capture_tools
from app.schemas.agent import AgentPlan, PlanStep
from app.schemas.chat import ChatRequest
from app.schemas.goals import GoalKind, TaskGoal
from eval.environment import BusinessEnvironment
from tests.unit.test_p5_harness_faults import _FaultModel

QUERY = "先查店里的降噪耳机，再按查到的 SKU 给我通用保修摘要。"


@pytest.mark.parametrize("enabled", [False, True])
async def test_dynamic_catalog_replan_uses_observed_sku_and_preserves_original_tool_evidence(
    monkeypatch,
    enabled,
):
    model = _FaultModel(
        intent="product_consult",
        hints=[{"name": "catalog-title-lookup", "quote": "先查店里的降噪耳机"}],
        semantics={
            "goal_signals": [
                {"category": "action", "kind": "product_detail", "quote": "先查店里的降噪耳机"},
            ]
        },
        plan=[
            {
                "step_id": 1,
                "goal": "find item",
                "tool_name": "search_products",
                "arguments": {"query": "降噪耳机"},
            }
        ],
        answer="目录匹配降噪耳机 Pro，通用保修摘要请以工具结果为准。",
    )
    monkeypatch.setenv("REACT_ENABLED", str(enabled))
    async with BusinessEnvironment(llm=model, memory_mode="M2") as env:
        settings = env.service._settings
        env.service._graph = build_graph(
            llm=model,
            settings=settings,
            retriever=env.service._retriever,
            reranker=env.service._reranker,
            registry=env.service.registry,
        )
        before = await env.snapshot()
        with capture_tools() as events:
            response = await env.service.chat(
                ChatRequest(user_id="u_demo", message=QUERY),
                trace_id="react-test",
            )
        names = [event["name"] for event in events]
        assert names == (["search_products", "get_warranty"] if enabled else ["search_products"])
        if enabled:
            assert events[-1]["arguments"] == {"sku": "SKU-HEADSET"}
        assert response.pending_action is None
        assert await env.snapshot() == before


@pytest.mark.parametrize(
    ("fault", "limit", "expected"),
    [
        ("missing_price", 6, ["search_products", "get_product_detail", "get_warranty"]),
        ("missing_price", 2, ["search_products", "get_product_detail"]),
        ("missing_price", 1, ["search_products"]),
        ("no_progress", 6, ["search_products", "get_product_detail"]),
        ("duplicate_match", 6, ["search_products"]),
        ("approval", 6, ["search_products"]),
    ],
)
async def test_shared_budget_and_provenance_stop_rules(monkeypatch, fault, limit, expected):
    async with BusinessEnvironment() as env:
        registry = env.service.registry
        search = registry.get("search_products")
        detail = registry.get("get_product_detail")
        original_search, original_detail = search.execute, detail.execute

        async def limited_search(parsed, context):
            result = await original_search(parsed, context)
            products = result.output["products"]
            if fault == "duplicate_match":
                products.append({**products[0], "sku": "SKU-UNRELATED"})
            if fault in {"missing_price", "no_progress"}:
                products[0].pop("price_cents")
            return result

        async def limited_detail(parsed, context):
            result = await original_detail(parsed, context)
            if fault == "no_progress":
                result.output.pop("price_cents")
            return result

        monkeypatch.setattr(search, "execute", limited_search)
        monkeypatch.setattr(detail, "execute", limited_detail)
        original_steps = [
            PlanStep(
                step_id=1,
                goal="catalogue",
                tool_name="search_products",
                arguments={"query": "降噪耳机"},
            ),
        ]
        goals = [
            TaskGoal(
                kind=GoalKind.PRODUCT_PRICE,
                request_text="售价",
                entity_type="product",
                fields=("price_cents",),
            )
        ]
        if fault == "approval":
            goals.append(TaskGoal(kind=GoalKind.CANCEL, request_text="取消", operation="write"))
        else:
            original_steps.append(
                PlanStep(
                    step_id=2,
                    goal="placeholder",
                    tool_name="get_warranty",
                    arguments={"sku": "SKU-GUESSED"},
                )
            )
        state = {
            "plan": AgentPlan(steps=original_steps),
            "user_query": QUERY + " 也要售价。",
            "user_id": "u_demo",
            "session_id": "react-boundary",
            "trace_id": "react-boundary",
            "task_goals": goals,
        }
        async with request_session(env.container.session_factory):
            with capture_tools() as events:
                result = await execute_with_replanning(
                    state,
                    registry=registry,
                    settings=Settings(_env_file=None, react_enabled=True, max_tool_calls=limit),
                )
        assert [event["name"] for event in events] == expected
        assert all(event["arguments"].get("sku") != "SKU-GUESSED" for event in events)
        assert len(result["tool_results"]) == len(result["tool_result_steps"]) == len(expected)
