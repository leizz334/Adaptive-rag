---
name: return-request
description: 为明确要寄回商品的用户准备退货申请，核对订单、商品、退货原因和适用规则，再生成待确认操作。仅询问退货政策、只要退款或申请换货时采用对应的业务路径。
metadata:
  adaptive-intents: "return_exchange"
  adaptive-goals: "return_request"
  adaptive-tools: "get_order,get_order_items,search_knowledge,create_return_request"
  adaptive-activation: "action"
  adaptive-legacy-name: "return_handling"
  adaptive-legacy-description: "退货处理标准流程"
  adaptive-legacy-triggers: "退货|换货|7天无理由"
  adaptive-legacy-intents: "return_exchange,refund"
---

# 退货申请

确认用户确实希望提交寄回商品的退货申请。问“可以退吗”属于资格咨询。只退钱的请求和换货履约有各自的能力边界。

## Steps

- 确认订单号与商品是否定制
- 检索退换货政策
- 判断是否在时效内
- 如需提交申请则创建待确认写操作

核实订单归属。用 `get_order_items` 查看商品、数量和 `customized` 字段。涉及资格与时效时依据政策检索和订单证据，政策依据不足时说明。用户需要选择某一件商品或仅退部分数量时，需要澄清订单级退货工具当前无法绑定单独 SKU 或件数。

`create_return_request` 使用可信订单号和用户说明的退货原因，原因长度 1 至 200 字。原因缺失时询问用户。生成待确认操作后等待正式确认，再走原执行链。只有成功返回 `return_id` 才能说退货申请已受理。系统未从该工具取得退款到账或退件物流事实。
