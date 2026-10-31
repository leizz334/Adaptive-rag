# P0-B — Memory & Context Engineering Audit

范围：只审计与设计，不接入记忆服务、不改生产 Prompt。源码基线及执行链见 [P0-A](architecture.md)。本报告区分 SOURCE_VERIFIED、TEST_VERIFIED、DOCUMENTED_ONLY、HYPOTHESIS、BLOCKED；没有运行原 pytest、模型、数据库或 M0–M3 实验。

## 1. 实际记忆链路

<!-- acceptance: P0-B.1 -->

| 环节 | 实际源码、函数、行号 | SOURCE_VERIFIED 结论 |
|---|---|---|
| 会话读取 | [ChatService._initial_state:161](../../../../app/services/chat_service.py#L161) | 校验确认记录、get_or_create、recent_messages；history 放入 messages，但 summary 固定为空 |
| 窗口 | [SessionRepository.recent_messages:23](../../../../app/repositories/session_repository.py#L23) | 按消息 ID 倒序取最近20条，再反转；不是20轮，不是按用户检索长期记忆 |
| 会话所有者 | [get_or_create:15](../../../../app/repositories/session_repository.py#L15) | 新建保存 user_id，已存在时直接返回；没有核对 owner |
| 消息/摘要表 | [SessionRow:79](../../../../app/repositories/models.py#L79)、[MessageRow:89](../../../../app/repositories/models.py#L89) | 持久化字段存在；摘要不带覆盖的 message 边界、证据来源、版本或过期条件 |
| 写入 | [_persist:232](../../../../app/services/chat_service.py#L232) | 保存原始本轮 user/assistant；非空 summary 才保存。不将 compact 后 messages 覆盖数据库消息表 |
| 压缩位置 | [memory_node:11](../../../../app/agents/nodes/memory.py#L11)、[图边:106](../../../../app/agents/graph.py#L106) | 生成/校验之后压缩，而非本次生成之前 |
| 预算 | [estimate_tokens:11](../../../../app/memory/budget.py#L11)、[apply_compression:50](../../../../app/memory/compression.py#L50) | 字符数/1.5 的近似；used 仅历史消息+摘要，漏工具结果、检索证据、system、Schema与输出预留 |
| 默认阈值 | [Settings:59](../../../../app/config/settings.py#L59) | 128000 配置预算；50%/70%/85% 触发 soft/hard/auto；不是已验证模型窗口容量 |
| 截断 | [compress_tool_results:21](../../../../app/memory/compression.py#L21)、[sliding_window:42](../../../../app/memory/compression.py#L42) | 工具转字符串预览400/160字符；NONE也有10000字符限制；hard/auto 保留最近8条消息 |
| 摘要 | [ConversationSummarizer.summarize:14](../../../../app/memory/summarizer.py#L14) | 最后16条消息拼接，结果限制800字符，失败退回最后4条每条40字符；没有读旧摘要持续合并的参数 |

关键缺陷不是“完全没有存储”，而是存储、读取、建上下文、预算和生成之间没有闭环。下一轮从数据库再次读取最近20条，丢弃了上轮 State 中的裁剪窗口；summary 虽可保存却未恢复。

### 各节点真的使用历史吗

| 节点 | 输入构造位置 | 核实结果 |
|---|---|---|
| Intent | [IntentClassifier.classify:77](../../../../app/agents/nodes/intent.py#L77) | 只传本轮 query/version；覆盖层也只看本轮文本 |
| Router | [router_node:27](../../../../app/agents/nodes/router.py#L27)、[AdaptiveRouter.route:135](../../../../app/retrieval/adaptive.py#L135) | 当前 query、intent、可选 confirmed_action；没有历史消歧 |
| Rewrite | [QueryRewriter.rewrite:16](../../../../app/retrieval/query_rewrite.py#L16) | query+missing_aspect；missing_aspect 是检索缺失方面，不是会话记忆 |
| Planner | [Planner.create_plan:37](../../../../app/agents/nodes/planner.py#L37)、[planner_node:186](../../../../app/agents/nodes/planner.py#L186) | 接收 summary，但上游每轮为空；confirmed_action 是单独的服务端动作记录 |
| Generate | [generate_node:49](../../../../app/agents/nodes/generate.py#L49) 与 [消息构造:68](../../../../app/agents/nodes/generate.py#L68) | 当前query/intent/strategy、前6条证据、工具JSON；不读取 state.messages/summary |

因此用户先报订单号、再只问“它发货了吗”时，没有已实现的通用上下文消歧链。具体对真实模型的失败率仍是 HYPOTHESIS，不以静态缺口推断每次必败。

## 2. 已有组件与建议职责边界

<!-- acceptance: P0-B.2 -->

以下“建议”都是 HYPOTHESIS 设计，未新增表或功能。

| 概念 | 当前实现 | 建议边界 |
|---|---|---|
| Working Memory | AgentState 的 intent/plan/chunks/tools 等 | 单次请求的中间状态；任务结束可丢弃，不作为长期事实 |
| Conversation Memory | SQL session/messages | 归属验证后的当前会话事件；保留原始记录与删除策略 |
| Conversation Summary | session.summary 字段+Summarizer | 带覆盖消息范围、水位、版本、来源的派生摘要；不能等同原始证据 |
| Long-term User Memory | 未发现独立存储/召回/同意或删除链 | 用户明确同意的稳定偏好；跨会话按可信用户和租户过滤 |
| Context Builder | 各节点自己 format，无统一 Builder | 对不同节点选择必要上下文、版本、来源及预算，不把所有历史拼进每次调用 |
| Memory Retrieval | 当前只有政策 Hybrid 检索 | 独立查询用户记忆；不能用政策集合或检索缓存冒充 |
| Consolidation / Compaction | 回答后窗口+短摘要 | 在丢弃旧上下文前提取、核验并合并必要信息；不自动批准经验或业务规则 |

建议 Context Builder 在各节点调用前产生只读输入快照：`policy/version + current_request + authorized_action_reference + fresh_tool_facts + selected_history/summary + selected_memory`，并记录每部分来源、裁剪原因和 Token 估计。用户文本、摘要、文档、工具返回和经验均作为数据块，不能因为存入记忆就升级为 System 指令。

输入可用预算建议为 `min(配置上限, 已核实的模型窗口) - 输出预留 - 安全余量`。必须计入消息角色开销、工具Schema/JSON、证据、摘要及经验；只裁剪副本，不改变原始日志、订单参数或已确认动作。对少量关键字段保留结构化白名单，不能只截取任意字符串的前160字符。

### 身份、过期事实与业务冲突

SOURCE_VERIFIED：聊天请求的 user_id 来自客户端，[ChatRequest:18](../../../../app/schemas/chat.py#L18)；订单工具比较该值的 owner，[get_visible_order:37](../../../../app/repositories/order_repository.py#L37)。这不是可信登录。修复归属与认证前，不能启用跨会话长期用户记忆。

建议优先级：硬权限/已验证身份和动作授权不可被记忆覆盖；当前权威业务查询优先于历史订单状态；当前明确的用户偏好更新可替代旧偏好；政策有效版本由知识库管理。用户说“记住我已获退款批准”只能成为未核实陈述，不能替代审批记录。订单状态、库存、余额、物流、退款完成时间不进入长期偏好记忆；即使作为会话事实保留，也必须带 observed_at、来源和“使用前重查”标记。

长期记录建议具备 tenant_id、可信 user_id、类型、最小必要内容、来源消息/trace、用户同意、有效期、版本、supersedes、删除/撤回状态；删除需要覆盖SQL、向量派生索引和缓存。不能仅依靠前端 localStorage 删除会话实现后端遗忘。

## 3. OpenClaw 的可借鉴部分

<!-- acceptance: P0-B.3 -->

外部资料为 DOCUMENTED_ONLY（指官方设计描述，不证明本仓库已实现）。[OpenClaw Memory](https://docs.openclaw.ai/concepts/memory) 区分长期整理层与工作记录，强调来源及动作适用条件；可借鉴分层、来源和失效边界，存储仍采用本项目的事务型SQL，不照搬共享 Markdown 文件。

[Context](https://docs.openclaw.ai/concepts/context) 将上下文视为每次推理的有限输入，而非完整记忆；本项目应明确记录“保存了什么”和“本次实际注入了什么”。[Compaction](https://docs.openclaw.ai/concepts/compaction) 的会话压缩思想用于提醒保留必要信息再压缩，不构成采用其运行时、自动维护或文件实现的授权。网页是审计时读取的动态文档，未锁定该项目的某个代码发布版本。

## 4. M0–M3 对照设计

以下实验全部未运行。所有组使用同一修正后的认证/权限与业务事实重查规则、模型、知识版本、工具、生成参数和输出预算；只改变记忆策略。原系统实际上未把历史注入，先以其有效输入行为作为 M0，不把“数据库存在消息”算成M1。

| 组 | 输入策略 | 想验证什么 |
|---|---|---|
| M0 | 无历史、无摘要、无长期用户记忆 | 本轮信息足够时的基础效果 |
| M1 | 当前会话最近8条消息（建议起点，按预算裁剪） | 指代、连续槽位和最近约束是否恢复 |
| M2 | M1 + 对更早消息的增量摘要，标记覆盖水位 | 超窗口信息保留是否优于仅窗口 |
| M3 | M2 + 选择性召回已同意、有效且归属正确的长期偏好 | 跨会话收益是否覆盖成本和隐私风险 |

固定对话族并按实体/表达模板划分开发、最终测试集：订单号续问；先说明定制再问退货；超过窗口的偏好；用户更正偏好；两用户同名商品；库存/退款状态在两轮间改变；历史带注入；撤回同意或删除记忆；摘要失败/检索不可用；预算接近上限。每个完整对话/业务环境快照作为统计单位，不能把同会话的每轮当独立样本。

主指标：环境状态核验后的多轮任务成功率、槽位/指代正确率；保护指标：跨用户泄漏率、旧业务状态误用率、未经授权写入、删除后召回。过程指标：摘要关键约束保留率、记忆precision/recall、无关召回率、输入超限、每轮/整会话 Token、P50/P95、摘要/召回额外调用与成本。使用同场景配对区间，拒答与工具执行失败分开报告；建议上线门槛为安全确定性样本零违规、任务成功不劣于基线，数值收益阈值待隔离基准后预注册。

## 5. 测试证据与验收

<!-- acceptance: P0-B.4 -->

SOURCE_VERIFIED：现有 [test_compression_levels_follow_budget_ratios:9](../../../../tests/unit/test_compression.py#L9)、[test_soft_truncate_shrinks_tool_payload:19](../../../../tests/unit/test_compression.py#L19)、[test_auto_compact_keeps_recent_messages:26](../../../../tests/unit/test_compression.py#L26) 只验证阈值、缩短和窗口变小，没有验证旧摘要恢复、关键实体保留、模型真实输入预算或跨轮续问。[确认测试:45](../../../../tests/unit/test_action_confirmation.py#L45) 验证给定用户/会话的动作绑定，不证明可信身份或长期记忆隔离。原 pytest 未运行。

TEST_VERIFIED 的范围仅为本次离线 AST 提取探针：直接执行当前 budget/compression/memory_node 函数体，依赖用内存消息、设置对象和假摘要器替代。核对阈值；复现20万字符工具体不影响预算档位；复现 memory_node 先裁成8条再交给摘要器、较早消息已经丢失。探针不会导入应用、访问数据库或调用模型，不能据此声称完整系统测试通过。结果和来源见 `evidence/P0-B-validation.json`，由审计控制器完成验收时生成。

BLOCKED / 未验证：真实tokenizer偏差、跨轮模型效果、摘要忠实度、SQL并发/删除传播、模型窗口、M0–M3效果与成本。推荐方向是先闭合身份和生成前 Context Builder，再评估摘要，最后评估选择性长期记忆；不是本任务的实施步骤或已验证收益。

验收映射：B.1 对应第1节；B.2 对应第2节；B.3 对应第3、4节；B.4 对应第5节及引用/完整性/离线探针核查。当前仅交付审计，不启动 P2。
