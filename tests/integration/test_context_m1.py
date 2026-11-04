from unittest.mock import patch

import pytest

from app.core.exceptions import InvalidRequestError
from app.observability.execution import capture_tools
from app.schemas.chat import ChatRequest
from eval.environment import BusinessEnvironment
from eval.multiturn import load_scenarios, run_scenarios


async def test_original_seven_reference_cases_use_live_reads_without_gold_changes():
    cases, digest = load_scenarios(
        __import__("pathlib").Path("eval/dataset/agent_v2_extended.json")
    )
    cases = [c for c in cases if c.id == "context_loss" or "_pronoun_" in c.id]
    assert len(cases) == 7
    with patch(
        "eval.multiturn.BusinessEnvironment",
        lambda **kw: BusinessEnvironment(memory_mode="M1", **kw),
    ):
        results = await run_scenarios(cases, dataset_sha256=digest, tracing=False)
    assert all(r.status == "PASS" for r in results), [(r.case_id, r.reasons) for r in results]
    assert all(r.metrics["environment_state_correct"] == 1 for r in results)


async def test_owner_validation_before_context_and_foreign_order_still_denied():
    async with BusinessEnvironment(memory_mode="M1") as env:
        first = await env.service.chat(
            ChatRequest(message="查询订单 ORD10001", user_id="u_demo"), trace_id="first"
        )
        with pytest.raises(InvalidRequestError):
            await env.service.chat(
                ChatRequest(message="它什么状态", user_id="other", session_id=first.session_id),
                trace_id="other",
            )
        foreign = await env.service.chat(
            ChatRequest(message="查询订单 ORD10001", user_id="other"), trace_id="foreign"
        )
        with capture_tools() as calls:
            await env.service.chat(
                ChatRequest(
                    message="它现在是什么状态", user_id="other", session_id=foreign.session_id
                ),
                trace_id="ref",
            )
        assert all(not e["success"] or e["name"] != "get_order" for e in calls)


async def test_ambiguous_reference_never_queries_arbitrary_order():
    async with BusinessEnvironment(memory_mode="M1") as env:
        first = await env.service.chat(
            ChatRequest(message="比较订单 ORD10001 和 ORD10002", user_id="u_demo"), trace_id="two"
        )
        with capture_tools() as calls:
            response = await env.service.chat(
                ChatRequest(
                    message="它现在是什么状态", user_id="u_demo", session_id=first.session_id
                ),
                trace_id="ambiguous",
            )
        assert not calls and "订单" in response.answer
