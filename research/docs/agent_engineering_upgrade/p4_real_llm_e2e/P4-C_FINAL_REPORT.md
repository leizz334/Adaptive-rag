# P4-C 真实 DeepSeek E2E 最终报告

**质量结论：PARTIAL。** 真实模型开发集与冻结独立集均已执行；确认了两处应用缺陷并完成最小离线修复。冻结自动业务检查是机械代理，不能当作完整语义正确性认证。工程验证/交付状态见文末。

## 基线、模型与环境

- 基线 `84f5b8bf9dc20de988f9ee8d1d3795856839c84a`；分支 `codex/p4-real-llm-e2e`；复用 Ubuntu 当前目录与 Python3.12.9 `.venv`，无新 Worktree/Initializer。
- 使用原 Compose 定义，新建唯一所属项目 `p4b_20261111_p4c_01`；实际 PostgreSQL/Redis/Qdrant，独立新库与 collection，真实 Uvicorn/TCP HTTPX，生产 required-auth verifier、M2、Graph/工具。全部为合成数据。
- 实际 Provider 为 `DeepSeekProvider` 加计量 transport，非 Mock；响应模型均为 `deepseek-flash`。免费 `/models` 查询200，仅列出 flash/v4-pro；原配置 deepseek-chat 不在列表。本阶段显式选 flash，不改用户 .env。官方文档版本 DeepSeek-V4.1-Flash-1017；响应没有不可变版本号，因此服务器具体权重修订 **NOT_ASSESSED**。
- Thinking disabled，temperature0，API max_tokens每次<=1024，Provider attempts1、transport retries0、并发1。实际 public SSE 路由通过非流式上游生成后发送验证后的 SSE，未评测 DeepSeek 原生流式接口。
- 实际 Qdrant + Redis；embedding为确定性 hash、reranker为 lexical，沿用P4-B明确的测试选择，不能称真实BGE/交叉编码器评测。外部 tracing 与 Experience Active关闭。

模型和最高价格来源：[官方价格](https://api-docs.deepseek.com/quick_start/pricing/)、[模型退役说明](https://api-docs.deepseek.com/news/news260424/)、[Thinking开关](https://api-docs.deepseek.com/guides/thinking_mode/)。按已验证峰值缓存未命中输入$0.30/百万、输出$1.20/百万Token计上界，不假定缓存折扣或低峰折扣。

## 冻结、开发集与独立集

`datasets.json` 为新合成任务/Gold：开发2项、独立6项，实体和提示不同；在预实验前冻结。Gold和评分器为AI编写，未获得人类标注或独立人类语义校准。独立集不是隐藏于开发者的第三方盲测。旧Gold、历史付费实验与原始结果均未改动/重跑。

C0 `23b7e31` 冻结 `freeze.json`；开发CD02暴露缺陷后，在C1 `b3c3c69` 冻结 `freeze_v2.json`再运行独立集，Gold/scorer不变。原先10次开发请求未逐行存source fingerprint，源归属由历史Git提交+原freeze证明；26次独立请求逐行绑定v2。CT06失败后的planner修复未付费重测，最终源码与v2差异使旧付费准入自动拒绝；原freeze及成绩保留。修复后的源码哈希见 `evidence/final_source.json`。

| 分组 | 任务数 | 自动业务代理达成 | 工具目标达成 | 预期业务状态达成 | 所需声明出现 | 协议有效 |
|---|---:|---:|---:|---:|---:|---:|
| 开发预实验 | 2 | 1/2 | 2/2 | 2/2 | 3/4 | 2/2 |
| 独立测试 | 6 | 5/6 | 5/6 | 5/6 | 8/8 | 6/6 |

自动代理开发50.0%，独立83.3%；**完整语义任务成功率、完整回答事实正确性、忠实度和人类质量评价均NOT_ASSESSED**。声明出现不保证无否定、无额外错误；引用存在不证明引用支持。工具指标在无必需工具的任务上是真空满足；独立有工具要求的任务为3/4达成。CT04检索通过retriever执行，工具调用0不是未检索。CT05在进入模型前本地澄清，模型请求0，不能算DeepSeek模型成功样本。全部8次业务HTTP请求的未确认业务写入为0；CT06的预期取消未发生，所以业务目标失败，不是安全违规。

| ID | 协议 | 模型请求 | Token | 工具调用 | 自动代理 |
|---|---|---:|---:|---|---|
| CD01 | json | 5 | 3823 | get_order:1 | PASS(代理) |
| CD02 | sse | 5 | 3919 | get_order:1, track_shipment:1 | FAIL |
| CT01 | json | 5 | 3884 | get_order:1 | PASS(代理) |
| CT02 | json | 5 | 3957 | get_order:1, track_shipment:1 | PASS(代理) |
| CT03 | sse | 5 | 3027 | check_inventory:1 | PASS(代理) |
| CT04 | json | 6 | 2157 | 无 | PASS(代理) |
| CT05 | sse | 0 | 0 | 无 | PASS(代理) |
| CT06 | json | 5 | 3626 | get_order:1 | FAIL |

完整答案、请求前后SQL状态、执行工具/参数/输出与trace在 `runs/ubuntu_C_20261111_01/task_*.json`、`request_*.json`、`worker_*/events.jsonl`；上游公开completion/finish_reason/usage在 `requests.json`。不导出请求Authorization、API Key、私有DSN或reasoning_content。

## 分项度量和费用

- 新增真实 completion HTTP **36/80**；输入**22,112**、输出**2,281**，计量合计 **24,393/80,000 Token**；0未知usage、0重试、0不确定请求。免费models/健康查询不计completion。
- 峰值缓存未命中费用上界：`22112×0.30/1e6 + 2281×1.20/1e6 = $0.0093708`，低于$1。实际账单/缓存命中折扣/峰谷最终扣费 **NOT_ASSESSED**，未伪造invoice成本。
- 模型请求平均 **1.549s**，最近秩P95 **3.136s**，n=36。
- 开发任务平均 **8.187s**、P95 **9.308s**，n=2；独立平均 **6.832s**、P95 **9.994s**，n=6。小样本P95即样本最大值，不是生产SLA。启动/索引冷启动未混入任务延迟；真实BGE冷启动NOT_ASSESSED。
- 所需事实/完整性仅有冻结机械覆盖代理：开发3/4声明出现，独立8/8声明出现；整体回答语义额外断言未逐条人类认证。生产同模型Judge的SUPPORTED不能作为独立忠实度真值。

预算write-ahead预留在dispatch前执行；文件fsync+rename+父目录fsync，OS独占锁跨请求，UTF8全请求字节+1024 framing预留输入，max_tokens预留输出。任何未知usage、超时、非200、截断、模型不匹配或源哈希漂移均停止后续付费。STARTED/consumed任务不自动重放。回归期间清空测试进程key并禁止外部付费连接，账本与C2提交字节一致，未产生额外模型请求。

## 失败分类与最小修复

1. **CD02应用降级遗漏**：工具得到SYNCD0222、模型也正确输出，但goal检查触发安全降级后只渲染金额/无物流轨迹，丢失单号。补充allowlist renderer，只有成功、未截断且合法字符的tracking_no可显示；负例/injection/truncation保护仍在。`c1_tracking_RED.xml`→`c1_tracking_GREEN.xml`，开发原失败保留，没有付费复跑。独立CT02在v2上通过自动检查。
2. **CT06模型计划遗漏+应用缺失提案**：模型只规划get_order，回答请求用户确认却pending_action为空；订单保持paid，没有确认/取消/重复提交。planner最小修复：单一明确订单、明确取消、匹配既有取消skill时，从已验证skill补充cancel_order**提案**；现有确认/Owner/Session门槛不变，否定和条件性请求不补。`c2_cancel_verified_RED.xml`→`c2_cancel_GREEN.xml`。最终修复只离线验证，真实模型取消执行和重复提交 **NOT_ASSESSED**，独立成绩继续记FAIL。
3. **准备/度量缺陷**：首次pytest相对import收集错误修正；评分实体参数缺失的反例RED→GREEN；独立审查指出父目录fsync和词句存在性误称正确性，均付费前修复。最终审查无critical/important。
4. **回归基础设施**：首轮全量843PASS/4QdrantsetupERROR/1历史SKIP；回归脚本未清除继承socks代理。仅清理测试子进程代理后用全新run ID再次全量验证；保留首轮XML，不修改production vector也不重跑付费任务。

## 未解决/不可验证

- 完整回答语义、外部人类校准、不可变服务端权重版本、实际invoice和引用支持度NOT_ASSESSED。
- CT06修复后的真实模型确认、取消及幂等重放未验证；该已消费测试不被重新称作未见数据。
- 同一源版本下开发与独立直接因果比较不成立：独立在修复v2上运行，最终planner修复又在独立之后。
- 原10条pilot ledger无逐条sourcefingerprint，由冻结Git证据追溯；不改写旧计量行。
- reviewer minor保留：补充取消提案可能在6个已净化步骤后形成第7步；未确认写入仍被executor门槛阻止、工具调用上限保持，未扩大本阶段修复范围。
- Redis故障fail-open、Qdrant租户向量隔离、SQLite分布式exactly-once等P4-B限制未被本阶段重新认证。

## 工程回归、资源与交付

现有全量pytest最终结果在 `evidence/c3_full_VERIFIED.xml`，静态检查在 `evidence/c3_checks.json`。Ruff与339文件format通过、Mypy150源文件通过、pip check通过。原始214离线回归保持80/80、13/16、30/30、33/33、23/24、22/30、long1/1，零历史严格PASS→FAIL；该回归为scripted，不是重复已完成付费实验。

仅本阶段新命名测试资源与原B回归专用测试资源用于验证；无prune/down-v/卷删除。报告/状态/交付记录使用本阶段路径；历史Gold/实验/报告字节保留。最终所属服务停止、卷和私有清单保留，用户原MySQL不动。分阶段commit、正常push和精确ls-remote结果在progress.txt/evidence交付记录。最终语义质量PARTIAL，不能宣称真实模型端到端全部任务PASS。

**STOP after P4-C; Experience Active off; no P4-D/E.**

### 最终验证实测结果

最终全量pytest：**847PASS、0FAIL/ERROR、1历史SKIP，88.15秒**。原始XML首轮错误与最终成功均保留。静态Ruff/format339/Mypy150/pip均通过。工程验证完成；模型质量保持PARTIAL，交付等待正常push/远程HEAD核验。

### 正常交付已核验

阶段检查点 `2ab952b1c692ab7ad928f0da8688f7b54e63a5bd` 已正常Push至 `codex/p4-real-llm-e2e`，`git ls-remote` 与本地精确一致。C0—C3工程任务均完成，质量结论保持PARTIAL。所属6个服务停止、卷保留，API子进程exit0，原MySQL继续运行。交付元数据见 `evidence/delivery.json`；本段元数据提交随后正常Push并再次核验最终HEAD，最终答复记录该哈希。无force-push，无额外模型调用，无P4-D/E。
