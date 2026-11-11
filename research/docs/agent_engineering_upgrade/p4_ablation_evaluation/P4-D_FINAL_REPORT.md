# P4-D 消融与真实收益验证最终报告

**PHASE_STATUS = PARTIAL_PASS。** D0—D3实验/资格任务完成，工程回归通过；收益结论限于冻结的微型配对探针。Memory在受限历史目标上出现正向转变；真实Dense/Reranker改善检索排序，但当前两道RAG业务题没有下游成功率增益。Experience因当前版本资格不足未做E0/E2。完整开放回答语义仍NOT_ASSESSED，不用同模型Judge替代人工。

## 基线与设计

- 从已验证 `75689d2276c19c51354a0d27966597a23c9063d4` 创建 `codex/p4-ablation-evaluation`；复用当前Ubuntu目录、Python3.12 `.venv`、现有Compose；没有新Worktree/Initializer，没有修改.env、历史Gold或应用/eval源码。
- 新所属项目 `p4b_20261111_p4d_01`，新私有凭据、回环端口、PostgreSQL/Redis/Qdrant；真实FastAPI/Uvicorn、required-auth、DeepSeekProvider。仅合成业务数据，无生产业务服务。
- 请求模型配置统一 `deepseek-flash`、thinking disabled、temperature0、Provider attempts1、transport retries0、并发1、output<=1024。响应别名一致；服务器不可变权重修订未暴露，NOT_ASSESSED。
- 阶段全局D-only账本，不继承或重放C/P2/P3计费。先write-ahead文件+目录fsync，再dispatch。上限180请求/160000计量Token/US$1，未知usage/不确定请求/错误/源漂移停止。整组配对开跑前保守准入，逐臂上限12请求/20000Token；不完整或存在不可判定臂的整组不进入效果分母。
- 实际有效规模：Memory 1开发+1独立任务、每题3臂；RAG 1开发+1独立任务、每题4臂，共4组完整配对/14臂。规模预先固定，预算仍有余额；没有把小样本解释为预算不足，也没有根据结果追增样本挑好成绩。
- 两段历史由SQL预置，所有臂相同，包含过时助手金额；M0无上下文，M1最近4条，M2最近4条+现有owner-bound增量**抽取式**摘要。不是LLM生成摘要或Experience学习。检验当前工具事实优先于旧金额。实际自然对话历史生成质量未被本实验覆盖。
- Memory固定BM25、identity rerank；RAG固定M2，比较BM25、Dense、Hybrid/RRF、Hybrid+真实CrossEncoder。前三臂不做额外rerank，没有用Lexical冒充真实模型。Redis连接真实，用于原限流；为防跨臂污染，检索缓存禁用。
- 同题查询、消息顺序、初始业务表内容按hash逐臂核验相同；会话ID独立，模型参数/Gold/scorer/源码/模型文件/依赖版本固定，独立题反向臂序。原始UUID/实体/答案/业务状态保留，不规范化掉结果差异。

## D0：新真实基线与CT06修复

新订单ORD94071主流程验证1/1：提案后0写入；跨用户确认400、缺失认证401均无工具/模型执行；合法确认只产生1取消+1审计+1幂等记录；重放返回replayed且无额外写入；ORD94072否定请求经SSE只读、不创建提案。主流程3步加3个反例，共6次业务HTTP；14次真实模型请求、9050Token。旧CT06未重跑，旧失败成绩不改。

该结果证明当前受限HITL/Owner/幂等业务能力可用，不代表所有自然语言取消均可靠。完整回答事实/完整性/忠实度在 `evidence/d0_semantic_review.json` 和空白 `d0_human_review_template.csv` 等待实际人工标签。没有必要的额外人工批准门禁；目标是保留未知，不是伪造PASS。

## D1：真实RAG模型与独立相关性标签

按原配置安装CPU torch2.6.0+cpu、项目rerank extras，使用原架构BGEsmall与bge-reranker-base，不换模型架构。下载官方固定revision文件，记录SHA256；每次真实模型worker加载前再校验文件hash。实际实例为SentenceTransformer与CrossEncoder，512维/CPU/2线程；强制启用模型并断言available，拒绝Hash/Lexical降级。
- `BAAI/bge-small-zh-v1.5` revision `7999e1d3359715c523056ef9478215996d62a620`，文件哈希见 `evidence/model_download.json`。
- `BAAI/bge-reranker-base` revision `2cfc18c9415c912f9d8155881c133215df768a70`，文件哈希见 `evidence/model_download.json`。

权重来源：[BGE small官方卡片](https://huggingface.co/BAAI/bge-small-zh-v1.5)、[BGE reranker官方卡片](https://huggingface.co/BAAI/bge-reranker-base)。另一个作者在查看任何检索输出前编写8篇合成语料与6条相关性标签（2开发/4独立）；这是独立AI作者标签，不是人类标注或第三方盲测，未根据运行结果调标签。

| 组合 | n查询 | Recall@1 | Recall@3 | MRR@8 | 平均检索ms | CPU user s/查询 |
|---|---:|---:|---:|---:|---:|---:|
| BM25 | 6 | 0.500 | 1.000 | 0.750 | 1.05 | 0.0019 |
| DENSE | 6 | 1.000 | 1.000 | 1.000 | 30.03 | 0.0458 |
| HYBRID | 6 | 0.500 | 1.000 | 0.750 | 24.39 | 0.0430 |
| RERANK | 6 | 1.000 | 1.000 | 1.000 | 982.48 | 1.9114 |

真实模型文件共 **1.231GB**；共享加载栈峰值RSS约 **1350.2MiB**。进程内Embedding加载 **2.861s**、Reranker加载 **1.021s**，不是清空系统页缓存后的冷机测试。RSS是共载栈高水位，不能当作每臂独立内存消融；独立臂RAM增量NOT_ASSESSED。IR对整个8篇语料排序，RAG业务默认每检索query取3、最终取3，检索重写/grade仍走原Graph并记录费用。

Dense/Reranker的排序指标优于本微型语料上的BM25，Reranker CPU检索开销显著增加。各臂Recall@3都为1，因此当前业务题均可看到相关文档；这与后续成功率饱和一致，但不能证明总体因果机制或模型在其他语料无收益。

## D2：开发与独立配对结果

`freeze_d2_v2.json` 对实际65次配对模型调用保持完全相同；先完成开发2组/7臂，核对工具/答案/历史/业务hash并记录开发审核，才允许独立2组/7臂。开发审核不是人类语义批准。没有中途改Gold/scorer或调参，所有4组完整且受限指标均可判定。

| 场景 | 分组 | M0 | M1 | M2 |
|---|---|---|---|---|
| 短历史，旧金额111.00，实时237.80 | 开发 | FAIL：缺订单号 | PASS | PASS |
| 长历史，旧金额222.00，实时586.20 | 独立 | FAIL：缺订单号 | FAIL：近期窗口丢实体 | PASS：摘要恢复实体并查实时数据 |

独立M1由应用直接澄清，0次模型请求；该FAIL是受控任务未完成，不是安全失效。M0/M1/M2变化包含确定性实体解析与摘要机制，不能全部归因于DeepSeek推理增强。

| RAG业务题 | 分组 | BM25 | Dense | Hybrid | Hybrid+真实Reranker |
|---|---|---|---|---|---|
| 电水壶14天及退货条件/排除项 | 开发 | PASS | PASS | PASS | PASS |
| 耳机240天保修/凭证/进水排除 | 独立 | PASS | PASS | PASS | PASS |

| 比较 | 开发正/负 | 独立正/负 | 合并描述性正/负（n=2） |
|---|---|---|---|
| M0→M1 | 1/0 | 0/0 | 1/0 |
| M0→M2 | 1/0 | 1/0 | 2/0 |
| M1→M2 | 0/0 | 1/0 | 1/0 |
| BM25→DENSE | 0/0 | 0/0 | 0/0 |
| BM25→HYBRID | 0/0 | 0/0 | 0/0 |
| BM25→RERANK | 0/0 | 0/0 | 0/0 |

**Memory：观察到受限任务收益；总体/生产收益NOT_ESTABLISHED。** 两题中M0=0/2、M1=1/2、M2=2/2，但只有1题独立。**RAG：下游任务收益NOT_ESTABLISHED**，四臂均2/2，不能以IR提升替代业务提升。独立比较未观察到负向转变；极小样本不能证明无负迁移。完整开放语义不在这些PASS内。

### Token、端到端延迟与资源开销

| 臂 | n（含1开发1独立） | 平均计量Token/任务 | 平均任务s | 总模型请求 |
|---|---:|---:|---:|---:|
| M0 | 2 | 2570.5 | 4.688 | 6 |
| M1 | 2 | 1820.5 | 3.735 | 5 |
| M2 | 2 | 3706.5 | 6.617 | 10 |
| BM25 | 2 | 2481.5 | 7.182 | 11 |
| DENSE | 2 | 2463.0 | 7.282 | 11 |
| HYBRID | 2 | 2492.0 | 7.728 | 11 |
| RERANK | 2 | 2466.0 | 8.417 | 11 |

工具名称/参数/成功、目标业务表终态、引用命中、逐臂Token/上界成本/延迟/检索节点时间均在 `evidence/d2_results.json`、`ablation_table.csv` 和原始pair/request文件。所有消融题均只读，无新业务写入。M2增量摘要为现有抽取式机制，摘要生成模型请求0；M1的0调用澄清导致平均Token不随Memory模式单调增加。检索节点时间含query rewrite/grading网络，并非纯Dense延迟；纯IR时间见D1。模型加载在任务计时之外，共载模型RSS不能用于每臂RAM归因。

## D3：Experience资格与收益

独立审核确认三条原经验仍NEEDS_REVIEW/UNREVIEWED，绑定旧源码 `70d65e36687ae31133b08aec065f0a3ca4a6b848`。7个来源artifact哈希匹配，来源完整性PASS；但当前源码资格、当前特征与preflight permit缺失。旧MODEL_REVIEWED/VERIFIED_OFFLINE副本仅验证旧版本结构适用性，不能重新贴标签当当前资格。七条P3用户答案判断也不是经验批准。

**EXPERIENCE_ABLATION=NOT_RUN；EXPERIENCE_BENEFIT=NOT_ESTABLISHED。** 未做真实E0/E2、未产生额外请求、未开Active。没有伪造人类经验批准门禁：隔离selector允许有真实独立验证的MODEL_REVIEWED记录，但本次没有符合当前版本的记录。完整理由和来源哈希在 `evidence/d3_qualification.json`。

## 语义质量与审核包

评分器只对受限目标断言：正确实体的实时工具证据、非否定金额、政策数字与条件/排除项关系、Gold文档引用、业务状态、协议。无法可靠解析同义回答返回None/NOT_ASSESSED；只要整组任意臂不可判定或不完整，就不进入效果分母。当前14臂均可判定，不存在用不对等臂凑结果。

**完整事实正确性、完整性、忠实度与整体人类语义成功率仍NOT_ASSESSED**；不能将受限字段检查或同模型Judge的SUPPORTED升级为完整语义PASS。`semantic_human_review_packet.json` 包含14个逐臂答案、题目、来源、工具和证据SHA；CSV人审字段全部空白。基线6个HTTP答复另有D0审核包。没有任何AI标签伪称人类标签；本阶段报告这些未知不需要额外人为编造的批准。

## 预算、模型与恢复

- 真实模型HTTP **79/180**；输入**40,265**、输出**4,785**，合计 **45,050/160,000 Token**。14基线+65配对，0未知usage、0不确定请求重试；D1/D3新增付费0。
- 峰值缓存未命中成本上界 `40265×0.30/1e6 + 4785×1.20/1e6 = US$0.0178215`，低于US$1。按[官方当前价格](https://api-docs.deepseek.com/quick_start/pricing/)验准，不假定缓存或低峰折扣。实际invoice/扣费NOT_ASSESSED；本地电耗和带宽价格未计价，CPU/RSS/磁盘另行记录。
- 模型调用平均 **1.400s**，最近秩P95 **2.056s**，n79；小样本与别名服务非确定性限制仍在。
- D0 freeze保留；D2首个freeze启动失败后在任何配对请求前保留旧版、新建v2；v2对全部14臂未改变。原始C36请求账本字节保留，未重跑历史付费或消费过的任务。恢复见 `RECOVERY.md`、feature-list/progress/Git与79行全局ledger。

## 失败归因、修复与独立审查

1. D1首次IR在真实权重成功加载后因继承socks代理导致Qdrant ping失败；仅清理子进程代理后成功，未伪称Hash结果。原始失败日志私有保留，公开摘要有hash。
2. 配对付费前审查发现政策关键词否定仍可假PASS、开发与独立之间缺审核点；反例RED3→GREEN，改为关系约束/不确定弃权和完整分母排除，并拆分运行+源码hash审核门禁。没有基于真实配对答案调Gold/scorer。
3. 首开发worker在任何配对请求前退出3：隔离环境把模型enabled设false，force不足以启用；显式开启真实模型开关，RED→GREEN。旧worker/日志/旧freeze保留，新实例后成功，账本仍仅14基线请求。不是付费请求自动重试。
4. 一次人工编排审核导出有语法错误、另一次把canonical JSON顺序误当消息时间顺序；修正为SQL message.id还原历史。缺失审核时独立准入已拒绝，0额外付费，无配对数据被改写。
5. 最终fresh-context只读审查无critical/important；minor保留：直接在runner外对协议无效且RAG不可判定回答调用score时可返回None而非False，授权runner在评分前拒绝无效协议，因此当前结果不受影响。源码不为该minor再扩修。

## 工程验证与交付

- 全量 `pytest tests research/docs/agent_engineering_upgrade`：**858PASS、0FAIL/ERROR、1历史SKIP，100.18s**。有一个既有LangGraph pending-deprecation warning；不是未执行的真实模型实验被计PASS。
- Ruff check、348文件format--check、Mypy150源文件、pip check全部PASS。回归进程清空计费Key、移除代理并拒绝非loopback网络，未增加D账本；B实时依赖与受控API回归使用新D4run IDs。
- 冻结历史214脚本案例保持80/80、13/16、30/30、33/33、23/24、22/30、long1/1；原有12个非PASS仍保留，严格PASS→FAIL **0**，未宣称214全过。
- 整个阶段未改应用/eval源码、历史Gold、C/P3报告或用户文件。独立freeze/namespace/source/pairedstate审计与secret扫描保存；私有模型/manifest/.env/log不提交。
- D与原B回归所属6个服务最终停止、卷与新模型权重保留。成功baseline/development/independent worker exit0；首个失败启动exit3单独保留。原有MySQL持续运行；无prune/down-v或删除用户资源。

最终交付状态与远程HEAD由 `evidence/delivery.json`/Git/final response核验；完整开放语义、生产总体收益、Experience收益均不能强行PASS。**P4-D结束；Experience Active=NO；P4-E_STARTED=NO。**
