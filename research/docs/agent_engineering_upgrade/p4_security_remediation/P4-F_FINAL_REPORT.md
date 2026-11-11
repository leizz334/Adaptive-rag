# P4-F 安全修复与验证最终报告

**PHASE_STATUS = PASS（本阶段明确边界内的安全修复）。** P4-E发现的应用层私有KB隔离与Redis敏感请求fail-open问题已修复并经真实依赖验证。不是整个项目生产认证，也不升级历史真实模型/语义结论。新增付费LLM请求0；Experience Active=NO；P5_STARTED=NO。

## 版本、环境与实现

基于 `a081291f9665f39fccb590600d51918773869906` 创建 `codex/p4-security-remediation`，复用当前Ubuntu固定目录/.venv/现有Compose，未创建Worktree或重复Initializer。仅新owned项目 `p4b_20261111_p4f_01` 和合成业务/文档/认证subject；没有生产服务连接。

F1检查点 `288b2d9c32f04a53e8aab3dd40869f85302eb403`；F2 `d6090214a9daa6ff2cef6454442dfdc8ea802a1e`；F3及交付HEAD由Git/delivery.json与最终答复给出。完整决策、故障策略和接入方式见 [SECURITY_DESIGN.md](SECURITY_DESIGN.md)，恢复见 [RECOVERY.md](RECOVERY.md)。

## F1：完整链路私有隔离

| 路径 | 修复 | 验证 |
|---|---|---|
| 认证/入库 | subject来自服务端Bearer验证；不接受body user_id/tenant_id，schema extra禁止；public禁用私有API | 无认证401、伪造scope422、聊天user_id伪造403、外部header不授权 |
| 文档/Chunk | SQL复合subject+document主键、不可变revision、chunk ID含subject/doc/revision；有界内容/数量 | 两租户同doc ID独立，跨主体更新/删除与不存在同404 |
| BM25 | 每请求只从当前subject SQL文档构建 | 双worker/两租户/同查询，无外租户片段 |
| Qdrant | 独立private collection；subject与当前有效chunk IDs双过滤，结果正文自SQL重建 | 真实Qdrant Dense/Hybrid路径，旧revision清理不删除新revision |
| Hybrid/Reranker/引用 | RRF与原reranker仅接收授权chunk；Graph最终引用ID必须来自本次chunk集 | HTTP/SSE答案与引用、两租户并发查询、12个并发读 |
| Redis缓存 | key含subject hash/generation/query/mode/top_k，值仅chunk IDs；命中后校验SQL重建 | 两worker重复命中、跨租户负例、外国/无效chunk缓存污染不返回 |
| 更新/删除/重索引 | generation写锁与查询SHARE锁；更新、删除、reindex使旧缓存代际不可达；物理清理限subject/doc/旧revision | 旧内容不再检索，跨worker更新删除与reindex、并发更新、fresh进程重载 |
| 故障/禁用 | private缺身份/配置拒绝；实际依赖失败不调用共享公共KB | public模式私有API403；私有Redis故障503，无共享降级 |

私有模式显式 `KNOWLEDGE_MODE=private`，默认public仍只放公共非敏感语料。private不导入共享knowledge目录，不混用公共BM25、collection或cache。命名空间等于服务端认证subject；**不支持组织成员共享、跨subject委托或管理员读取所有私有文档**。这是明确授权模型，不把客户端自报tenant ID当身份。

SQL为权限/版本权威，向量和缓存不是授权源；孤儿向量或陈旧cache不能扩展返回范围。查询/生成在SQL事务快照授权，写操作等待同subject读锁；**不承诺删除可以撤回已保存历史、已发送或在途SSE内容**。

### 失败证据和最小修复

- P4-E原应用私有租户失败JSON保留原路径与hash，见 `f1_baseline_and_validation.json`；旧报告未改判。新增设置/验证契约最初2FAIL保存 `f1_contract_RED.xml`。
- 初始真实HTTP7PASS，扩展12PASS；审查发现空白文档和tokenless BM25可导致主体搜索500，另有文档级后台清理可能误删新revision。`f1_review_RED.xml` 保存4FAIL。修复strip+长度约束、tokenless空结果、revision级清理后 `f1_FINAL_GREEN.xml` 为16PASS；后续新增fresh进程重载，最终全量涵盖全部11项私有HTTP测试。
- 一次孤立单元运行暴露既有包初始化循环依赖，harness显式先加载app.main；失败XML仍保留，未为此重构无关应用。初次Mypy私有/公共局部变量类型混淆已通过变量命名修正，最终152源文件检查通过。
- 独立F1审查确认重要问题修复；残余取消清理与“同revision重索引”交错可能短暂影响Dense可用性，但SQL仍阻止跨主体/未知revision披露。该可用性边界保留，不升级为无故障索引承诺。

## F2：Redis故障策略与全局配额

| API/操作 | 策略 |
|---|---|
| chat、SSE、HITL确认、private KB CRUD/search/reindex | Redis原子准入；不可用/超时/未知结果503 RATE_LIMIT_UNAVAILABLE；配额耗尽429 |
| 远程Embedding启动入库 | Provider初始化/入库前先获得Redis bootstrap准入；无准入不发远程请求 |
| health/ready/capabilities/metrics | 只读诊断保持可访问；ready仍报告逐依赖实际状态，不能仅用HTTP200断言全健康 |
| 只读admin工具catalog | 保持Bearer/admin权限验证，不触发付费/业务写入 |
| 无API凭据、public、无Redis、显式testing的离线profile | 可用进程内测试限流；不是全局限流，不能用于生产 |
| 显式ordinary-read Redis utility | 保留可选fail-open供普通只读/旧兼容测试；敏感运行时没有此调用路径 |

Lua使用Redis服务端TIME、滑动窗口和UUID成员，在一次原子调用内清理、计数、判定及记录；只计获准请求。API deadline为250ms，不确定返回拒绝，不自动重试；配置Redis但启动ping失败时保留客户端，恢复后重连，不能回退本地。准入后Redis中途失败不承诺撤销此前已准入操作；这也不是Token/美元预算系统。

真实验证包含：停止Redis、CLIENT PAUSE超时、恢复、两个生产配置ASGI进程竞争同subject配额，以及Redis已故障时启动后恢复。12个竞争请求、配额4，**4次200、8次429**；故障期间chat/私有写入拒绝、SSE只有error/done无answer，SQL前后状态相同，恢复后新操作通过。没有把本地多进程配额称为全局。

新增unit RED3、真实HTTP RED1（旧fail-open实际返回200并写入合成文档）与SQL前后态均保留。初始真实6GREEN、组合18GREEN。审查发现远程Embedding凭据可绕过“离线测试本地限流”例外及启动入库门禁，保存 `f2_review_RED.xml` 2FAIL，修复后针对性10GREEN。最终 `f2_FINAL_GREEN.xml` 为9PASS；最终全量再次覆盖这些代码。测试中的远程Provider工厂被禁止初始化，没有外部计费调用。

旧B3 API Redis故障测试从200降级强化为503/noTools/noWrites；ordinary-read utility mock改为实际Lua eval故障。**未修改历史Gold或raw结果，未放宽安全检查**。

## F3：最终回归与独立审查

- 全量 `pytest tests research/docs/agent_engineering_upgrade`：**893PASS、0FAIL/ERROR、1历史SKIP，140.52s**。证据 `evidence/f3_full_FIRST.xml`。既有LangGraph pending-deprecation warning1保留。
- Ruff check及format **364文件PASS**；Mypy **152源文件PASS**；pip check PASS，命令/输出在 `f3_checks_FIRST.json`。
- 真实依赖13、认证HTTP20、真实依赖API/恢复20，以及11私有HTTP测试和4 Redis真实故障/多进程测试均包含于最终全量，不累加重复执行当独立质量样本。
- 冻结历史214案例保持80/80、13/16、30/30、33/33、23/24、22/30、long1/1；原12项非PASS保留，**新增严格PASS→FAIL=0**。新输出 `../p4_dependency_integration/runs/ubuntu_F3_legacy_20261111/`，旧结果不覆盖。
- F1/F2独立focused审查及fresh whole-branch最终审查均为只读；重要发现经RED→GREEN修复并复核，最终无新critical/important。审查者未运行测试/服务/网络或付费请求；最终执行与交付由本次执行者核验。

全部真实依赖测试使用合成数据、实际ASGI生产认证/配置与OfflineLLM；受控hash向量/lexical reranker验证ACL数据流，**不冒充真实神经检索质量或真实DeepSeek收益评测**。既有真实模型质量和完整语义结论保持原样。测试wrapper和ASGI子进程均清空计费Key并拒绝外部socket。

## 保留审计、清理与交付

`f3_preservation.json`核对基线Git blobs：仅授权源码、测试、README/部署指引和状态文件改变；历史Gold、报告、原始JSON和C/D账本原字节保留。4份旧CSV仅工作区CRLF/Git LF归一化相等，未重写或stage历史CSV。旧实验freeze在当前安全源码有预期漂移，历史源码仍在其Git提交；禁止改旧freeze或重跑付费实验。

`f3_secret_scan.json`检查当前实际Key、所有私有manifest凭据与demo token，未输出凭据值；.env/.private/日志/数据库/模型权重不提交。公开fixture token只用于合成测试，不可生产使用。所属3依赖服务停止并保留卷，精确API子进程清理记录保留；原MySQL运行，无prune/down-v或删除用户资源。

交付分支 `codex/p4-security-remediation` 正常Push、git ls-remote精确核验；实际交付记录见delivery.json/最终Git记录。最后metadata提交自身hash以Git/最终答复为准，避免递归。

## 未解决边界

1. subject隔离不是组织共享/委托授权系统；不支持的跨主体文档操作拒绝。
2. 事务快照授权不能撤回旧历史、客户端已有内容或在途SSE；该限制不是跨租户授权漏洞。
3. 取消的物理清理可能影响同revision重索引可用性；等待在途工作结束后显式重索引。孤儿向量GC、WAL/备份擦除未验收。
4. Redis超时可能占用quota而不执行业务，保守拒绝；Redis持久化丢失/跨机灾难恢复不在本次承诺内。
5. TLS、外部渗透、生产密钥运维、宿主机/DB管理员威胁、完整回答语义及真实模型总体收益继续NOT_ASSESSED/NOT_ESTABLISHED，不因F通过而升级。

**本阶段安全修复验收通过（上述边界内）；完成后STOP，无新增研究阶段，Experience Active=NO，P5_STARTED=NO。**
