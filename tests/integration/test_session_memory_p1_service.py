from app.observability.execution import capture_tools
from app.repositories.models import OrderRow
from app.repositories.session_repository import SessionRepository
from app.schemas.chat import ChatRequest
from eval.environment import BusinessEnvironment


async def test_elliptical_shipping_followup_reads_fresh_state_and_persists_raw_query():
    async with BusinessEnvironment(memory_mode="M2") as env:
        first = await env.service.chat(
            ChatRequest(user_id="u_demo", message="订单 ORD10003 现在什么状态？"),
            trace_id="p1_initial",
        )
        async with env.container.session_factory() as db:
            order = await db.get(OrderRow, "ORD10003")
            order.status = "shipped"
            order.shipped_at = order.paid_at
            order.tracking_no = "P1SYNTHETIC"
            await db.commit()

        followup = "现在发货了吗？"
        with capture_tools() as calls:
            await env.service.chat(
                ChatRequest(user_id="u_demo", session_id=first.session_id, message=followup),
                trace_id="p1_followup",
            )
        assert any(
            call["name"] == "get_order"
            and call["arguments"].get("order_id") == "ORD10003"
            and call["output"].get("status") == "shipped"
            for call in calls
        )

        async with env.container.session_factory() as db:
            history = await SessionRepository(db).recent_messages(first.session_id)
        assert history[-2].content == followup


async def test_ambiguous_order_does_not_dispatch_and_current_correction_uses_new_target():
    async with BusinessEnvironment(memory_mode="M2") as env:
        session_id = None
        for index, message in enumerate(("查一下 ORD10001 状态。", "也查一下 ORD10002 状态。")):
            response = await env.service.chat(
                ChatRequest(message=message, user_id="u_demo", session_id=session_id),
                trace_id=f"p1_setup_{index}",
            )
            session_id = response.session_id

        with capture_tools() as calls:
            response = await env.service.chat(
                ChatRequest(message="这单现在什么状态？", user_id="u_demo", session_id=session_id),
                trace_id="p1_ambiguous",
            )
        assert not calls and "请明确" in response.answer

        correction = "不是 ORD10002，是 ORD10001，查一下状态。"
        with capture_tools() as calls:
            await env.service.chat(
                ChatRequest(message=correction, user_id="u_demo", session_id=session_id),
                trace_id="p1_correction",
            )
        assert any(c["name"] == "get_order" and c["success"] for c in calls)
        assert {c["arguments"]["order_id"] for c in calls if "order_id" in c["arguments"]} == {
            "ORD10001"
        }
        async with env.container.session_factory() as db:
            history = await SessionRepository(db).recent_messages(session_id)
        assert history[-2].content == correction
