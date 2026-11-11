# P4-D 人工语义审核包（P4-E整理）

20条原始交互：14消融回答+6基线HTTP结果。全部标签空白，完整语义NOT_ASSESSED。请逐项填写CSV；可选PASS/FAIL/UNCERTAIN/NOT_APPLICABLE，不能把受限工具成功当整体语义正确。

事实：每项事实是否符合实时工具与文档？完整性：是否回答任务所有目标？忠实度：是否只陈述已有证据？业务终态：是否满足授权且无重复写入？无答复的401/400反例请将回答语义标NOT_APPLICABLE，另核对安全拒绝。

D场景独立样本极小；本包不是新盲测，不是经验批准。

## E_SEM_01｜D_MEM_DEV｜M0｜development

**问题**：它现在的总金额是多少？

**原始回答**：

```text
请提供要处理的订单号，确认后我才能继续。
```

**Gold/历史条件（仅审核员可见）**：

```json
{
  "id": "D_MEM_DEV",
  "split": "development",
  "kind": "memory",
  "order": "ORD93041",
  "cents": 23780,
  "old_cents": 11100,
  "query": "它现在的总金额是多少？",
  "history": [
    [
      "user",
      "请记住我们刚查询的是 ORD93041。"
    ],
    [
      "assistant",
      "旧查询金额111.00元，仅为历史记录。"
    ]
  ]
}
```

**实际引用与工具**：

```json
{
  "citations": [],
  "tools": []
}
```

**原始证据**：[查看完整请求/业务前后态](../p4_ablation_evaluation/runs/ubuntu_D_20261111_01/request_p4c_39dd6c4e7ad6447c9f98bb06d5023938.json)
 SHA256 `d172f5aef95927077cea8c15b8a81f4a7d6e0a1e140d24652b8e44f98cb180d0`

事实：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；完整性：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A

忠实度：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；业务终态：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A

整体：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；审核者：______ 时间：______ 说明：______

## E_SEM_02｜D_MEM_DEV｜M1｜development

**问题**：它现在的总金额是多少？

**原始回答**：

```text
订单 ORD93041 当前总金额为 237.80 元（total_cents: 23780）。该金额来自实时订单查询结果，订单状态为已支付（paid）。
```

**Gold/历史条件（仅审核员可见）**：

```json
{
  "id": "D_MEM_DEV",
  "split": "development",
  "kind": "memory",
  "order": "ORD93041",
  "cents": 23780,
  "old_cents": 11100,
  "query": "它现在的总金额是多少？",
  "history": [
    [
      "user",
      "请记住我们刚查询的是 ORD93041。"
    ],
    [
      "assistant",
      "旧查询金额111.00元，仅为历史记录。"
    ]
  ]
}
```

**实际引用与工具**：

```json
{
  "citations": [],
  "tools": [
    {
      "name": "get_order",
      "arguments": {
        "order_id": "ORD93041"
      },
      "success": true,
      "status": "executed",
      "failure_kind": null,
      "output": {
        "order_id": "ORD93041",
        "user_id": "u_demo",
        "status": "paid",
        "items": [],
        "total_cents": 23780,
        "created_at": "2026-11-11T05:34:34.052942Z",
        "paid_at": null,
        "shipped_at": null,
        "delivered_at": null,
        "tracking_no": null,
        "receiver_city": null
      }
    }
  ]
}
```

**原始证据**：[查看完整请求/业务前后态](../p4_ablation_evaluation/runs/ubuntu_D_20261111_01/request_p4c_552afa75b16c4aaaa6c391c6983b4805.json)
 SHA256 `667af4155f8c3c08ee8c8bcbb3b175ef315dc183fc4e8e2026977be5b3c9ed60`

事实：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；完整性：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A

忠实度：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；业务终态：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A

整体：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；审核者：______ 时间：______ 说明：______

## E_SEM_03｜D_MEM_DEV｜M2｜development

**问题**：它现在的总金额是多少？

**原始回答**：

```text
订单 ORD93041 的实时查询结果显示：总金额为 23780 分，即 237.80 元；当前状态为 paid（已支付）。该订单的商品明细为空，因此无法核对金额构成；如需明细或发票信息，请补充说明或转人工核实。
```

**Gold/历史条件（仅审核员可见）**：

```json
{
  "id": "D_MEM_DEV",
  "split": "development",
  "kind": "memory",
  "order": "ORD93041",
  "cents": 23780,
  "old_cents": 11100,
  "query": "它现在的总金额是多少？",
  "history": [
    [
      "user",
      "请记住我们刚查询的是 ORD93041。"
    ],
    [
      "assistant",
      "旧查询金额111.00元，仅为历史记录。"
    ]
  ]
}
```

**实际引用与工具**：

```json
{
  "citations": [],
  "tools": [
    {
      "name": "get_order",
      "arguments": {
        "order_id": "ORD93041"
      },
      "success": true,
      "status": "executed",
      "failure_kind": null,
      "output": {
        "order_id": "ORD93041",
        "user_id": "u_demo",
        "status": "paid",
        "items": [],
        "total_cents": 23780,
        "created_at": "2026-11-11T05:34:34.052942Z",
        "paid_at": null,
        "shipped_at": null,
        "delivered_at": null,
        "tracking_no": null,
        "receiver_city": null
      }
    }
  ]
}
```

**原始证据**：[查看完整请求/业务前后态](../p4_ablation_evaluation/runs/ubuntu_D_20261111_01/request_p4c_05ff3a52cfef46fcab711bdd0f7e996c.json)
 SHA256 `972df7c9d83b079666adc304c2b75a54e95a6e1fc4ee4edf6fdcf16f2a5a8d94`

事实：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；完整性：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A

忠实度：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；业务终态：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A

整体：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；审核者：______ 时间：______ 说明：______

## E_SEM_04｜D_MEM_TEST｜M2｜independent_test

**问题**：之前那笔订单此刻的总额是多少？

**原始回答**：

```text
订单 ORD93042 的实时查询结果显示：当前状态为已支付（paid），订单总额为 58620 分，即 586.20 元。商品明细为空，因此无法核对各商品金额构成；如需明细，请补充信息或转人工核实。
```

**Gold/历史条件（仅审核员可见）**：

```json
{
  "id": "D_MEM_TEST",
  "split": "independent_test",
  "kind": "memory",
  "order": "ORD93042",
  "cents": 58620,
  "old_cents": 22200,
  "query": "之前那笔订单此刻的总额是多少？",
  "history": [
    [
      "user",
      "前面核对的是 ORD93042。"
    ],
    [
      "assistant",
      "过去看到的金额是222.00元。"
    ],
    [
      "user",
      "谢谢，请继续保持简洁。"
    ],
    [
      "assistant",
      "好的。"
    ],
    [
      "user",
      "谢谢，请继续保持简洁。"
    ],
    [
      "assistant",
      "好的。"
    ],
    [
      "user",
      "谢谢，请继续保持简洁。"
    ],
    [
      "assistant",
      "好的。"
    ],
    [
      "user",
      "谢谢，请继续保持简洁。"
    ],
    [
      "assistant",
      "好的。"
    ],
    [
      "user",
      "谢谢，请继续保持简洁。"
    ],
    [
      "assistant",
      "好的。"
    ]
  ]
}
```

**实际引用与工具**：

```json
{
  "citations": [],
  "tools": [
    {
      "name": "get_order",
      "arguments": {
        "order_id": "ORD93042"
      },
      "success": true,
      "status": "executed",
      "failure_kind": null,
      "output": {
        "order_id": "ORD93042",
        "user_id": "u_demo",
        "status": "paid",
        "items": [],
        "total_cents": 58620,
        "created_at": "2026-11-11T05:34:34.054147Z",
        "paid_at": null,
        "shipped_at": null,
        "delivered_at": null,
        "tracking_no": null,
        "receiver_city": null
      }
    }
  ]
}
```

**原始证据**：[查看完整请求/业务前后态](../p4_ablation_evaluation/runs/ubuntu_D_20261111_01/request_p4c_f468541828a14a309285b1c51bf3d21d.json)
 SHA256 `54ebe9ce3e77a896202f67804795d9ab3d1b3d936d8127195f173c76fa87752d`

事实：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；完整性：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A

忠实度：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；业务终态：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A

整体：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；审核者：______ 时间：______ 说明：______

## E_SEM_05｜D_MEM_TEST｜M1｜independent_test

**问题**：之前那笔订单此刻的总额是多少？

**原始回答**：

```text
请明确需要处理的订单号；当前会话指代不明确。
```

**Gold/历史条件（仅审核员可见）**：

```json
{
  "id": "D_MEM_TEST",
  "split": "independent_test",
  "kind": "memory",
  "order": "ORD93042",
  "cents": 58620,
  "old_cents": 22200,
  "query": "之前那笔订单此刻的总额是多少？",
  "history": [
    [
      "user",
      "前面核对的是 ORD93042。"
    ],
    [
      "assistant",
      "过去看到的金额是222.00元。"
    ],
    [
      "user",
      "谢谢，请继续保持简洁。"
    ],
    [
      "assistant",
      "好的。"
    ],
    [
      "user",
      "谢谢，请继续保持简洁。"
    ],
    [
      "assistant",
      "好的。"
    ],
    [
      "user",
      "谢谢，请继续保持简洁。"
    ],
    [
      "assistant",
      "好的。"
    ],
    [
      "user",
      "谢谢，请继续保持简洁。"
    ],
    [
      "assistant",
      "好的。"
    ],
    [
      "user",
      "谢谢，请继续保持简洁。"
    ],
    [
      "assistant",
      "好的。"
    ]
  ]
}
```

**实际引用与工具**：

```json
{
  "citations": [],
  "tools": []
}
```

**原始证据**：[查看完整请求/业务前后态](../p4_ablation_evaluation/runs/ubuntu_D_20261111_01/request_p4c_d8cbed92273249d595f1970513cb2b83.json)
 SHA256 `d65913c0861be4cb48546510406490800fcd867ab641e02c0552088b72b590d3`

事实：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；完整性：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A

忠实度：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；业务终态：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A

整体：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；审核者：______ 时间：______ 说明：______

## E_SEM_06｜D_MEM_TEST｜M0｜independent_test

**问题**：之前那笔订单此刻的总额是多少？

**原始回答**：

```text
请提供要处理的订单号，确认后我才能继续。
```

**Gold/历史条件（仅审核员可见）**：

```json
{
  "id": "D_MEM_TEST",
  "split": "independent_test",
  "kind": "memory",
  "order": "ORD93042",
  "cents": 58620,
  "old_cents": 22200,
  "query": "之前那笔订单此刻的总额是多少？",
  "history": [
    [
      "user",
      "前面核对的是 ORD93042。"
    ],
    [
      "assistant",
      "过去看到的金额是222.00元。"
    ],
    [
      "user",
      "谢谢，请继续保持简洁。"
    ],
    [
      "assistant",
      "好的。"
    ],
    [
      "user",
      "谢谢，请继续保持简洁。"
    ],
    [
      "assistant",
      "好的。"
    ],
    [
      "user",
      "谢谢，请继续保持简洁。"
    ],
    [
      "assistant",
      "好的。"
    ],
    [
      "user",
      "谢谢，请继续保持简洁。"
    ],
    [
      "assistant",
      "好的。"
    ],
    [
      "user",
      "谢谢，请继续保持简洁。"
    ],
    [
      "assistant",
      "好的。"
    ]
  ]
}
```

**实际引用与工具**：

```json
{
  "citations": [],
  "tools": []
}
```

**原始证据**：[查看完整请求/业务前后态](../p4_ablation_evaluation/runs/ubuntu_D_20261111_01/request_p4c_6e26b1fdd628452b9d7ea2f4673a3c29.json)
 SHA256 `0bb54925dcfb23139215fb3ea428cee8bbce5de823ef6917cd89dbd3eae419b7`

事实：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；完整性：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A

忠实度：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；业务终态：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A

整体：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；审核者：______ 时间：______ 说明：______

## E_SEM_07｜D_Q01｜BM25｜development

**问题**：澄舟 K17 电水壶的无理由退货政策是什么，签收后多少天内可以退，必须满足什么条件？

**原始回答**：

```text
澄舟 K17 电水壶的无理由退货政策如下：自签收之日起14天内可申请无理由退货（D_R01）。必须满足的条件是：未通电使用、壶体无损、原包装及配件齐全；已烧水的商品不适用无理由退货（D_R01）。以上为评测用合成政策，不代表真实商家；实际退货请以订单页展示的商家政策为准。如需进一步核实，请提供订单号或转人工确认。
```

**Gold/历史条件（仅审核员可见）**：

```json
{
  "id": "D_Q01",
  "split": "development",
  "kind": "rag",
  "query": "澄舟 K17 电水壶的无理由退货政策是什么，签收后多少天内可以退，必须满足什么条件？",
  "relevant_ids": [
    "D_R01"
  ],
  "atoms": [
    [
      "14天",
      "14 天"
    ],
    [
      "未通电",
      "未使用",
      "没有通电"
    ],
    [
      "包装"
    ],
    [
      "配件",
      "附件"
    ],
    [
      "不适用",
      "不能",
      "不可",
      "不支持"
    ]
  ],
  "forbidden": [
    "已烧水也可无理由退货"
  ],
  "required_source_facts": [
    "自签收之日起14天内可申请无理由退货",
    "未通电使用、壶体无损且原包装及配件齐全",
    "已烧水不适用无理由退货"
  ]
}
```

**实际引用与工具**：

```json
{
  "citations": [
    {
      "document_id": "D_R01",
      "title": "虚构政策：澄舟电水壶退货",
      "chunk_id": "D_R01",
      "section": null
    }
  ],
  "tools": []
}
```

**原始证据**：[查看完整请求/业务前后态](../p4_ablation_evaluation/runs/ubuntu_D_20261111_01/request_p4c_793d4e7168a7474184b084cbe0170d63.json)
 SHA256 `55bcb33f1b167e7d0e3a8b10554b3899e52cffce169d6d0af48452100b2391a1`

事实：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；完整性：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A

忠实度：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；业务终态：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A

整体：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；审核者：______ 时间：______ 说明：______

## E_SEM_08｜D_Q01｜DENSE｜development

**问题**：澄舟 K17 电水壶的无理由退货政策是什么，签收后多少天内可以退，必须满足什么条件？

**原始回答**：

```text
澄舟 K17 电水壶的无理由退货政策如下：自签收之日起 14 天内可申请无理由退货；需满足未通电使用、壶体无损、原包装及配件齐全；已烧水的商品不适用无理由退货。以上为评测政策说明，不代表真实商家；实际以平台/商家页面为准。若需办理，请提供订单号，我可协助发起退货确认（不会直接完成操作）。
```

**Gold/历史条件（仅审核员可见）**：

```json
{
  "id": "D_Q01",
  "split": "development",
  "kind": "rag",
  "query": "澄舟 K17 电水壶的无理由退货政策是什么，签收后多少天内可以退，必须满足什么条件？",
  "relevant_ids": [
    "D_R01"
  ],
  "atoms": [
    [
      "14天",
      "14 天"
    ],
    [
      "未通电",
      "未使用",
      "没有通电"
    ],
    [
      "包装"
    ],
    [
      "配件",
      "附件"
    ],
    [
      "不适用",
      "不能",
      "不可",
      "不支持"
    ]
  ],
  "forbidden": [
    "已烧水也可无理由退货"
  ],
  "required_source_facts": [
    "自签收之日起14天内可申请无理由退货",
    "未通电使用、壶体无损且原包装及配件齐全",
    "已烧水不适用无理由退货"
  ]
}
```

**实际引用与工具**：

```json
{
  "citations": [
    {
      "document_id": "D_R01",
      "title": "虚构政策：澄舟电水壶退货",
      "chunk_id": "D_R01",
      "section": null
    }
  ],
  "tools": []
}
```

**原始证据**：[查看完整请求/业务前后态](../p4_ablation_evaluation/runs/ubuntu_D_20261111_01/request_p4c_7b7d4ccd00834df994b66446edfb6a4d.json)
 SHA256 `f4dd4d40b552c59c373928c5269815470be2fae9be04d2095322ae4b9d0b9079`

事实：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；完整性：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A

忠实度：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；业务终态：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A

整体：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；审核者：______ 时间：______ 说明：______

## E_SEM_09｜D_Q01｜HYBRID｜development

**问题**：澄舟 K17 电水壶的无理由退货政策是什么，签收后多少天内可以退，必须满足什么条件？

**原始回答**：

```text
澄舟 K17 电水壶的无理由退货政策如下：自签收之日起14天内可申请无理由退货；须满足未通电使用、壶体无损、原包装及配件齐全；已烧水的商品不适用无理由退货。以上为评测政策说明，不代表真实商家政策。若需办理退货，请提供订单号，以便进一步核实并转人工确认。
```

**Gold/历史条件（仅审核员可见）**：

```json
{
  "id": "D_Q01",
  "split": "development",
  "kind": "rag",
  "query": "澄舟 K17 电水壶的无理由退货政策是什么，签收后多少天内可以退，必须满足什么条件？",
  "relevant_ids": [
    "D_R01"
  ],
  "atoms": [
    [
      "14天",
      "14 天"
    ],
    [
      "未通电",
      "未使用",
      "没有通电"
    ],
    [
      "包装"
    ],
    [
      "配件",
      "附件"
    ],
    [
      "不适用",
      "不能",
      "不可",
      "不支持"
    ]
  ],
  "forbidden": [
    "已烧水也可无理由退货"
  ],
  "required_source_facts": [
    "自签收之日起14天内可申请无理由退货",
    "未通电使用、壶体无损且原包装及配件齐全",
    "已烧水不适用无理由退货"
  ]
}
```

**实际引用与工具**：

```json
{
  "citations": [
    {
      "document_id": "D_R01",
      "title": "虚构政策：澄舟电水壶退货",
      "chunk_id": "D_R01",
      "section": null
    }
  ],
  "tools": []
}
```

**原始证据**：[查看完整请求/业务前后态](../p4_ablation_evaluation/runs/ubuntu_D_20261111_01/request_p4c_bcd75aa5a27c4d669db82b178c8966ae.json)
 SHA256 `6aac4fc90df77ab15c5bcf69b9501566bde1ad8a56fe550104874de6bcd15aa0`

事实：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；完整性：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A

忠实度：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；业务终态：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A

整体：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；审核者：______ 时间：______ 说明：______

## E_SEM_10｜D_Q01｜RERANK｜development

**问题**：澄舟 K17 电水壶的无理由退货政策是什么，签收后多少天内可以退，必须满足什么条件？

**原始回答**：

```text
澄舟 K17 电水壶的无理由退货政策如下：自签收之日起 14 天内可申请无理由退货；需满足未通电使用、壶体无损、原包装及配件齐全；已烧水的商品不适用无理由退货。以上依据为评测用合成政策，不代表真实商家规则。若需办理，请提供订单号，我将为您发起退货确认；是否最终可退仍需以订单实际状态和商家确认为准。
```

**Gold/历史条件（仅审核员可见）**：

```json
{
  "id": "D_Q01",
  "split": "development",
  "kind": "rag",
  "query": "澄舟 K17 电水壶的无理由退货政策是什么，签收后多少天内可以退，必须满足什么条件？",
  "relevant_ids": [
    "D_R01"
  ],
  "atoms": [
    [
      "14天",
      "14 天"
    ],
    [
      "未通电",
      "未使用",
      "没有通电"
    ],
    [
      "包装"
    ],
    [
      "配件",
      "附件"
    ],
    [
      "不适用",
      "不能",
      "不可",
      "不支持"
    ]
  ],
  "forbidden": [
    "已烧水也可无理由退货"
  ],
  "required_source_facts": [
    "自签收之日起14天内可申请无理由退货",
    "未通电使用、壶体无损且原包装及配件齐全",
    "已烧水不适用无理由退货"
  ]
}
```

**实际引用与工具**：

```json
{
  "citations": [
    {
      "document_id": "D_R01",
      "title": "虚构政策：澄舟电水壶退货",
      "chunk_id": "D_R01",
      "section": null
    }
  ],
  "tools": []
}
```

**原始证据**：[查看完整请求/业务前后态](../p4_ablation_evaluation/runs/ubuntu_D_20261111_01/request_p4c_3cff0e29e8cb4f07baee6d110c5cef97.json)
 SHA256 `bf6d60ac0a24561bd5bfa9e9aea86a893e36bcb3a7131e844dd5f53f2fdc68ce`

事实：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；完整性：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A

忠实度：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；业务终态：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A

整体：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；审核者：______ 时间：______ 说明：______

## E_SEM_11｜D_Q02｜RERANK｜independent_test

**问题**：晴栈 H26 蓝牙耳机日常使用时一边听不到声音，售后能免费修多久？申请要拿什么证明，泡水弄坏也算吗？

**原始回答**：

```text
根据现有政策证据，分三点说明：

1. 免费保修期限：晴栈 H26 蓝牙耳机自签收之日起保修 240 天；正常使用出现单侧无声，可申请免费维修（D_R04）。

2. 申请所需证明：申请时须提供订单凭证（D_R04）。

3. 泡水损坏是否免费：进水损坏不在免费保修范围内，因此泡水弄坏不能免费维修（D_R04）。

补充：上述为合成评测政策，不代表真实商家；实际以平台/商家最新规则为准。若需进一步核实，请补充订单号或转人工确认。
```

**Gold/历史条件（仅审核员可见）**：

```json
{
  "id": "D_Q02",
  "split": "independent_test",
  "kind": "rag",
  "query": "晴栈 H26 蓝牙耳机日常使用时一边听不到声音，售后能免费修多久？申请要拿什么证明，泡水弄坏也算吗？",
  "relevant_ids": [
    "D_R04"
  ],
  "atoms": [
    [
      "240天",
      "240 天"
    ],
    [
      "免费维修",
      "免费修理"
    ],
    [
      "单侧无声",
      "单边无声",
      "一边听不到",
      "一侧无声"
    ],
    [
      "订单凭证",
      "订单证明",
      "订单记录"
    ],
    [
      "进水"
    ],
    [
      "不在",
      "不包含",
      "不涵盖",
      "不适用",
      "不能",
      "不保修",
      "不属于"
    ]
  ],
  "forbidden": [
    "进水损坏可免费维修"
  ],
  "required_source_facts": [
    "自签收之日起保修240天",
    "正常使用出现单侧无声可免费维修",
    "须提供订单凭证",
    "进水损坏不在免费保修范围内"
  ]
}
```

**实际引用与工具**：

```json
{
  "citations": [
    {
      "document_id": "D_R04",
      "title": "虚构政策：晴栈耳机保修",
      "chunk_id": "D_R04",
      "section": null
    }
  ],
  "tools": []
}
```

**原始证据**：[查看完整请求/业务前后态](../p4_ablation_evaluation/runs/ubuntu_D_20261111_01/request_p4c_32157abfbfac4056a5a6e389b0b4097b.json)
 SHA256 `2ae364f4464d508566bad596d5753fbfc810fd084dc103db0a8e70a6b9c5dd69`

事实：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；完整性：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A

忠实度：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；业务终态：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A

整体：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；审核者：______ 时间：______ 说明：______

## E_SEM_12｜D_Q02｜HYBRID｜independent_test

**问题**：晴栈 H26 蓝牙耳机日常使用时一边听不到声音，售后能免费修多久？申请要拿什么证明，泡水弄坏也算吗？

**原始回答**：

```text
关于晴栈 H26 蓝牙耳机：

1. 免费保修期：自签收之日起 240 天内，正常使用出现单侧无声可免费维修（D_R04）。
2. 申请所需证明：须提供订单凭证（D_R04）。
3. 泡水损坏：进水损坏不在免费保修范围内，因此泡水弄坏不能免费维修（D_R04）。

补充：若考虑退货，自签收之日起 10 天内可申请无理由退货，但需耳机卫生封条未拆、包装及配件齐全；已拆卫生封条不适用无理由退货（D_R03）。

如需进一步核实，请提供订单号；若对进水损坏的判定有异议，可转人工评估。
```

**Gold/历史条件（仅审核员可见）**：

```json
{
  "id": "D_Q02",
  "split": "independent_test",
  "kind": "rag",
  "query": "晴栈 H26 蓝牙耳机日常使用时一边听不到声音，售后能免费修多久？申请要拿什么证明，泡水弄坏也算吗？",
  "relevant_ids": [
    "D_R04"
  ],
  "atoms": [
    [
      "240天",
      "240 天"
    ],
    [
      "免费维修",
      "免费修理"
    ],
    [
      "单侧无声",
      "单边无声",
      "一边听不到",
      "一侧无声"
    ],
    [
      "订单凭证",
      "订单证明",
      "订单记录"
    ],
    [
      "进水"
    ],
    [
      "不在",
      "不包含",
      "不涵盖",
      "不适用",
      "不能",
      "不保修",
      "不属于"
    ]
  ],
  "forbidden": [
    "进水损坏可免费维修"
  ],
  "required_source_facts": [
    "自签收之日起保修240天",
    "正常使用出现单侧无声可免费维修",
    "须提供订单凭证",
    "进水损坏不在免费保修范围内"
  ]
}
```

**实际引用与工具**：

```json
{
  "citations": [
    {
      "document_id": "D_R03",
      "title": "虚构政策：晴栈耳机退货",
      "chunk_id": "D_R03",
      "section": null
    },
    {
      "document_id": "D_R04",
      "title": "虚构政策：晴栈耳机保修",
      "chunk_id": "D_R04",
      "section": null
    }
  ],
  "tools": []
}
```

**原始证据**：[查看完整请求/业务前后态](../p4_ablation_evaluation/runs/ubuntu_D_20261111_01/request_p4c_c4d502c57aad49a2942d5a5c62a6d079.json)
 SHA256 `57e3d37eef0af84572a664147ac613061ca1220c927509abc187b36e11861513`

事实：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；完整性：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A

忠实度：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；业务终态：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A

整体：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；审核者：______ 时间：______ 说明：______

## E_SEM_13｜D_Q02｜DENSE｜independent_test

**问题**：晴栈 H26 蓝牙耳机日常使用时一边听不到声音，售后能免费修多久？申请要拿什么证明，泡水弄坏也算吗？

**原始回答**：

```text
关于晴栈 H26 蓝牙耳机：

1. 免费保修时长：自签收之日起保修240天；日常正常使用出现单侧无声，可申请免费维修（D_R04）。
2. 申请所需证明：须提供订单凭证（D_R04）。
3. 泡水损坏是否免费：进水损坏不在免费保修范围内，因此泡水弄坏不能免费维修（D_R04）。

补充：上述为合成评测政策，不代表真实商家；实际以平台/商家最新政策为准。若需进一步核实，请补充订单号或转人工确认。
```

**Gold/历史条件（仅审核员可见）**：

```json
{
  "id": "D_Q02",
  "split": "independent_test",
  "kind": "rag",
  "query": "晴栈 H26 蓝牙耳机日常使用时一边听不到声音，售后能免费修多久？申请要拿什么证明，泡水弄坏也算吗？",
  "relevant_ids": [
    "D_R04"
  ],
  "atoms": [
    [
      "240天",
      "240 天"
    ],
    [
      "免费维修",
      "免费修理"
    ],
    [
      "单侧无声",
      "单边无声",
      "一边听不到",
      "一侧无声"
    ],
    [
      "订单凭证",
      "订单证明",
      "订单记录"
    ],
    [
      "进水"
    ],
    [
      "不在",
      "不包含",
      "不涵盖",
      "不适用",
      "不能",
      "不保修",
      "不属于"
    ]
  ],
  "forbidden": [
    "进水损坏可免费维修"
  ],
  "required_source_facts": [
    "自签收之日起保修240天",
    "正常使用出现单侧无声可免费维修",
    "须提供订单凭证",
    "进水损坏不在免费保修范围内"
  ]
}
```

**实际引用与工具**：

```json
{
  "citations": [
    {
      "document_id": "D_R04",
      "title": "虚构政策：晴栈耳机保修",
      "chunk_id": "D_R04",
      "section": null
    }
  ],
  "tools": []
}
```

**原始证据**：[查看完整请求/业务前后态](../p4_ablation_evaluation/runs/ubuntu_D_20261111_01/request_p4c_5d367e2250d646de9ea68140d96812b5.json)
 SHA256 `c69bc60b1d65ca90548f283c988de2b64e87526b238dbc3d26d10bf2bd7089e1`

事实：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；完整性：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A

忠实度：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；业务终态：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A

整体：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；审核者：______ 时间：______ 说明：______

## E_SEM_14｜D_Q02｜BM25｜independent_test

**问题**：晴栈 H26 蓝牙耳机日常使用时一边听不到声音，售后能免费修多久？申请要拿什么证明，泡水弄坏也算吗？

**原始回答**：

```text
根据现有政策证据，分点说明如下：

1. 免费维修期限：晴栈 H26 蓝牙耳机自签收之日起保修 240 天（D_R04）。
2. 单侧无声是否免费修：正常使用出现单侧无声，可免费维修（D_R04）。
3. 申请所需证明：须提供订单凭证（D_R04）。
4. 泡水损坏：进水损坏不在免费保修范围内，因此泡水弄坏不能免费修（D_R04）。

补充：上述为评测用合成政策，不代表真实商家；如需实际办理，请补充订单号，或转人工核实。
```

**Gold/历史条件（仅审核员可见）**：

```json
{
  "id": "D_Q02",
  "split": "independent_test",
  "kind": "rag",
  "query": "晴栈 H26 蓝牙耳机日常使用时一边听不到声音，售后能免费修多久？申请要拿什么证明，泡水弄坏也算吗？",
  "relevant_ids": [
    "D_R04"
  ],
  "atoms": [
    [
      "240天",
      "240 天"
    ],
    [
      "免费维修",
      "免费修理"
    ],
    [
      "单侧无声",
      "单边无声",
      "一边听不到",
      "一侧无声"
    ],
    [
      "订单凭证",
      "订单证明",
      "订单记录"
    ],
    [
      "进水"
    ],
    [
      "不在",
      "不包含",
      "不涵盖",
      "不适用",
      "不能",
      "不保修",
      "不属于"
    ]
  ],
  "forbidden": [
    "进水损坏可免费维修"
  ],
  "required_source_facts": [
    "自签收之日起保修240天",
    "正常使用出现单侧无声可免费维修",
    "须提供订单凭证",
    "进水损坏不在免费保修范围内"
  ]
}
```

**实际引用与工具**：

```json
{
  "citations": [
    {
      "document_id": "D_R04",
      "title": "虚构政策：晴栈耳机保修",
      "chunk_id": "D_R04",
      "section": null
    }
  ],
  "tools": []
}
```

**原始证据**：[查看完整请求/业务前后态](../p4_ablation_evaluation/runs/ubuntu_D_20261111_01/request_p4c_37e330e8f7c545e7a71264d8aa202782.json)
 SHA256 `8a74b846a69ef29d047e5fa0399790d1f8c3deb183c9967dc544637e9ae78b7f`

事实：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；完整性：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A

忠实度：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；业务终态：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A

整体：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；审核者：______ 时间：______ 说明：______

## E_SEM_15｜proposal｜D0｜baseline

**问题**：请取消订单 ORD94071。

**原始回答**：

```text
确认后将取消订单 ORD94071。请核对订单号。
```

**Gold/历史条件（仅审核员可见）**：

```json
{
  "expected": "D0取消ORD94071需确认、单次写入/重放无新增；ORD94072否定不提案；未认证/跨用户拒绝",
  "original_record": "p4_ablation_evaluation/runs/ubuntu_D_20261111_01/request_p4c_77e8d8b0c5b24ce4bfe8ee6a1672f3be.json"
}
```

**实际引用与工具**：

```json
{
  "citations": [],
  "tools": []
}
```

**原始证据**：[查看完整请求/业务前后态](../p4_ablation_evaluation/runs/ubuntu_D_20261111_01/request_p4c_77e8d8b0c5b24ce4bfe8ee6a1672f3be.json)
 SHA256 `9e84cb8cfb926861af2d988b26948509801d68f363a23046f93c845ad9d2ecd6`

事实：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；完整性：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A

忠实度：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；业务终态：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A

整体：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；审核者：______ 时间：______ 说明：______

## E_SEM_16｜cross_user_confirmation｜D0｜baseline

**问题**：确认取消

**原始回答**：

```text
（无回答；请查看原始HTTP拒绝状态）
```

**Gold/历史条件（仅审核员可见）**：

```json
{
  "expected": "D0取消ORD94071需确认、单次写入/重放无新增；ORD94072否定不提案；未认证/跨用户拒绝",
  "original_record": "p4_ablation_evaluation/runs/ubuntu_D_20261111_01/request_p4c_519ebea4538342c7b3c7cd0a3d9d7455.json"
}
```

**实际引用与工具**：

```json
{
  "citations": [],
  "tools": []
}
```

**原始证据**：[查看完整请求/业务前后态](../p4_ablation_evaluation/runs/ubuntu_D_20261111_01/request_p4c_519ebea4538342c7b3c7cd0a3d9d7455.json)
 SHA256 `beb7ada10314325f042f665f7b5e39e292c07619975f250784fd69cb0638beda`

事实：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；完整性：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A

忠实度：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；业务终态：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A

整体：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；审核者：______ 时间：______ 说明：______

## E_SEM_17｜missing_credentials｜D0｜baseline

**问题**：取消订单 ORD94072

**原始回答**：

```text
（无回答；请查看原始HTTP拒绝状态）
```

**Gold/历史条件（仅审核员可见）**：

```json
{
  "expected": "D0取消ORD94071需确认、单次写入/重放无新增；ORD94072否定不提案；未认证/跨用户拒绝",
  "original_record": "p4_ablation_evaluation/runs/ubuntu_D_20261111_01/request_p4c_7d41a82159684afb96c20aa7307ee79d.json"
}
```

**实际引用与工具**：

```json
{
  "citations": [],
  "tools": []
}
```

**原始证据**：[查看完整请求/业务前后态](../p4_ablation_evaluation/runs/ubuntu_D_20261111_01/request_p4c_7d41a82159684afb96c20aa7307ee79d.json)
 SHA256 `70655bbfd808c0f4906e5bbdff617397f882284267a12255ca997b019ac6a4f2`

事实：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；完整性：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A

忠实度：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；业务终态：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A

整体：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；审核者：______ 时间：______ 说明：______

## E_SEM_18｜confirm｜D0｜baseline

**问题**：确认取消

**原始回答**：

```text
已为您发起取消订单 ORD94071 的确认，系统返回状态为 cancelled。请注意：该结果来自工具返回，属于取消操作的确认结果；如后续涉及退款金额或到账时效，当前没有可引用的证据，建议您补充订单号或转人工核实。
```

**Gold/历史条件（仅审核员可见）**：

```json
{
  "expected": "D0取消ORD94071需确认、单次写入/重放无新增；ORD94072否定不提案；未认证/跨用户拒绝",
  "original_record": "p4_ablation_evaluation/runs/ubuntu_D_20261111_01/request_p4c_6c10d63e6551435d98b72f9cd69d7a97.json"
}
```

**实际引用与工具**：

```json
{
  "citations": [],
  "tools": [
    {
      "name": "cancel_order",
      "arguments": {
        "order_id": "ORD94071"
      },
      "success": true,
      "status": "executed",
      "failure_kind": null,
      "output": {
        "order_id": "ORD94071",
        "status": "cancelled"
      }
    }
  ]
}
```

**原始证据**：[查看完整请求/业务前后态](../p4_ablation_evaluation/runs/ubuntu_D_20261111_01/request_p4c_6c10d63e6551435d98b72f9cd69d7a97.json)
 SHA256 `817d75d7762e0dc87b9f49e455d662ddb10b3cde95989d177d42365729829502`

事实：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；完整性：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A

忠实度：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；业务终态：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A

整体：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；审核者：______ 时间：______ 说明：______

## E_SEM_19｜idempotent_replay｜D0｜baseline

**问题**：确认取消

**原始回答**：

```text
已收到您的取消请求。系统已对订单 ORD94071 发起取消操作，工具返回状态为 cancelled。请注意：取消属于不可逆操作，以上为系统执行结果回执，建议您稍后在订单详情页再次核对最终状态；如状态未更新，请提供订单号转人工核实。
```

**Gold/历史条件（仅审核员可见）**：

```json
{
  "expected": "D0取消ORD94071需确认、单次写入/重放无新增；ORD94072否定不提案；未认证/跨用户拒绝",
  "original_record": "p4_ablation_evaluation/runs/ubuntu_D_20261111_01/request_p4c_b3b86d91c2d849f5a98244687491cce1.json"
}
```

**实际引用与工具**：

```json
{
  "citations": [],
  "tools": [
    {
      "name": "cancel_order",
      "arguments": {
        "order_id": "ORD94071"
      },
      "success": true,
      "status": "replayed",
      "failure_kind": null,
      "output": {
        "order_id": "ORD94071",
        "status": "cancelled"
      }
    }
  ]
}
```

**原始证据**：[查看完整请求/业务前后态](../p4_ablation_evaluation/runs/ubuntu_D_20261111_01/request_p4c_b3b86d91c2d849f5a98244687491cce1.json)
 SHA256 `37eeee3ce289df0136f06150907b23ff9e7d436c75126c2aa4de58b3aac82e09`

事实：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；完整性：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A

忠实度：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；业务终态：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A

整体：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；审核者：______ 时间：______ 说明：______

## E_SEM_20｜negative_request｜D0｜baseline

**问题**：不要取消订单 ORD94072，只查询订单状态。

**原始回答**：

```text
已按您的要求不取消订单，仅查询订单 ORD94072 的状态。实时查询结果：订单状态为 paid（已支付）；下单时间为 2026-11-11T05:34:34.052132Z；订单金额为 31940 分（即 319.40 元）；商品明细为空；paid_at、shipped_at、delivered_at 均为空，暂无运单号，收货城市为空。因此，目前只能确认订单已支付，无法确认是否已发货、物流进度或预计送达时间。若需进一步核实发货或物流情况，请提供更多订单信息或转人工客服查询。
```

**Gold/历史条件（仅审核员可见）**：

```json
{
  "expected": "D0取消ORD94071需确认、单次写入/重放无新增；ORD94072否定不提案；未认证/跨用户拒绝",
  "original_record": "p4_ablation_evaluation/runs/ubuntu_D_20261111_01/request_p4c_cf6bf0bfaeff493f8cc7fa51e3a23481.json"
}
```

**实际引用与工具**：

```json
{
  "citations": [],
  "tools": [
    {
      "name": "get_order",
      "arguments": {
        "order_id": "ORD94072"
      },
      "success": true,
      "status": "executed",
      "failure_kind": null,
      "output": {
        "order_id": "ORD94072",
        "user_id": "u_demo",
        "status": "paid",
        "items": [],
        "total_cents": 31940,
        "created_at": "2026-11-11T05:34:34.052132Z",
        "paid_at": null,
        "shipped_at": null,
        "delivered_at": null,
        "tracking_no": null,
        "receiver_city": null
      }
    }
  ]
}
```

**原始证据**：[查看完整请求/业务前后态](../p4_ablation_evaluation/runs/ubuntu_D_20261111_01/request_p4c_cf6bf0bfaeff493f8cc7fa51e3a23481.json)
 SHA256 `b9af7fbf22340796012c34f25214e4e0c04e3eb410479975f53f3184af3c45d6`

事实：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；完整性：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A

忠实度：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；业务终态：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A

整体：[ ] PASS [ ] FAIL [ ] UNCERTAIN [ ] N/A；审核者：______ 时间：______ 说明：______
