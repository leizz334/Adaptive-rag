# Ubuntu 可复现浏览器演示

只用隔离合成数据。默认 OfflineLLMProvider（受控规则/安全fallback），不是实际DeepSeek推理或真实质量评测。生产 Experience Active关闭。Node满足frontend/package.json，Python复用本仓库`.venv`。

## 1. 新环境准备

在仓库根目录选择**未使用**项目名。不要复制包含密码的manifest到公开位置，不要修改`.env`。已存在的项目只可核对后start，不能重复up创建或重跑迁移回环。

```bash
export P4B_RUN_LIVE=1
export WEB_DEMO_PROJECT=p4b_s1web_your_unique_id
.venv/bin/python -m research.docs.agent_engineering_upgrade.p4_dependency_integration.sandbox prepare --project "$WEB_DEMO_PROJECT"
export P4B_MANIFEST="$PWD/research/docs/agent_engineering_upgrade/p4_dependency_integration/.private/$WEB_DEMO_PROJECT/manifest.json"
.venv/bin/python -m research.docs.agent_engineering_upgrade.p4_dependency_integration.sandbox up
.venv/bin/python -m research.docs.agent_engineering_upgrade.p4_dependency_integration.migrate --roundtrip
npm ci --prefix frontend
npm run build --prefix frontend
.venv/bin/python -m research.docs.agent_engineering_upgrade.p4_final_acceptance.offline research.docs.agent_engineering_upgrade.s1_web_upgrade.demo prepare
.venv/bin/python -m research.docs.agent_engineering_upgrade.p4_final_acceptance.offline research.docs.agent_engineering_upgrade.s1_web_upgrade.demo serve
```

`demo prepare/info` 只输出URL和忽略的0600凭据文件路径，不打印Token。首次在工作台的“本地开发凭证”输入该文件tokens.a（可信主体web_demo_a）；tokens.b是第二合成主体。请在本机私下读取文件，不粘贴凭证到聊天、命令行参数、日志或提交。若更换Docker项目，应先归档当前新demo私有配置到独立私有目录，再为新目标生成新配置；不要覆盖已完成演示数据库。

## 2. 三个演示

1. **订单与Memory**：发送“请查询 ORD95101 的订单状态和金额”，展开Agent Execution查看get_order及状态/金额摘要。追问“这单的商品明细和是否定制也帮我核实”，应看到合成帆布包及非定制，session不变、历史计数增加、get_order_items真实执行。新建/切换会话；响应模式可选HTTP/SSE。
2. **私有知识库**：上传唯一标题/ID的.txt或.md合成政策，创建后检索；对话提问相同唯一政策，查看citation和执行面板原文片段。编辑需填写完整新正文；更新后检索应命中新版本；确认删除后列表/检索不可再命中。切换tokens.b时不应看到A的文档/会话；越权delete返回404，伪造user_id返回403，既有外人session请求返回400的opaque session-not-found，Trace返回404。
3. **取消与HITL**：请求“请取消订单 ORD95102”，查看Planner和待确认Action，确认后真实订单取消；点击“幂等重放（同一 Action）”，只有一次业务写入。用ORD95104演示“取消操作”撤销待确认提案，再确认会被拒绝。已完成/过期提案无法撤销，不能回滚已提交订单。

订单95102/95103/95105/95106/95107可供不同新演示，一经取消不得重置来伪装首次执行。再次运行E2E用`S1WEB_CANCEL_ORDER=ORD95106`等尚未取消订单。所有初始数据均为合成，seed遇到Owner/金额冲突拒绝而不覆盖。

## 3. 真实浏览器自动验证

在另一个终端保留相同仓库、Node PATH及demo已运行：

```bash
cd frontend
npx playwright install chromium --only-shell
S1WEB_CANCEL_ORDER=ORD95102 npm run test:e2e
```

Playwright真实Chromium单worker、重试0，连接实际FastAPI/PG/Redis/Qdrant，无route mock。包含上述3场景、跨用户拒绝、凭证刷新清理、Experience诚实标注、390px布局、浏览器实际断网及传输取消。原始测试报告在忽略私有目录，公开审计汇总在evidence，避免凭证进入浏览器trace/HAR（这些采集关闭）。运行前复制/保存已有报告，新实验使用新文件名，不覆盖历史结果。截图只做视觉辅助，不代替浏览器验收。

结束先对本次API进程Ctrl+C，再用同一manifest执行`...sandbox stop`，保留数据卷。不使用down -v、prune或停止其他容器。已完成本阶段的自动实验不自动重复；未配置付费模型，也不要为演示启用付费模型。
