---
name: catalog-title-lookup
description: 用户给出具体商品名称但没有 SKU 时，用名称关键词查商品目录信息，例如在卖的商品名、价格、标签或库存。类别推荐、已有 SKU 的直接查询走各自路径。
metadata:
  adaptive-activation: "catalog"
  adaptive-intents: "product_consult"
  adaptive-goals: "product_detail,product_price,inventory"
  adaptive-tools: "search_products"
---

# 按名称查询商品目录

适用于用户已经指出具体商品名，希望找到对应的目录条目。仅给出偏好、用途或品类并希望推荐时，使用推荐技能。明确提供 SKU 的请求交给 SKU 读取契约。

提取用户原文中的主要商品名称，用 `search_products(query)` 查询目录。查询参数是 1 至 80 字的目录关键词。根据返回的名称和 SKU 对比候选，有多个合理匹配时展示区分信息并等待用户确认。

空结果时告知本次名称查询未匹配，可请用户补充简称或 SKU。回答只引用这次结果中的名称、价格、库存、标签与说明字段。工具执行失败时说明目录暂未取得结果。
