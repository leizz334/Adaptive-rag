import json
import time

from app.observability.execution import capture_tools
from app.repositories.models import SessionRow
from app.repositories.session_repository import SessionRepository
from app.schemas.chat import ChatRequest
from eval.environment import BusinessEnvironment


async def seed(env, topic):
    async with env.container.session_factory() as db:
        repo = SessionRepository(db)
        await repo.get_or_create("p6", "u_demo")
        await repo.append_message("p6", "user", topic)
        for i in range(10):
            await repo.append_message("p6", "assistant", "已收到")
            await repo.append_message("p6", "user", f"先等等，我还在整理备注 {i}")
        await db.commit()


async def chat(env, message, session=None):
    return await env.service.chat(
        ChatRequest(message=message, session_id=session, user_id="u_demo"), trace_id="p6-context"
    )


async def test_historical_sku_fetches_current_catalog_once():
    async with BusinessEnvironment(memory_mode="M2") as env:
        await seed(env, "前面在看降噪耳机 SKU-HEADSET，之后想查价格和库存。")
        with capture_tools() as events:
            result = await chat(env, "回到刚才那款，帮我查售价和还剩几件。", "p6")
        assert [(e["name"], e["arguments"]) for e in events] == [
            ("get_product_detail", {"sku": "SKU-HEADSET"})
        ]
        assert "299" in result.answer and "42" in result.answer


async def test_identifier_only_turn_resumes_one_incomplete_read():
    async with BusinessEnvironment(memory_mode="M2") as env:
        first = await chat(env, "我想查退款进度，单号还没找到。")
        with capture_tools() as events:
            await chat(env, "找到了，单号是 ORD10002。", first.session_id)
        assert [(e["name"], e["arguments"]) for e in events] == [
            ("get_refund_status", {"order_id": "ORD10002"})
        ]


async def test_task_memory_keeps_evidence_provenance_but_not_old_business_values():
    async with BusinessEnvironment(memory_mode="M2") as env:
        result = await chat(env, "查 ORD10001 的金额。")
        async with env.container.session_factory() as db:
            row = await db.get(SessionRow, result.session_id)
            summary = json.loads(row.summary)
        assert summary["version"] == 2
        task = summary["tasks"][-1]
        assert task["order_ids"] == ["ORD10001"]
        assert task["goals"][0]["status"] == "completed"
        evidence = task["evidence"][0]
        assert evidence["tool"] == "get_order" and "total_cents" in evidence["fields"]
        assert evidence["at"] and "29900" not in json.dumps(evidence)


async def test_p5_summary_is_reindexed_from_its_covered_user_messages():
    async with BusinessEnvironment(memory_mode="M2") as env:
        await seed(env, "请查 ORD10001 的实付金额。")
        async with env.container.session_factory() as db:
            repo = SessionRepository(db)
            original = (await repo.recent_message_rows("p6", limit=100))[0]
            row = await db.get(SessionRow, "p6")
            row.summary = json.dumps(
                {
                    "version": 1,
                    "session_id": "p6",
                    "owner_id": "u_demo",
                    "coverage_message_id": original.id,
                    "source_message_id": original.id,
                    "revision": 1,
                    "order_ids": ["ORD10001"],
                    "text": "旧状态和金额不能作为事实",
                    "expires_at": time.time() + 3600,
                }
            )
            await db.commit()
        with capture_tools() as events:
            await chat(env, "多少钱来着？", "p6")
        assert [(e["name"], e["arguments"]) for e in events] == [
            ("get_order", {"order_id": "ORD10001"})
        ]


async def test_context_bound_payment_gate_uses_actual_unpaid_result():
    async with BusinessEnvironment(memory_mode="M2") as env:
        await seed(env, "稍后我要查刚下的那张订单 ORD10003。")
        async with env.container.session_factory() as db:
            from app.repositories.models import OrderRow

            order = await db.get(OrderRow, "ORD10003")
            order.status, order.paid_at = "created", None
            await db.commit()
        with capture_tools() as events:
            result = await chat(
                env, "那张订单只有在付款成功时才查询商品明细。没付款的话只说明付款状态。", "p6"
            )
        assert [event["name"] for event in events] == ["get_order"]
        assert "未付款" in result.answer and "纯棉T恤" not in result.answer


def test_per_node_budget_keeps_atomic_constraints_and_drops_oversize_history():
    from app.memory.context import SelectedContext
    from app.schemas.goals import GoalKind, TaskGoal

    context = SelectedContext(
        "继续刚才那张单",
        order_id="ORD10001",
        source="session_summary_user_entity",
        structured=True,
        context_budget=170,
        history=("无关的长历史" * 200, "之前提到订单 ORD10001"),
        resumed_goal=TaskGoal(
            kind=GoalKind.ORDER_AMOUNT,
            request_text="只查总额",
            constraints=("不要列商品明细",),
            fields=("total_cents",),
        ),
    )
    intent = context.prompt_context("intent")
    assert "不要列商品明细" in intent and "之前提到" in intent and "无关的长历史" not in intent
    assert "之前提到" not in context.prompt_context("planner")
    assert "不要列商品明细" in context.prompt_context("generate")
    assert context.prompt_context("executor") == ""


async def test_prefaced_correction_with_separate_read_binds_only_the_corrected_order():
    async with BusinessEnvironment(memory_mode="M2") as env:
        with capture_tools() as events:
            await chat(env, "我核对过了，不是 ORD10001，是 ORD10002。把这笔的实付金额告诉我。")
        assert [(e["name"], e["arguments"]) for e in events] == [
            ("get_order", {"order_id": "ORD10002"})
        ]


async def test_supplying_identifier_resumes_read_even_when_model_labels_user_wait_dependency():
    from tests.unit.test_p5_harness_faults import _FaultModel

    model = _FaultModel(
        intent="refund",
        semantics={
            "goal_signals": [
                {"category": "dependency", "kind": "refund_status", "quote": "先等我把单号找出来"},
            ]
        },
    )
    async with BusinessEnvironment(llm=model, memory_mode="M2") as env:
        first = await chat(env, "我想查一张订单的退款进度，先等我把单号找出来。")
        with capture_tools() as events:
            await chat(env, "单号是 ORD10002。", first.session_id)
        assert [(e["name"], e["arguments"]) for e in events] == [
            ("get_refund_status", {"order_id": "ORD10002"})
        ]
