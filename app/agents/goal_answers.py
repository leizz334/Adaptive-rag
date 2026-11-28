"""Render bounded observations in offline mode, one requested fact at a time.

Reuses the allowlisted business fact formatting from historical cdc4b92.
"""

from collections.abc import Sequence
from decimal import Decimal

from app.agents.state import AgentState
from app.schemas.agent import AgentPlan, ToolResult
from app.schemas.goals import GoalKind, TaskGoal
from app.tools.goal_contract import CAPABILITIES, observed_goal

G = GoalKind
ORDER_STATUS = {
    "created": "待支付",
    "paid": "已支付",
    "shipped": "已发货",
    "delivered": "已签收",
    "cancelled": "已取消",
    "refunding": "退款中",
    "refunded": "已退款",
}
SHIPMENT_STATUS = {"warehouse": "仓库处理中", "in_transit": "运输中", "delivered": "已签收"}
_REFUND_STATUS = {
    "requested": "已申请",
    "processing": "处理中",
    "completed": "已完成",
    "rejected": "被拒绝",
}
_LABELS = {
    G.ORDER_STATUS: "订单状态",
    G.ORDER_PAYMENT: "订单支付状态",
    G.ORDER_AMOUNT: "订单金额",
    G.ORDER_ITEMS: "订单商品明细",
    G.SHIPMENT: "物流状态",
    G.TRACKING_NUMBER: "运单号",
    G.REFUND_STATUS: "退款进度",
    G.INVENTORY: "库存",
    G.PRODUCT_DETAIL: "商品资料",
    G.PRODUCT_PRICE: "商品价格",
    G.POLICY: "政策资料",
}
_UNAVAILABLE_LABELS = {
    "scan_location": "实际扫描地点",
    "estimated_delivery_at": "预计送达时间",
    "product_attribute": "独立的商品属性字段",
}
_WORKFLOW_SKIP = {
    "condition_false": "订单尚未付款，条件不成立，已跳过后续查询。",
    "condition_unknown": "未取得足够证据确认条件成立，已跳过后续查询。",
    "prerequisite_failed": "前置查询失败，已跳过依赖该结果的查询。",
    "prerequisite_skipped": "前置步骤未执行，已跳过依赖该结果的查询。",
    "limit_reached": "已达到本次查询步骤上限，未执行该查询。",
}
_WORKFLOW_ACTION_ANSWERS = {
    "ineligible": "当前订单状态不符合取消条件，未创建待确认操作。",
    "unverified": "暂时无法核验办理所需的订单信息，未创建待确认操作。",
    "failed": "无法查询该订单。请核对订单号或稍后重试。",
}
_SKILL_CLARIFICATIONS = {
    "order_id": "请提供或明确要处理的订单号。",
    "return_reason": "请说明申请退货的原因，确认后才会提交。",
    "return_scope": "当前只能提交订单级退货申请。请明确是否退整单；单件退货需人工核对。",
}
_CONFIRMED_OUTCOMES = {
    "cancel_order": ("cancelled", None, "订单 {order_id} 已取消。"),
    "create_refund_request": (
        "requested",
        "refund_id",
        "订单 {order_id} 的退款申请已提交，尚不代表款项到账。",
    ),
    "create_return_request": (
        "requested",
        "return_id",
        "订单 {order_id} 的退货申请已提交，尚不代表退款完成。",
    ),
}


def _money(cents: int) -> str:
    return f"{Decimal(cents) / 100:.2f} 元"


def _render(goal: TaskGoal, data: dict) -> str:
    kind = goal.kind
    if kind == G.ORDER_STATUS:
        return ORDER_STATUS[data["status"]]
    if kind == G.ORDER_PAYMENT:
        return f"已支付，支付时间 {data['paid_at']}" if data["paid_at"] else "暂无支付时间记录"
    if kind in {G.ORDER_AMOUNT, G.PRODUCT_PRICE}:
        return _money(data["total_cents"] if kind == G.ORDER_AMOUNT else data["price_cents"])
    if kind == G.ORDER_ITEMS:
        if "items" not in goal.fields:
            return (
                "、".join(
                    f"{item['name']}（{'定制' if item['customized'] else '非定制'}）"
                    for item in data["items"]
                )
                or "暂无商品明细"
            )
        return (
            "、".join(
                f"{item['name']}（{item['sku']}，{item['quantity']} 件，单价 {_money(item['unit_price_cents'])}，"
                f"{'定制' if item['customized'] else '非定制'}）"
                for item in data["items"]
            )
            or "暂无商品明细"
        )
    if kind == G.SHIPMENT:
        return (
            " → ".join(
                f"{SHIPMENT_STATUS.get(event['status'], '状态未知')}（{event['at']}）"
                for event in data["events"]
            )
            or "暂无物流轨迹"
        )
    if kind == G.TRACKING_NUMBER:
        return data["tracking_no"] or "暂无运单号"
    if kind == G.INVENTORY:
        return f"{data['inventory']} 件"
    if kind == G.REFUND_STATUS:
        return (
            "、".join(
                f"退款单 {row['refund_id']} {_REFUND_STATUS.get(row['status'], '状态未知')}（{_money(row['amount_cents'])}）"
                for row in data["refunds"]
            )
            or "暂未查询到退款申请记录"
        )
    if kind == G.PRODUCT_DETAIL:
        return "，".join(data[field] for field in goal.fields)
    return str(data["chunks"][0]["content"])[:240]


def render_goal_answer(
    goals: Sequence[TaskGoal],
    plan: AgentPlan,
    results: Sequence[ToolResult],
    result_steps: Sequence[int] = (),
) -> str:
    lines = []
    missing = set()
    for goal in goals:
        if goal.negated:
            continue
        if goal.kind == G.UNKNOWN and goal.independent:
            missing.add("request")
        if goal.kind not in _LABELS:
            continue
        if goal.independent and goal.clarification:
            missing.update(goal.clarification)
            continue
        target = f"{goal.entity_id} " if goal.entity_id else ""
        for field in goal.unavailable_fields:
            lines.append(f"{target}{_UNAVAILABLE_LABELS.get(field, '所需信息')}：暂未取得证据。")
        if not goal.fields:
            continue
        result = find_goal_observation(goal, plan, results, result_steps)
        value = _render(goal, result.output) if result else "暂未取得证据"
        lines.append(f"{target}{_LABELS[goal.kind]}：{value}。")
    if "order_id" in missing:
        lines.append("请补充其余查询所需的订单号。")
    if "sku" in missing:
        lines.append("请补充其余查询所需的商品 SKU。")
    if "request" in missing:
        lines.append("其余请求暂未取得证据，请补充需要核对的具体内容。")
    return "\n".join(lines)


def find_goal_observation(
    goal: TaskGoal,
    plan: AgentPlan,
    results: Sequence[ToolResult],
    result_steps: Sequence[int] = (),
) -> ToolResult | None:
    correlated = len(results) == len(result_steps)
    for index, result in enumerate(results):
        capability = CAPABILITIES.get(result.name)
        if capability is None or "fallback_from" in result.output:
            continue
        steps = [
            step
            for step in plan.steps
            if step.tool_name == result.name
            and (not correlated or step.step_id == result_steps[index])
        ]
        if not correlated and len(steps) != 1 and not capability.returned_entity:
            continue
        if any(observed_goal(goal, step.arguments, result) for step in steps):
            return result
    return None


def bounded_read_answer(state: AgentState) -> str | None:
    plan = state.get("plan")
    if plan is None:
        return None
    goals = state.get("task_goals", [])
    if plan.skill_clarification:
        return _SKILL_CLARIFICATIONS[plan.skill_clarification]
    if state.get("workflow_error"):
        return "暂时无法安全执行此业务流程，请核对请求或稍后重试。"
    if plan.skill_mode == "workflow":
        return _workflow_answer(state, plan, goals)
    if plan.planning_strategy == "confirmed":
        return _confirmed_answer(state)
    active = [goal for goal in goals if not goal.negated]
    exact_reads = (
        plan.read_contract_mode == "full"
        and plan.read_contract_applied
        and active
        and all(
            goal.operation == "read" and goal.kind in _LABELS and goal.kind != G.POLICY
            for goal in active
        )
    )
    if plan.read_contract_mode == "partial" or exact_reads:
        return render_goal_answer(
            goals, plan, state.get("tool_results") or [], state.get("tool_result_steps", ())
        )
    if plan.read_contract_mode == "clarify":
        if any(goal.conditions for goal in goals):
            return "这些查询取决于前置条件，请确认满足什么条件后再查。"
        missing = {item for goal in goals if not goal.negated for item in goal.clarification}
        if "order_id" in missing:
            return "请明确要查询的订单号。"
        if "sku" in missing:
            return "请提供要查询的商品 SKU。"
        return "现有证据不足，请补充需要核对的具体内容。"
    return None


def _confirmed_answer(state: AgentState) -> str | None:
    """Report only the verified status returned by the confirmed operation."""
    action = state.get("confirmed_action")
    outcome = _CONFIRMED_OUTCOMES.get(action.tool_name) if action else None
    if action is None or outcome is None:
        return None
    status, result_id, answer = outcome
    order_id = action.arguments.get("order_id")
    for result in state.get("tool_results") or []:
        if not (result.success and not result.truncated and result.name == action.tool_name):
            continue
        output = result.output
        request_id = output.get(result_id) if result_id else None
        if (
            isinstance(order_id, str)
            and output.get("order_id") == order_id
            and output.get("status") == status
            and (result_id is None or isinstance(request_id, str) and request_id.strip())
        ):
            return answer.format(order_id=order_id)
    return "暂未核实操作结果。请查看订单状态或联系人工客服。"


def _workflow_answer(state: AgentState, plan: AgentPlan, goals: Sequence[TaskGoal]) -> str | None:
    statuses = state.get("workflow_step_statuses", {})
    results = state.get("tool_results", ())
    result_steps = state.get("tool_result_steps", ())
    notices = []
    blocked: set[tuple[GoalKind, str]] = set()
    for step in plan.steps:
        status = statuses.get(step.step_id)
        if status is None or status not in _WORKFLOW_SKIP:
            continue
        capability = CAPABILITIES.get(step.tool_name or "")
        argument = step.arguments.get(capability.argument) if capability else None
        if capability and isinstance(argument, str):
            blocked.update((kind, argument) for kind in capability.goals)
        notices.append(_WORKFLOW_SKIP[status])
    available_goals = [
        goal
        for goal in goals
        if (goal.kind, goal.request_text if goal.kind == G.POLICY else goal.entity_id)
        not in blocked
        or find_goal_observation(goal, plan, results, result_steps) is not None
    ]
    facts = render_goal_answer(available_goals, plan, results, result_steps)
    outcome = state.get("workflow_action_status")
    if outcome:
        if message := _WORKFLOW_ACTION_ANSWERS.get(outcome):
            notices.append(message)
    if facts:
        notices.append(facts)
    if notices:
        return "\n".join(dict.fromkeys(notices))
    return None if state.get("pending_action") else "暂未取得完成该请求所需的证据。"


def compound_read_evidence(state: AgentState) -> str | None:
    """Canonical fallback for a compound factual read, leaving RAG policy answers intact."""
    plan = state.get("plan")
    goals = [goal for goal in state.get("task_goals", []) if not goal.negated]
    if plan is None or not plan.read_contract_applied or len(goals) < 2:
        return None
    if any(goal.kind == G.POLICY for goal in goals):
        return None
    return render_goal_answer(
        goals, plan, state.get("tool_results") or [], state.get("tool_result_steps", ())
    )
