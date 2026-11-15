# 真实 DeepSeek Agent 业务验收报告

日期：2026-11-15。延续同一工作树、分支和原账本。新增授权：20 次模型 HTTP（含重试）、费用上限 $0.05、不设累计 Token 上限。

**四项真实业务通过；HITL 未运行，原因是 20 次请求已用满。服务端付费开关和本轮账本授权均已关闭。没有扩大额度、重置账本或以 Mock 代替真实验收。**

## 真实结果

| 场景 | 结果 | 模型 HTTP | 输入 / 输出 Token | 场景耗时 | 按 usage 估算费用上界 |
|---|---|---:|---:|---:|---:|
| ORD95101 / Tool Calling | PASS | 5 | 3574 / 336 | 6.184 秒，含 Chromium | $0.0014754 |
| 同会话 Memory / SSE | PASS | 5 | 3631 / 364 | 5.422 秒 | $0.0015261 |
| 私有政策 RAG / 引用 | PASS | 6 | 2398 / 483 | 7.685 秒 | $0.0012990 |
| 不存在订单 / 防幻觉 | PASS | 4 | 2801 / 204 | 3.903 秒 | $0.0010851 |
| HITL / 确认 / 状态变更 / 幂等 | **NOT_RUN / BUDGET_BLOCKED** | 0 | 0 / 0 | 未发送 | $0 |

20 次模型响应均成功，20 个 LLM span 均有可信 usage；场景耗时合计 23.194 秒，逐次模型延迟见 Trace。节点、工具参数、结果与回答保存在 `evidence/B3-*-response.json`；汇总见 [最终证据](evidence/B4-final-summary.json)。

真实 Chromium 从 8000 选择 DeepSeek、跳转 8001，空凭证框要求重新认证，发送订单查询并显示真实回答。`get_order(order_id=ORD95101)` 与 PostgreSQL 一致：已支付、6800 分（68 元）。同一真实会话继续追问商品，Memory 关联回 ORD95101，`get_order_items` 返回实际商品；HTTP/SSE、历史保存及另一 Owner 的访问拒绝通过。

RAG 新增隔离合成政策 `business-policy-26c42758cef4`，A 用户可检索、B 用户不可见。真实回答区分“定制商品不适用七天无理由”和“质量问题仍可申请售后”，说明照片/订单凭证及人工审核，明确政策为合成验收数据。引用 ID 与授权知识库实际 chunk 完全对应，Trace 的文档、标记和摘录也相符。

RAG 原验收脚本直接比较 Trace chunk ID 时失败，因为通用脱敏显示为 `[REDACTED]`。原失败保留，改用授权知识库 ID 与实际引用交叉核验另存 [RAG 复核](evidence/B3-rag-business-review.json)；**不改后台脱敏、历史 Gold，不付费重跑**。

不存在订单经实际工具返回失败，回答明确无法查到，没有编造状态或金额。HITL 在发送模型请求前被次数门禁拒绝，合成订单 `ORD202611159746571421` 保持 `paid`，没有执行取消。原有 Mock/单元回归不替代本轮真实 HITL 验收。

## 同账本追加授权

旧账本仅剩 1014 Token，小于最小预留，且上限绑定原指纹。现增加最小持久授权与请求映射，仍使用原 `adaptive-rag-real-agent-dev_real_budget` 内的同一 `budget.sqlite3`：

- 原指纹、历史请求、预留和结算不改写。原 6 次 / 10000 Token / $0.05 配置保留，仅用于原指纹与价格兼容校验。
- 本轮 ID：`business-20261115-20usd005`；新请求受 **20 次 / $0.05 / max_tokens=NULL** 控制，不受旧累计 Token 上限阻断。模型与既有单请求上下文限制保留。
- 可信管理员显式追加，启动只选择授权，不自动创建。完全相同的重复授权幂等；冲突/重叠授权拒绝；关闭有追加见证，不能重新打开补满额度。
- 每次 HTTP 前以 SQLite `BEGIN IMMEDIATE` 原子预留完整请求和最大输出的最坏费用。可信 usage 可减少费用占用，**请求次数不返还**。异常、中断及未知消费保守处理，pending/uncertain 阻止后续消费。
- 未选择、未知或关闭的授权不能回退旧额度；重启、并发、重复授权、崩溃、篡改及关闭边界均有回归。

已核对 [DeepSeek 官方价格](https://api-docs.deepseek.com/quick_start/pricing/)，使用 `deepseek-flash` 保守高峰上界：输入未命中缓存 $0.30 / 百万 Token、输出 $1.20 / 百万 Token。官方 HTTPS 端点、实际 DeepSeekProvider，未使用额外计费网络搜索，原 Key 未修改。

## 调用和账本结算

| 指标 | 本轮新增 | 含原历史合计 |
|---|---:|---:|
| 请求 | **20 / 20** | 23 |
| Trace 输入 / 输出 | 12404 / 1387 | 不重算旧历史 |
| Trace 实际 Token | **13791** | 不补填旧历史 |
| 按 usage 的费用估算上界 | **$0.0053856** | 非供应商扣款账单 |
| 账本有效费用占用 | **$0.0125115 / $0.05** | $0.0162981 |
| 账本有效 Token 占用 | 31844，无累计限制 | 40830 |
| 累计原始预留 Token / USD | 80809 / $0.0316623 | 89795 / $0.0354489 |
| 完成 / 已结算 / pending / uncertain | 20 / 15 / 0 / 0 | 23 / 15 / 0 / 0 |

首次订单业务成功，但五条请求没有按 usage 结算，保留预留 $0.0086013。随即关费排查，未重跑订单。

本地 RED 复现压缩响应缺陷：观察层读取原始压缩字节，Provider 则经 HTTPX 解压后成功解析。已改为双方读取同一份解压内容，避免重复解压；解码、取消、提前关闭等仍保守处理。新增 gzip/deflate JSON/SSE 和关闭边界测试通过；修复后 15 次真实调用全部结算。

首次五条的原始编码头未留存，不能证明每条均由压缩导致。**五条仍按原预留占用，未返额或补结算；原失败断言保留，真实业务事实另行复核。** 因此账本占用高于 Trace 用量估算，二者均低于 $0.05。原三条历史的 8986 Token / $0.0037866 保留。[订单复核](evidence/B3-order-business-review.json)、[修复证据](evidence/compression-tests.json)。

## 回归和保护

- 最终后端 **947 项 pytest 通过**，无失败/跳过；一条既有 LangChain 弃用提示。
- 前端 **54 项单元测试、类型检查通过**。真实 Chromium 验证模式切换、重新认证和订单回答；关费后再次验证两端登录和明确提示，无模型发送。
- Ruff、Mypy（152 个应用文件）通过。独立审查无剩余 Critical/Important；审查本身未执行测试或付费请求。
- 8000 容器 ID、镜像、启动时间、卷及全部数据库表指纹与本次开始相同；未更新、停止或 Seed 正式环境。
- 两份 `.env`、Key、Stash、6239 个受保护历史文件不变；全部 **22 个卷**保留。仅新增合成政策、订单和测试会话，不改历史实验。
- Experience Active=OFF；后台经验模块、前端应用源码未改，没有恢复 Shadow。

## 最终状态与使用

8000 Offline 正常。8001 保留最新真实服务，Bearer 登录和查看历史正常；**REAL_AGENT_PAID_AUTHORIZED=false，授权 closed=true**。实际聊天探测返回 503，账本未增加；前端明确提示未授权付费，不静默降级。

共 **8 个健康容器**，两套各 4 个；真实环境额外占用 4 个容器。全部付费测试活动已停止，没有持续付费入口。Real API 镜像为 `sha256:3bcaeb16e0d2ce1960f89006e8b1d415d0bcef045dea12500bcab21fd9e82f88`。

私有运行配置在 `/home/panda/.adaptive-rag-business-20261114/business.compose.env`，镜像 overlay 为同目录 `business-image.json`，均不含 Key 明文。Key 仍由原 0600 文件读取；重启不会自动追加授权或开费。

无需真实环境时，在固定工作树 WSL 终端停止服务，保留数据：

```bash
sudo docker compose \
  --env-file /home/panda/.adaptive-rag-business-20261114/business.compose.env \
  -p adaptive-rag-real-agent-dev \
  -f compose.showcase.yml -f compose.agent-dev.yml \
  -f /home/panda/.adaptive-rag-business-20261114/business-image.json \
  stop api postgres redis qdrant
```

将末行改为 `start postgres redis qdrant api` 可恢复现有容器，付费仍关闭。不要删除或用备份替换当前账本。后续真实 HITL 需要新的明确请求数/费用授权和新的审计 ID；本轮不自动追加或开启新阶段。

提交、普通 Push 和远端 HEAD 核验记在 `progress.txt`。私有凭证、原始错误日志、账本备份不提交；首次失败、复核及 Trace 均保留，未将未运行场景标为 PASS。
