# P0-D — Agent Tracing / Observability Audit

只核对源码、安装元数据和官方资料；未接入服务、设API密钥、启动Collector、上传业务数据或运行Tracing实验。SOURCE_VERIFIED 为源码/元数据事实；TEST_VERIFIED 仅实际隔离测试，本任务无SDK运行测试；平台文档为DOCUMENTED_ONLY；接入建议/性能判断为HYPOTHESIS；连接和兼容性运行验证为BLOCKED。

## 1. 当前调用级可见性

<!-- acceptance: P0-D.1 -->

| 层 | 当前能力与实际源码 | Span缺口 |
|---|---|---|
| HTTP | [request_context:72](../../../../app/main.py#L72) 接收或生成trace/request ID，写request.state与响应头；[new_trace_id:11](../../../../app/core/ids.py#L11) 为tr_前缀UUID hex | 关联ID不是span_id或parent关系；请求头值没长度/格式验证，不是可信身份 |
| Context / JSON日志 | [bind_request_context:8](../../../../app/observability/context.py#L8)、[ContextFilter:20](../../../../app/observability/logging.py#L20) | 注入trace_id/request_id字段，无每次调用开始/结束、父子span、逻辑/网络尝试ID；Filter会用ContextVar覆盖extra的ID |
| ChatService | [chat:70](../../../../app/services/chat_service.py#L70)、[_observe:271](../../../../app/services/chat_service.py#L271) 完成日志、总延迟、成功/拒答计数 | 异常路径常不走_observe；status=ok可能只代表返回非拒答，不代表工具/任务成功；计时在限流后开始 |
| Metrics | [metrics.py:5](../../../../app/observability/metrics.py#L5) 请求/路由/工具/Token/延迟/幻觉聚合 | 无请求级因果关系；_observe只发布intent/retrieval/llm阶段，未统一覆盖routing/tool/check/summary；失败和检查器异常口径需分离 |
| LangGraph | [build_graph:45](../../../../app/agents/graph.py#L45)、[SSE astream:97](../../../../app/services/chat_service.py#L97) 有节点定义、updates进度 | 仓库未显式传Tracing callback/run配置；LangChain框架可潜在产生Run，但外部环境是否启用未检查；不能宣称已有完整持久Trace或绝对无Trace |
| DeepSeek | [generate:48](../../../../app/providers/deepseek.py#L48) 原生httpx、usage、有限重试；[retry:32](../../../../app/core/retry.py#L32) 失败日志 | 普通Python方法不自动成为LLM语义Span；阶段、每次尝试、成功/失败usage没有完整归集；HTTP span也不等于LLM语义span |
| Retriever | [Hybrid.retrieve:37](../../../../app/retrieval/hybrid.py#L37) 数量/总耗时日志，单路失败日志；缓存命中提前return | 无BM25/Dense/RRF/CE/改写/每跳Grade的因果树；缓存命中缺同等完成日志 |
| 本地线程 | [VectorRetriever.search:161](../../../../app/retrieval/vector.py#L161)、[CrossEncoder.rerank:107](../../../../app/providers/reranker.py#L107) 使用to_thread | 需要确认框架callback和所选SDK上下文都跨线程，不只业务ContextVar |
| Tool Executor | [executor_node:95](../../../../app/agents/nodes/executor.py#L95) 工具状态Metrics、fallback元信息、ToolContext.trace_id | 无逐step/参数校验/审批/执行/结果/commit Span；fallback成功还计原工具ok，聚合语义不足以重建轨迹 |
| SQL业务审计 | [write_audit:139](../../../../app/repositories/order_repository.py#L139) trace_id+动作+订单标识 | 只覆盖部分写操作，不是全工具或读调用Span；依赖事务提交 |
| Memory | [memory_node:11](../../../../app/agents/nodes/memory.py#L11) 状态变换与可选模型摘要 | 没有压缩前后预算、丢弃范围、摘要版本和独立耗时/失败追踪 |
| SSE | [stream:84](../../../../app/services/chat_service.py#L84) Queue+create_task节点进度，结束后48字符分段 | 没有生命周期Span；不能用token事件当Provider首Token；取消/流中异常和已提交状态未精确区分 |

现有计数适合容量/趋势监控，trace_id适合关联日志；缺的是调用级时间、父子关系和业务结果。Prometheus继续保留，不把trace_id/user_id/session_id放进高基数label；可用日志/Trace关联或受控exemplar，不能用每请求label代替Span。

## 2. 版本与平台比较

<!-- acceptance: P0-D.2 -->

只读 `importlib.metadata` 核实：当前Conda环境langgraph **0.2.76**、langchain-core **0.3.86**、langsmith **0.14.12**、httpx **0.28.1**；Langfuse/OpenInference/OTel API/SDK未安装。[uv.lock](../../../../uv.lock) 中langsmith为 **0.14.7**，存在环境与锁差异。[pyproject.toml](../../../../pyproject.toml) 没直接声明langsmith，它作为传递依赖存在。以上不是SDK接口/连通性验证，原始元数据快照由本任务validation保存；没有导入SDK或读取.env。

| 方案 | 框架与自定义链 | Async/SSE与关联 | 部署/运维和最小侵入判断 |
|---|---|---|---|
| LangSmith | LangChain/LangGraph集成；自定义Provider/检索/工具需手动语义埋点 | 支持traceable、上下文/Run、元数据与生成器；仍需验证当前旧图版本的父子关系和关闭语义 | 本仓库已传递安装SDK，接入层最短是推断而非实测；云导出需批准，私有化资格/运维另核对 |
| Langfuse | LangChain CallbackHandler与手动observations | 能关联框架与自定义观察；要显式管理会话/评测ID、父上下文、取消和flush | 有云和自托管；需新增并锁定依赖，自托管带存储/队列/备份运维，不能认为免费无成本 |
| Arize Phoenix | OpenInference框架埋点+OTel/OTLP，普通httpx语义需手工补足 | 统一Span语义并发送本地/远程后端；需要独立SDK/Exporter和上下文验证 | 自托管本地审计优先可考察；比现有SDK方案多集成层，但利于保留数据控制 |
| OpenTelemetry | 中立追踪标准，可覆盖ASGI/HTTP/SQL及自定义节点；自身不是Agent评测平台 | Context传播、父子Span/links、Exporter/Collector；LLM语义和评分展示需另外约定 | 后端可替换，自主管理成本较高；平台无关不代表零改造或自动识别Provider用途 |

平台能力依据：LangSmith [手动埋点](https://docs.langchain.com/langsmith/annotate-code)、[框架Tracing](https://docs.langchain.com/langsmith/trace-with-langchain)；Langfuse [SDK埋点](https://langfuse.com/docs/observability/sdk/instrumentation)、[LangGraph集成](https://langfuse.com/integrations/frameworks/langchain)、[自托管](https://langfuse.com/self-hosting)；Phoenix [官方仓库](https://github.com/Arize-ai/phoenix)、[OpenInference说明](https://arize-ai.github.io/openinference/python/instrumentation/openinference-instrumentation-langchain/)；[OTel Python传播](https://opentelemetry.io/docs/languages/python/propagation/)。资料描述是DOCUMENTED_ONLY。候选最新文档不保证兼容本项目0.2图栈，不能为匹配文档而在P0升级依赖。

建议：先定义中立的事件/ID和脱敏契约。若允许批准后的云导出，LangSmith是当前最短接入路径的候选；若数据必须留本地，比较Phoenix与Langfuse自托管的隔离PoC，再选择。LangSmith也有[自托管说明](https://docs.langchain.com/langsmith/self-hosted)，部署资格/许可和账户区域必须另行核实，不能将开源SDK等同可免费私有化整个平台。无需本次引入四套SDK或双写所有Trace。

## 3. LangSmith最小改造边界（建议，不是实施步骤）

<!-- acceptance: P0-D.3 -->

保留FastAPI、Graph、Provider协议和业务SQL。变更候选集中在可观测性适配器、ChatService请求边界、Graph配置、Provider/检索/Tool调用边界；不需要把DeepSeek重写为其他供应商的SDK。SDK直接使用未来应成为显式锁定依赖，但本次不修改pyproject/lock。

### ID、树结构与语义

- 每轮生成**服务端唯一root run UUID**；原 `tr_...` 保留为经过校验/脱敏的 `app_trace_id` 元数据，不强行当LangSmith run UUID。客户端提供的任意x-trace-id不能指定已有Run、伪造owner或改变租户；必要时只保留请求关联的HMAC值。
- 元数据区分 app_trace_id、request_id、root_run_id、task_run_id、turn_index、伪名化session/user/tenant、版本快照、数据集case/group。新HTTP请求含确认操作时是新root，通过经脱敏的action reference和task_run_id关联，不把跨请求动作强塞成仍在运行的父Span。
- 父子树建议：`chat.turn → session_load / confirmation_resolve → graph → node → llm.logical_call / retrieval / tool.step → attempt`，图结束后仍有 `persist/commit`；SSE另记录delivery阶段。框架自动节点Span与手动叶Span只各保留一层，不给每节点重复包多套根。
- 每个LLM调用有purpose：intent/route/rewrite/plan/generate/grade/judge/self_correct/summary；逻辑调用下记录每个网络attempt、等待、状态与可获取usage。失败无usage标unknown，不能假装0；汇总区分逻辑调用、尝试次数和实际计费Token，按调用ID去重。
- Retriever记录查询ID/长度、缓存命中、真实backend、候选ID/排名/score、每跳缺失方面与停止原因；默认不记录全文。Tool区分proposed/validated/approved/executed/result/committed，记录schema版本、规范化参数的安全摘要、原始/fallback名称、业务成功与技术异常。等待确认是pending，不是失败或完成。

### 异步、SSE与生命周期

根上下文必须在async generator开始迭代到关闭的范围内有效，不能在`call_next`返回Response对象时就结束。向ainvoke/astream传播所选callback与metadata；在create_task前建立上下文，验证线程to_thread中的父关系。ContextVar通常可随Python task/thread辅助函数传播，但当前SDK、框架回调、ASGI任务边界仍须测，不能假定每层自动挂对。

事件队列只携带必要、安全的事件；明确 await/close/cancel 的Span终态，等待被取消子任务清理。分别记录执行完成、事务提交、正文首段、流结束/取消；客户端断开后若订单已commit，业务效果是已提交、delivery可取消，不允许为了“补Trace”重试业务写入。不能把最终正文的48字符分段发送记作LLM真实stream token延迟。官方[生成器Tracing](https://docs.langchain.com/langsmith/trace-generator-functions)支持异步生成器/聚合，仍需有界聚合与提前关闭测试，不能收集无限输出或在异常路径遗留pending Run。

Tracing采用有界后台导出、超时/丢弃计数、关闭时有界flush；导出器失败不改变订单和聊天结果。业务失败与遥测失败分开。不能为保证追踪上传而延长数据库事务，也不能因导出失败再执行工具。

### 脱敏与导出

先默认关闭外发；经批准后只导出白名单元数据，隐藏原始输入/输出，待验证脱敏覆盖后才允许合成样本正文。LangSmith官方[隐私处理](https://docs.langchain.com/langsmith/mask-inputs-outputs)提供隐藏/处理输入输出及元数据的方案，选用项必须核对当前锁定SDK是否支持。

[现有mask_pii:42](../../../../app/core/security.py#L42)不是全链路脱敏；[ContextFilter:22](../../../../app/observability/logging.py#L22)只处理msg，不处理args/extra/异常stack或所有嵌套字段。Graph自动追踪可能捕获完整State，节点/Provider手动装饰器也可能捕获kwargs中的消息、Session对象、工具结果；必须在序列化/export边界对**副本**白名单化，不更改模型实际输入或原始审计事实。

API key/token/cookie永不导出；手机号、身份/地址/邮箱、订单/用户/会话等标识替换或租户隔离HMAC；限制字符串长度、列表/递归深度，处理Pydantic对象、metadata、tags、error message/stack和stream events。仅隐藏inputs/outputs不保证事件、metadata与exception也已隐藏。原始业务材料如确需保留，应在本地受限证据库，导出不可反推的引用和访问审计。自托管仍需RBAC、保留期、删除索引与备份、网络出站策略。

### 与Evaluation V2关联

以root_run_id和task_run_id关联case、turn、实际工具事件及终态oracle，feedback带评分器/版本/证据与judge_error，晚到评分用独立记录关联，不篡改原Span。错误分类至少区分模型/输出解析/检索/参数/权限/业务拒绝/事务/依赖/取消/telemetry；正常安全拒绝和pending不是需要学习纠正的错误。失败采样/保留不能只看HTTP500，因为工具失败可能HTTP200；若需失败全量需受控tail保留，而非预先丢掉根Span后承诺100%失败覆盖。

## 4. 验证方法与限制

<!-- acceptance: P0-D.4 -->

SOURCE_VERIFIED：现有 [API trace断言:14](../../../../tests/e2e/test_chat_api.py#L14) 和 [SSE拼接断言:48](../../../../tests/e2e/test_chat_api.py#L48) 没验证Span父子、异步隔离、flush、脱敏、SDK故障；[retry测试](../../../../tests/unit/test_retry.py)验证退避行为而非attempt Span；[Metrics测试](../../../../tests/unit/test_metrics.py)主要测试eval算术，不是Prometheus错误覆盖。原pytest未运行，本任务没有TEST_VERIFIED平台集成结果。

未来隔离验证应包含：两并发用户无串Span；CLI与HTTP同样有root；SINGLE/MULTI/AGENT与fallback完整叶树；每个模型用途与attempt用量；cache hit无虚构网络Span；SSE正常/早关/取消/commit后断流；导出关闭和故障不影响业务；所有导出字段加入合成PII canary，原始canary不得出现在任何payload、事件、日志或异常。性能指标包括Span完整率、错误/取消分类率、孤儿/重复Span率、脱敏漏检、导出丢弃、队列上限、P50/P95增量、内存和关闭flush时间。阈值待无Tracing隔离基线后确定，安全与不重复写入必须是硬门槛，不承诺当前性能数字。

静态验证保存到 `evidence/P0-D-validation.json`：引用/行号、源码哈希、环境/锁版本快照、范围完整性、验收覆盖。SDK未导入，未读取密钥或试连；自动回调兼容、真实多任务上下文、SSE取消和各部署运维均为BLOCKED/HYPOTHESIS，不能把metadata安装版本当SDK验收。未开始P1。
