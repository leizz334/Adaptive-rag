---
name: order-cancellation
description: 为用户明确要求取消的订单核对订单状态和权限，按订单号准备待确认取消操作；适用于取消动作，取消规则或已取消状态查询只需政策检索或只读订单查询。
metadata:
  adaptive-intents: "cancel_order"
  adaptive-goals: "cancel"
  adaptive-tools: "get_order,cancel_order"
  adaptive-activation: "action"
  adaptive-legacy-name: "order_cancellation"
  adaptive-legacy-description: "取消尚未发货订单的确认流程"
  adaptive-legacy-triggers: "取消订单|不想要了"
  adaptive-legacy-intents: "cancel_order"
---

# 订单取消

用户明确要求取消时使用。仅询问取消政策、订单是否已经取消或尚未核实的外部条件时，按相应只读业务或澄清路径处理。

## Steps

- 核对订单号与当前状态
- 明确用户希望取消后，先展示待确认操作
- 收到确认后执行取消

读取 `get_order(order_id)` 时使用已校验的订单号和当前用户权限。`created` 或 `paid` 是当前支持取消的订单状态。未查到有效状态时说明缺少证据，发货后说明取消路径不适用，并等待用户选择是否需要其他售后帮助。

明确取消且订单符合条件时，准备绑定该订单的 `cancel_order` 待确认操作。用户确认后由既有执行链重新校验用户归属与订单状态。工具成功返回 `status: cancelled` 后才能告知订单已取消。取消操作的输出不含退款到账证据。
