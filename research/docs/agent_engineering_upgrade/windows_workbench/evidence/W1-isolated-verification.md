# W1 隔离业务验证

2026-11-13，在已有 worktree 内执行：

```powershell
wsl -d Ubuntu-24.04 -u root -- python3 /mnt/d/Code/Adaptive-rag/.worktrees/p3-experience-validation/research/docs/agent_engineering_upgrade/windows_workbench/w1_verify.py --project adaptive-rag-w1-20261113 --port 18083 --create
```

进程退出码 0，输出 `W1 PASS; sanitized evidence saved; isolated stack remains running`。
运行使用已有三个应用镜像，`docker compose up -d --no-build --pull never`，没有修改产品代码。
新项目创建前检查了同名容器、卷、网络和端口冲突；之后验证 Compose 项目、来源、标签、卷名前缀和 loopback 端口。
原有 `adaptive-rag-showcase` 六个容器的 ID、镜像、状态、启动时间、端口和卷挂载在前后快照中一致。

| 验证 | 实际结果 | 证据 |
| --- | --- | --- |
| 原问题：定制商品过了七天，但有质量问题还能退吗？ | 私有知识为空时 return_exchange / single_hop / single，检索 0、引用 0、token 0，正常无证据兜底 | `adaptive-rag-w1-20261113/question_before_seed.json` 与对应 trace |
| HTTP + SSE 多轮订单 | ORD95101 已支付，6800 分；第二轮沿用会话并查询商品，2 件演示帆布包、非定制；M2 有历史消息；Owner B 历史读取 404 | `adaptive-rag-w1-20261113/multi_turn.json` 与对应 traces |
| 私有知识上传、搜索、引用 | 仅新项目内上传明确标注为合成的演示政策；原问题获得带引用的资料节选，仍明确提示未配置生成模型；Owner B 搜索 0、列表不可见、删除及 trace 404 | `adaptive-rag-w1-20261113/private_knowledge.json` 与对应 trace |
| Planner / HITL / 幂等 | ORD95103 提案后仍 paid；确认后 cancelled；同一 Action 重放前后 SQL 快照完全相同；cancel_order 审计恰好 1 条，幂等记录 1 条；Owner B 取消 404，完成后取消 409 | `adaptive-rag-w1-20261113/hitl.json` |

这些结果证明原现象来自缺少私有政策证据及 Offline 的有限能力，没有发现需修补的模型逻辑缺陷。公共 `knowledge/` 不会自动进入用户私有知识。合成政策仅用于测试隔离环境，不代表真实商家规则。所有业务验证均为 Offline，付费调用 0。

新项目保持运行，保留所有卷，供 W4 使用：

- 项目 `adaptive-rag-w1-20261113`，API `http://127.0.0.1:18083`。
- 私有 Compose override：`windows_workbench/.private/adaptive-rag-w1-20261113/compose.override.json`。
- 私有浏览器配置：`windows_workbench/.private/adaptive-rag-w1-20261113/browser-config.json`；凭证仅在同一忽略目录，报告不包含令牌。
- `ORD95102` 和 `ORD95104` 仍为 paid，留给 W4 浏览器场景；`ORD95103` 已验证取消。
- 当前 API 镜像内的前端是原有构建。验证 W2 新界面时可用独立 Vite 服务，设置 `VITE_API_BASE=http://127.0.0.1:18083`，并给 Playwright 配置该 Vite 端口。若更新容器，只能对这个新项目执行经过身份检查的操作。
- 完整可复用 Compose 参数在 `adaptive-rag-w1-20261113/reuse.json`。不要对既有用户项目执行重启、重建、停止或数据变更。

`--create` 要求全新项目名和未使用端口；完成后的业务数据非幂等初始化，不能把本次已完成项目当作空白项目重新执行整套验证。
