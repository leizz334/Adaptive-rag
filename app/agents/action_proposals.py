"""User-facing summaries for confirmed business actions."""


def action_summary(tool_name: str, arguments: dict) -> str:
    order_id = arguments.get("order_id", "该订单")
    if tool_name == "cancel_order":
        return f"确认后将取消订单 {order_id}。请核对订单号。"
    if tool_name == "create_refund_request":
        return f"确认后将为订单 {order_id} 提交退款申请；提交不代表退款已到账。"
    if tool_name == "create_return_request":
        return f"确认后将为订单 {order_id} 提交退货申请；提交不代表退款已到账。"
    return "确认后将提交该操作。"
