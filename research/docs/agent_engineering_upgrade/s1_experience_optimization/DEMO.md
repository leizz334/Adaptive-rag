# 可复现的零付费演示

从本分支新克隆、按 Ubuntu 部署说明建立 `.venv` 后，在仓库根目录运行：

```bash
.venv/bin/python -m research.docs.agent_engineering_upgrade.p4_final_acceptance.offline research.docs.agent_engineering_upgrade.s1_experience_optimization.demo
```

无需 API Key 或 Docker 启动，不发模型请求、不写业务数据库。使用公共已保存原始 Planner 响应，通过实际 Planner 解析/安全校验重放；不会把脚本预设结果冒充新模型推理。执行会在新 UUID 的忽略目录 `.private/demos/` 建立演示 SQLite，不覆盖原始证据。

可依次展示：历史 PSV22-R0 可验证遗漏 → 固定工具覆盖原则 → 原有提案/审核/验证状态机 → 精确许可和兼容/安全过滤 → E0 与 E2 的 Planner 消息及实际记录计划。E0 已选择两个正确工具，E2 仍是同样计划，不能展示为失败被新经验治愈。新当前失败提案仍 NEEDS_REVIEW；没有审批也不进入 E2。

演示使用明确的历史时钟 `2026-11-12T00:00:00Z` 复现当时资格，不是重新激活到期生产经验。新 SQLite 从公开资格记录重建，不能声称与原始冻结 SQLite 字节相同。原始实验所有文件/依赖/私有数据库校验的 `verify_freeze` 和完整 analyze 需要原实验主机的忽略私有 SQLite；新克隆可执行本公开离线重放和检查公开捕获。

预期输出：OFFLINE_RECORDED_RESPONSE_REPLAY_NOT_NEW_INFERENCE；E0 hints=0、E2 hints=2；两者工具为 get_order(ORD73101)、get_refund_status(ORD73102)；12 个公开分数重放匹配；new_model_requests=0；human_approvals=0；real_benefit=NOT_ESTABLISHED。实际输出见 [ex3_demo.json](evidence/ex3_demo.json)。

不得运行 `run.py development/independent` 重放已经完成的付费实验；消费标记是不可自动重试的恢复门禁。未使用预算不代表自动授权新实验。
