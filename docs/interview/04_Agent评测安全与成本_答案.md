# Agent 评测、安全与成本答案

> 原题编号与标题保持题库原文。概念、源码能力和历史验收范围分别陈述；历史测试数字不表示本轮重跑，收费价格只在注明日期的历史记录范围内使用。

<a id="q137"></a>
### Q137：System/Developer/User/Tool消息分别承担什么职责？
★核心60

#### 1. 标准答案

System 通常承载平台级身份、安全边界和高层规则；Developer 承载应用开发者的任务约束与输出契约；User 表达当前目标与输入；Tool 表示工具调用结果及外部观察。具体支持哪些 role、优先级如何执行，要以所用供应商协议为准，不能假定所有兼容 API 都完全支持同一体系。工具返回、检索文档、历史与用户粘贴的“system 指令”都应视为数据，不能因内容自称高优先级就升级权限。真实授权由后端身份、工具白名单与业务校验执行，不能只靠 Prompt 文字。

#### 2. 面试口述版

这些角色首先帮助区分规则、目标和观察。System 放身份与总体约束，Developer 是应用规则，User 是用户当前请求，Tool 是外部调用得到的数据。但我不会把某个平台的优先级直接套到所有模型 API，要核对供应商实际支持的消息格式。项目的生成和裁判主要显式构造 system、user 两类消息，把检索证据与工具结果放入受约束的上下文；不能因此说已经实现原生四角色工具对话。安全上更关键的是，文档或工具结果里的命令不能覆盖规则，用户也不能靠一句“我是管理员”获得权限，最终仍由认证身份与后端工具校验控制执行。

#### 3. Adaptive-RAG实际实现

**已实现** `generate_node()` 以 `ANSWER_SYSTEM` 构造 system，再以 `ANSWER_USER` 放当前问题、证据与工具 JSON；会话上下文被标记为不可信数据。[app/agents/nodes/generate.py:L89](../../app/agents/nodes/generate.py#L89)、[app/agents/nodes/generate.py:L102](../../app/agents/nodes/generate.py#L102)。`ANSWER_SYSTEM` 要求仅依据证据，缺资料明确不确定，禁止未确认操作宣称完成。[app/prompts/answer.py:L5](../../app/prompts/answer.py#L5)。`DeepSeekProvider.generate()` 透传 messages 到请求 payload。[app/providers/deepseek.py:L63](../../app/providers/deepseek.py#L63)。**项目未实现**在该生成路径中独立的 developer role 与原生 tool-message 回合；项目工具由应用编排执行后将结果序列化进入上下文，不能把概念四角色说成已全部使用。

#### 4. 面试官可能追问

- **追问：工具结果写“忽略所有规则”怎么办？** 答：将其视为外部不可信内容，限制到证据用途；真正权限与执行校验不交给模型判断。
- **追问：用户粘贴 `role: system` 会升级权限吗？** 答：不会，它只是 user 内容中的字符串；消息角色由服务端构造。
- **追问：没有 developer role 是否不能实现应用规则？** 答：可以用该供应商支持的消息格式表达规则，但要说明实际协议，不能伪称具有另一协议的优先级保证。

#### 5. 测试与证据

`test_compact_judge_prompt_omits_open_ended_rationale` 核对裁判 Prompt 契约；`test_judge_outage_no_arbitrary_policy_excerpt_or_false_configuration` 覆盖不把任意政策摘录当安全事实。[tests/unit/test_p2s_answer_reliability.py:L66](../../tests/unit/test_p2s_answer_reliability.py#L66)、[tests/unit/test_p2s_answer_reliability.py:L97](../../tests/unit/test_p2s_answer_reliability.py#L97)。这些不能证明模型永远遵守角色层级。完整四角色兼容性及任意注入免疫：**未实现/未验证**；本轮未调用模型。

<a id="q138"></a>
### Q138：Prompt Engineering 与 Context Engineering有什么差异？
★核心60

#### 1. 标准答案

Prompt Engineering 关注如何表达任务、规则、示例和输出格式；Context Engineering 关注在每次调用前，为该节点选择哪些历史、摘要、检索证据、工具结果与状态，如何排序、压缩、标记可信度并满足预算。两者有重叠：良好的指令依赖合适上下文，上下文也要有清晰的格式与规则。Context 不是越多越好，过期业务事实、歧义指代、跨用户记忆和外部恶意指令都可能降低质量。评估应看节点完成率、事实完整性、隔离与 token 成本，而非 Prompt 长度。

#### 2. 面试口述版

Prompt Engineering 解决“怎样向模型说明任务”，Context Engineering 解决“这一次到底让模型看到什么”。比如我可以把回答格式写得很清楚，但如果把另一个用户的历史或过期订单状态放进来，模型仍然可能做错。项目里 Prompt 模块定义生成、分类和裁判规则，ContextBuilder 则选择历史、消解订单指代，M2 还利用受控摘要；不同节点通过 node_query 和 node_context 获取相关内容。生成时会合并当前工具事实和必要子目标，最后完整请求还有预算检查。我会把记忆当解释用户意图的辅助，实时金额和状态仍必须重新查工具，不能让历史信息变成授权或最新业务事实。

#### 3. Adaptive-RAG实际实现

**已实现** Prompt 模板层，如 `ANSWER_SYSTEM/ANSWER_USER`。[app/prompts/answer.py:L5](../../app/prompts/answer.py#L5)。上下文层由 `ContextBuilder.build()` 按 memory mode、历史和摘要选择 `SelectedContext`，M0 返回无历史上下文；`node_query/node_context` 为节点取值。[app/memory/context.py:L83](../../app/memory/context.py#L83)、[app/memory/context.py:L249](../../app/memory/context.py#L249)。生成节点附加受控上下文、当前必要证据与未解决子目标；`enforce_request_budget()` 检查完整请求及最大输出。[app/agents/nodes/generate.py:L102](../../app/agents/nodes/generate.py#L102)、[app/memory/budget.py:L14](../../app/memory/budget.py#L14)。**部分实现**上下文工程；尚无通用自动优化器证明任意上下文配置最优，估算界限也不是供应商实际 token usage。

#### 4. 面试官可能追问

- **追问：为什么不把全量聊天历史放进去？** 答：预算有限，历史还可能冲突、过期或引入歧义；应按节点用途选择，并保留澄清路径。
- **追问：摘要记住“订单已支付”，后续还要查吗？** 答：要。摘要用于指代，订单状态、金额和权限以当前工具及数据库为准。
- **追问：如何判断是 Prompt 问题还是上下文问题？** 答：固定规则看输入是否含必要证据与实体，再做仅替换上下文或仅替换指令的配对实验，避免同时改多个变量。

#### 5. 测试与证据

`test_selected_memory_payload_bounded_without_truncating_entity` 检查被选记忆受限且不截断实体；`test_complete_serialized_input_and_output_reservation_checked_before_http` 检查最终请求超限先阻断。[tests/unit/test_context_budget.py:L34](../../tests/unit/test_context_budget.py#L34)、[tests/unit/test_context_budget.py:L10](../../tests/unit/test_context_budget.py#L10)。`test_scripted_arm_exercises_node_prompts_with_no_paid_tokens` 是 **Offline Scripted** 对照，不是真实模型 Context 收益评测。[tests/integration/test_memory_ablation.py:L4](../../tests/integration/test_memory_ablation.py#L4)。本轮未重跑业务测试。

<a id="q152"></a>
### Q152：如何定义Agent任务成功率，能只用“模型回答看起来对”吗？
★核心60

#### 1. 标准答案

先定义任务可观察的完成条件：目标是否达成、必要工具及参数是否正确、权限和审批是否满足、提交后的业务状态是否正确、是否存在额外副作用、答案是否准确传达结果。任务成功率可定义为满足全部必要条件的任务数除以预先声明的有效任务总数，同时单列 ERROR 和 NOT_RUN。查询任务以实际工具观察为证据，写任务以独立连接看到的已提交状态及审计为证据；路径可以允许等价实现，但危险副作用不能因回答正确被豁免。还需记录成本、时延与失败原因。

#### 2. 面试口述版

我不把回答流畅当任务完成。用户问订单金额，要真的查到指定用户的指定订单，并正确表达结果；用户确认取消，要看到数据库已提交取消状态、审计与幂等行为，还要确认别的订单没被改。项目评测把工具轨迹、独立环境状态和最终答案分开，Gold 不传给业务服务。统计时我会保留未执行和基础设施错误，说明分母，不把 NOT_RUN 当成功。真实 DeepSeek 历史验收只有四项业务通过，HITL 因请求额度用尽没有运行；二十次模型 HTTP 成功不能推导出所有业务成功，更不能据此声称线上成功率或真实用户规模。

#### 3. Adaptive-RAG实际实现

**已实现** `score_goal()` 对初始/最终订单、退款/退货、审计及必要工具 observations 独立评分，禁止未授权订单变更、受保护字段修改和额外表副作用，不读取自然语言答案来决定数据库目标。[eval/goal_scoring.py:L7](../../eval/goal_scoring.py#L7)。`EvaluationResult` 显式区分 PASS/FAIL/ERROR/NOT_RUN 并记录 dataset SHA 与 model_evaluation。[eval/contracts.py:L44](../../eval/contracts.py#L44)。`run_scenarios()` 为每场景构建独立 BusinessEnvironment，不把 expected/gold 注入服务。[eval/multiturn.py:L67](../../eval/multiturn.py#L67)。**部分实现**任务验证；不是经过大规模生产用户验证的在线成功率平台。

#### 4. 面试官可能追问

- **追问：回答说已取消但事务没提交，算成功吗？** 答：不算。必须在独立观察中确认提交后状态，不能仅看当前事务内对象。
- **追问：工具顺序不同但结果对，是否必须失败？** 答：可允许等价有效路径，但授权、必要依赖、调用上限及副作用约束仍必须满足。
- **追问：20/20 HTTP 成功率能写成 Agent 100% 吗？** 答：不能，它的分母是模型请求；业务场景数、执行状态和目标通过率必须另外统计。

#### 5. 测试与证据

`test_query_goal_uses_observed_tool_result_not_answer`、`test_uncommitted_write_cannot_satisfy_goal` 分别覆盖观察型查询和提交边界。[tests/integration/test_goal_evaluation.py:L11](../../tests/integration/test_goal_evaluation.py#L11)、[tests/integration/test_goal_evaluation.py:L157](../../tests/integration/test_goal_evaluation.py#L157)。2026-11-15 真实历史报告记录四项业务 PASS、HITL NOT_RUN/BUDGET_BLOCKED。[真实业务报告:L9](../../research/docs/agent_engineering_upgrade/deepseek_business_acceptance/REPORT.zh-CN.md#L9)。947 pytest/54 前端测试是该报告的历史回归，**本轮未运行**；线上 SLA/用户成功率**未验证**。

<a id="q153"></a>
### Q153：如何搭建RAG评测集，问题、金标准证据和答案从哪来？
★核心60

#### 1. 标准答案

问题来自脱敏业务问题、人工编写的任务与有明确来源的合成扩展；必须标注来源类型。固定语料快照，人工标出相关文档/块、必要条件、允许答案要点和无答案理由，避免把模型生成的参考答案直接当真值。覆盖精确编号、同义改写、多证据、冲突版本、缺资料、权限隔离及长尾失败。按文档族、来源或时间划分开发与留出集，避免同一模板改写跨集合泄漏；冻结版本、哈希和评分 rubric。检索、答案支持度、完整性和拒答分别计分，并人工复核争议。

#### 2. 面试口述版

我会先固定知识库版本，再收集有代表性的问题，让人标注应引用哪些证据和必须表达哪些条件，而不是先让模型生成一个漂亮答案就当 Gold。问题可以来自业务记录、人工场景和合成扩展，但来源必须标清楚，当前项目不能声称有大规模真实用户日志。现有 RAG 集用相关文档 ID 和答案关键词，适合初步回归，严格的多证据评测还需要逐块和条件级标注。开发集用于调参，留出集按来源或模板隔离，Gold 不进入 Prompt。评测要同时看检索、忠实度、完整性和无答案处理，安全场景还要检查用户 A 的问题不会拿到用户 B 的私有材料。

#### 3. Adaptive-RAG实际实现

**部分实现**数据与评分契约。`rag_eval.jsonl` 每条有 `id/query/relevant_doc_ids/gold_answer_contains`，例如定制退货问题指向 return_policy；它是仓库维护的评测资料，不能声称来自已验证线上用户分布。[eval/dataset/rag_eval.jsonl:L1](../../eval/dataset/rag_eval.jsonl#L1)。多轮 `load_scenarios()` 校验 schema、重复 ID 并计算 SHA256；运行器明确不把 Gold 传给 service/provider/prompt。[eval/multiturn.py:L56](../../eval/multiturn.py#L56)、[eval/multiturn.py:L76](../../eval/multiturn.py#L76)。**项目未实现**全量人工双标的声明级 RAG benchmark 与线上流量采样平台；历史合成政策验收不是生产政策评测。

#### 4. 面试官可能追问

- **追问：答案关键词全中就一定正确吗？** 答：不一定，否定关系、主体和例外可能错；关键词指标只作代理，要检查证据支持和完整条件。
- **追问：LLM 能帮助出题吗？** 答：可以做候选和改写，但人要核对来源、难度、可回答性及 Gold，防止模型共同偏差。
- **追问：如何防止留出集污染？** 答：按来源/模板划分，冻结哈希，限制调参访问，发现失败后加入新回归集并建立新的未见留出集，保留旧结果。

#### 5. 测试与证据

`test_baseline_is_offline_dataset_snapshot` 固定 Offline baseline 的身份；`test_reject_unknown_execution_and_result_states` 检查执行状态契约。[tests/unit/test_eval_contracts.py:L24](../../tests/unit/test_eval_contracts.py#L24)、[tests/unit/test_eval_contracts.py:L8](../../tests/unit/test_eval_contracts.py#L8)。`test_frozen_scenarios_have_reliable_oracles_and_honest_context_failure` 检查冻结场景及诚实失败。[tests/integration/test_multiturn_evaluation.py:L6](../../tests/integration/test_multiturn_evaluation.py#L6)。数据集人工双标一致率和线上代表性：**未验证**；本轮仅文档核对。

<a id="q159"></a>
### Q159：如何做Memory M0/M1/M2对照，排除随机性和测试污染？
★核心60

#### 1. 标准答案

先固定每组定义：无历史、有限历史、历史加摘要等只是常见设计，必须与项目实际配置对应。控制模型版本、温度、Prompt、工具、JSON 修复、语料、时钟及初始数据库状态，只改变 Memory 策略；各组隔离会话、缓存和存储，采用同一冻结场景配对比较。真实模型需重复试验并报告波动，temperature=0 也不是绝对确定性保证。评估指代消解、长窗口遗忘、实时状态更新、跨用户隔离、误记忆、成本和延迟；Gold 不能出现在历史、摘要或 Provider 输入。脚本化 Offline 对照只能验证机制。

#### 2. 面试口述版

我会先确认 M0、M1、M2 在代码里分别启用了什么，再做只改变 Memory 的对照。项目 M0 不引入历史，M1 使用受控历史，M2 在此基础上使用摘要相关能力；JSON 修复等可靠性逻辑应对所有组一致，不能把修复收益算给记忆。每组重新创建隔离环境，用同一组冻结问题和状态变更，重点看“这单”能否指回正确订单，以及历史说已支付但当前已经取消时是否重新查事实。现有消融明确是 Offline Rule 或 Scripted，禁止网络、付费调用为零；它能证明链路和输入被使用，不能证明真实模型收益，更不能通过反复调留出集把分数做高。

#### 3. Adaptive-RAG实际实现

**已实现** `ContextBuilder.build()` 的 M0 无历史分支；ChatService 在 M2/M3 处理摘要，M1 保留有限历史上下文。[app/memory/context.py:L95](../../app/memory/context.py#L95)、[app/services/chat_service.py:L205](../../app/services/chat_service.py#L205)。`eval.memory_ablation.run_arm()` 为各场景创建 Provider，patch 网络连接为禁止，输出 OFFLINE_RULE/OFFLINE_SCRIPTED、真实模型 NOT_RUN、paid_api_calls=0。[eval/memory_ablation.py:L124](../../eval/memory_ablation.py#L124)。`evaluate()` 固定 heldout 哈希，保留原结果路径，遍历 M0/M1/M2/M3，并声明所有组使用相同 JSON 可靠性修复。[eval/memory_ablation.py:L265](../../eval/memory_ablation.py#L265)。**部分实现**控制实验；真实模型重复消融与统计显著性**未验证**。

#### 4. 面试官可能追问

- **追问：temperature=0 还需要重复吗？** 答：真实服务可能有非确定性和版本漂移，仍需重复或配对置信区间；确定性 fixture 则要明确其限制。
- **追问：ScriptedProvider 返回支持，能证明 Faithfulness 吗？** 答：不能，它是固定规则响应并标注不是真实语义裁判，作用是检查节点上下文和编排。
- **追问：M2 记住错误订单状态怎么办？** 答：记忆只帮助确定用户指代，实时状态仍需工具查询；评测应包含对话中途状态改变和跨用户拒绝。

#### 5. 测试与证据

`test_scripted_arm_exercises_node_prompts_with_no_paid_tokens` 对同一 context_loss 场景比较 M0/M1，明确断言 paid_api_calls 和 paid_tokens 为 0。[tests/integration/test_memory_ablation.py:L4](../../tests/integration/test_memory_ablation.py#L4)。`ScriptedProvider` 的文档与裁判固定输出明确写有 OFFLINE_SCRIPTED_NOT_A_SEMANTIC_JUDGE。[eval/memory_ablation.py:L50](../../eval/memory_ablation.py#L50)、[eval/memory_ablation.py:L104](../../eval/memory_ablation.py#L104)。这些是可复核机制证据，本轮未运行；不能据此报告真实 Memory 提升百分比。

<a id="q190"></a>
### Q190：一个用户请求为什么会触发多次模型API请求？怎样定位每次Token消耗？
★核心60

#### 1. 标准答案

一次用户请求可能经过意图分类、策略路由、Query 改写、规划、生成、证据裁判与自纠错，每个节点都可能单独调用模型；重试也会增加 HTTP 尝试。应分清用户请求、逻辑 LLM 调用与实际 HTTP attempt，不能仅按最后生成调用估算成本。建立请求 root span，嵌套 Graph 节点、LLM 和 HTTP attempt，记录各次 prompt/completion/total usage、模型、时延与状态，并注明未知 usage。汇总时选择一个层级，避免父子 span 重复相加；费用账本预留与观测 usage 另算。

#### 2. 面试口述版

用户点一次发送，并不等于只调用模型一次。分类、路由、规划、回答和裁判各有职责，重试还会额外产生 HTTP 请求。我会先看 Trace 的节点树，再分出逻辑模型调用和实际 HTTP attempt，用每次返回的输入、输出和总 usage 解释消耗，避免只看最后答案的 token。项目最早的真实问候就经过 Intent、Router、Generate 三次调用，总 usage 一千二百零七，这三次不是重试。后来的四项业务验收共二十次 HTTP，是另一授权范围。账本预留、实际 usage 和费用估算分别报告，不能把其中任意一个数字当成另一个，也不能把二十个成功响应称为二十项业务成功。

#### 3. Adaptive-RAG实际实现

**已实现** `DeepSeekProvider.generate()` 带 `llm.deepseek` span，内部 `_call()` 带 `llm.http_attempt`，经 `with_exponential_backoff` 执行；响应解析 prompt/completion/total tokens。[app/providers/deepseek.py:L50](../../app/providers/deepseek.py#L50)、[app/providers/deepseek.py:L75](../../app/providers/deepseek.py#L75)、[app/providers/deepseek.py:L108](../../app/providers/deepseek.py#L108)。`traced()` 从 LLMResponse.usage 记录数值到 LLM span，初始化 `usage_known=False`，不能将异常时未知 usage 记成确定零消费。[app/observability/tracing.py:L164](../../app/observability/tracing.py#L164)、[app/observability/tracing.py:L208](../../app/observability/tracing.py#L208)。**部分实现**请求关联与观察；费用可信结算由独立 BudgetedTransport/UsageEvidence 控制，不靠前端汇总或模型自报。

#### 4. 面试官可能追问

- **追问：哪一层作为成本次数分母？** 答：预算按实际 HTTP 尝试，包含重试；逻辑 LLM 调用用于诊断，用户轮次用于产品体验，三者分别统计。
- **追问：为什么不能把所有 span 的 tokens 相加？** 答：父子 span 可能描述同一个调用，混加会重复计数；选定 LLM usage 层级并对账 HTTP 账本。
- **追问：缺 usage 就按零算吗？** 答：不能，标未知并保守保留预留；是否已消费不明确时阻断继续付费。

#### 5. 测试与证据

历史 2026-11-14 报告记录三次调用分别为 718、219、270 tokens，总计 1207，明确不是重试。[首次真实报告:L25](../../research/docs/agent_engineering_upgrade/deepseek_live_acceptance/DEEPSEEK_LIVE_ACCEPTANCE_REPORT.md#L25)。2026-11-15 新授权记录 20 个 LLM span、13791 tokens；真实四项业务通过，HITL NOT_RUN。[真实业务报告:L17](../../research/docs/agent_engineering_upgrade/deepseek_business_acceptance/REPORT.zh-CN.md#L17)、[真实业务报告:L43](../../research/docs/agent_engineering_upgrade/deepseek_business_acceptance/REPORT.zh-CN.md#L43)。`test_grant_counts_every_http_retry_against_twenty_attempts` 验证重试计数。[tests/unit/test_budget_authorization.py:L254](../../tests/unit/test_budget_authorization.py#L254)。本轮无 HTTP/模型调用。

<a id="q191"></a>
### Q191：你项目里首次1207实际Token却预留8986，如何解释？
★核心60

#### 1. 标准答案

实际 usage 是供应商返回的输入/输出 token 计数；预留是发送前按最坏情况做的容量占用，目的不同。预留通常包括完整序列化请求的保守输入界限、协议余量和 `max_tokens` 输出上限，实际输出远少于最大值时差距会很大。还必须先确认两个数属于同一批请求、同一授权范围和同一账本阶段。原始预留、可信结算后的有效占用、usage 费用估算和供应商实际扣费是不同指标，不得互换；改进结算也不能追溯伪造旧请求证据。

#### 2. 面试口述版

这两个数确实来自同一个历史范围：二〇二六年十一月十四日首次真实问候，共三次 HTTP，输入一千零八十六、输出一百二十一，总 usage 一千二百零七。八千九百八十六是当时门禁累计保守预留，按完整请求、协议余量和最大输出估计，旧实现消费后不退回，所以两者明显不同。当时一万 token 上限只剩一千零十四，下一次 Intent 预留放不下就停止，不能按 usage 擅自重置余额。十一月十五日的新授权和可信结算属于后续另一范围，我会分开讲，不能用后续二十次或结算后的账本值替换原历史，也不能把预留说成供应商账单。

#### 3. Adaptive-RAG实际实现

**已实现且有历史证据**：2026-11-14 首次问候 3 次 HTTP，usage 输入/输出/总数为 1086/121/1207，累计保守预留 8986，原 Token 上限 10000；旧阶段未返额。[首次真实报告:L33](../../research/docs/agent_engineering_upgrade/deepseek_live_acceptance/DEEPSEEK_LIVE_ACCEPTANCE_REPORT.md#L33)、[首次真实报告:L44](../../research/docs/agent_engineering_upgrade/deepseek_live_acceptance/DEEPSEEK_LIVE_ACCEPTANCE_REPORT.md#L44)。当前 `_request_reservation()` 以 `len(payload)+1024+16*len(messages)` 作输入界限，再加最大输出；它是保守估算，不是 tokenizer 实测。[app/providers/paid_budget.py:L76](../../app/providers/paid_budget.py#L76)。

后续**已实现**可信 usage 结算且保留原始预留，但旧三条没有补结算；2026-11-15 新增 20 次不是原问候范围。[真实业务报告:L31](../../research/docs/agent_engineering_upgrade/deepseek_business_acceptance/REPORT.zh-CN.md#L31)、[真实业务报告:L56](../../research/docs/agent_engineering_upgrade/deepseek_business_acceptance/REPORT.zh-CN.md#L56)。**未验证**供应商实际扣款账单，不能用估算费用冒充。

#### 4. 面试官可能追问

- **追问：8986 是否就是模型上下文实际长度？** 答：不是，是三次请求累计保守占用，包含输出最大值和协议余量；上下文与累计预算也不是同一层限制。
- **追问：为什么不把差额立即返还？** 答：旧阶段没有可信结算能力，不能靠前端统计或缺失原响应补造结算；后续追加结算需完整可信证据。
- **追问：能否用新授权绕开旧限制？** 答：只有明确追加授权才可增加范围，并保留同账本原历史；不能换账本、删历史或重启清零。

#### 5. 测试与证据

`test_exact_token_ceiling_denies_without_consuming_request` 检查预留放不下时先拒绝；`test_grant_adds_capacity_without_mutating_original_history_or_fingerprint` 检查追加授权不改旧记录。[tests/unit/test_live_authorized_budget.py:L40](../../tests/unit/test_live_authorized_budget.py#L40)、[tests/unit/test_budget_authorization.py:L24](../../tests/unit/test_budget_authorization.py#L24)。1207/8986 来自 **2026-11-14 已有公开验收报告**，不是本轮重跑，也不是 2026-11-15 13791 tokens 新授权的统计。本轮没有读取私有账本或凭证。

<a id="q192"></a>
### Q192：为什么需要费用预留、可信usage结算和不可确定消费阻断？
★核心60

#### 1. 标准答案

费用预留解决并发请求都认为“余额够”的竞态：发送前在同一原子事务检查容量并占用最坏费用。可信 usage 结算在响应完整、模型与格式正确、计数一致且传输消费完成后追加真实用量，使有效占用可低于预留；原预留仍不可改写，尝试次数不返还。网络超时、断流或进程崩溃可能已经在供应商侧消费，无法确认时保留预留并阻断后续付费，防止重试无限扩大损失。账本必须持久、可审计，并区分完成、已结算和消费不确定。

#### 2. 面试口述版

这三步分别解决发送前、完成后和失败时的问题。先原子预留，避免两个并发请求同时花掉同一余额；拿到完整可信 usage 后追加结算，释放最坏估计与实际之间的差额；超时或断流时不知道供应商是否消费，就保留占用并停止后续付费。项目用持久 SQLite 事务记录每次 HTTP，次数不返还，原始预留也不改写。真实验收中二十次都成功，但最早五条没有完成账本结算，仍按原预留占用，后十五条才成功结算。因此实际 usage 费用估算低于账本有效占用是可解释的，不能为追求好看的成本数字补造旧证据或把不确定消费当零。

#### 3. Adaptive-RAG实际实现

**已实现** `AttemptLedger.reserve()` 在 `_transaction()` 中检查容量并写 pending、预留证据及授权映射；`settle()` 追加可信结算，不修改原始 attempts 预留。[app/providers/paid_budget.py:L653](../../app/providers/paid_budget.py#L653)、[app/providers/paid_budget.py:L551](../../app/providers/paid_budget.py#L551)。`ensure_ready/_check_capacity` 遇 pending/uncertain 阻断，不能重启自动清零。[app/providers/paid_budget.py:L612](../../app/providers/paid_budget.py#L612)。`UsageEvidence.settlement()` 校验模型、响应结构、finish、usage 或 SSE 完整结束才产生结算依据。[app/providers/usage_settlement.py:L226](../../app/providers/usage_settlement.py#L226)。**部分实现**本地开发付费门禁与授权账本，不等于生产跨地域计费系统或供应商扣款对账平台。

#### 4. 面试官可能追问

- **追问：HTTP 200 就能释放预留吗？** 答：不能，还要验证完整解码后的响应与可信 usage，提前关闭或读取失败不能当正常结算。
- **追问：业务成功和结算成功为什么不同？** 答：Provider 可成功解析回答，但观察层未拿到合格证据；两条路径的完成条件不同，应分别保留事实。
- **追问：为什么次数不返还？** 答：真实 HTTP 尝试已经发生，费用降低不代表尝试没发生；返还次数会让重试绕过请求上限。

#### 5. 测试与证据

`test_atomic_admission_across_processes` 验证跨进程原子准入；`test_uncertainty_blocks_without_retry` 验证不确定消费阻断。[tests/unit/test_paid_budget.py:L135](../../tests/unit/test_paid_budget.py#L135)、[tests/unit/test_paid_budget.py:L236](../../tests/unit/test_paid_budget.py#L236)。`test_compressed_provider_success_settles_decoded_usage` 覆盖 gzip/deflate JSON/SSE 解码结算。[tests/unit/test_paid_budget_compression.py:L26](../../tests/unit/test_paid_budget_compression.py#L26)。2026-11-15 历史：20 次/13791 usage tokens，usage 估算上界 $0.0053856，账本有效费用 $0.0125115，20 完成/15 已结算，最早五条保留原预留；费用按该历史报告记录费率，**非现价或供应商账单**。[真实业务报告:L41](../../research/docs/agent_engineering_upgrade/deepseek_business_acceptance/REPORT.zh-CN.md#L41)。本轮未付费运行。

<a id="q193"></a>
### Q193：Trace中如何关联Graph节点、模型请求、工具、数据库与返回事件？
★核心60

#### 1. 标准答案

为用户请求分配应用 trace/request ID，以 root span 关联一次处理，节点、模型、HTTP 尝试、工具与事务作为子 span，通过 root_id/parent_id 形成树；会话 ID 用于跨轮关联，不能代替每次请求 ID。SSE 生命周期可能长于普通函数返回，应覆盖迭代、断连和取消清理。模型记录 usage 与尝试，工具记录状态和受控计数，数据库至少区分操作与 commit，避免把“工具返回成功”误认为事务持久化。元数据要白名单化、限量与脱敏，导出故障不能改变业务结果。

#### 2. 面试口述版

我希望从一次用户请求往下看到完整因果链：哪个 Graph 节点发起模型调用，是否重试，调用哪个工具，最后事务有没有提交，SSE 在哪里结束。项目用 ContextVar 维护当前 root 和 parent，span 有独立 ID、父 ID、耗时和状态，用户与会话标识通过进程盐 HMAC 引用，避免直接导出原文。ChatService 还标记加载、图调用、提交和持久化，LLM span 记录 usage。但它不是全量 SQL 语句追踪，通用 Trace 也不会序列化完整 State 或工具参数。调试时要区分安全事件摘要与受控证据，不能为了看清链路把 Key、用户内容和原始数据库资料放进日志。

#### 3. Adaptive-RAG实际实现

**已实现** `Span` 的 id/root_id/parent_id，`TraceRecorder.turn()` 给根节点增加应用 trace、session、user、request 的 HMAC 引用；`span()` 用 ContextVar 嵌套并记录 error/cancelled。[app/observability/tracing.py:L61](../../app/observability/tracing.py#L61)、[app/observability/tracing.py:L104](../../app/observability/tracing.py#L104)、[app/observability/tracing.py:L151](../../app/observability/tracing.py#L151)。ChatService 标记 `graph.invoke/transaction.commit/session.persist`，工具 `BaseTool` 标记 `tool.execute`。[app/services/chat_service.py:L320](../../app/services/chat_service.py#L320)、[app/services/chat_service.py:L342](../../app/services/chat_service.py#L342)、[app/tools/base.py:L72](../../app/tools/base.py#L72)。**部分实现**跨层关联：不是每条 SQL 自动埋点，也不能承诺进程盐引用可跨重启稳定关联；完整参数与正文不进入通用 metadata。[app/observability/tracing.py:L42](../../app/observability/tracing.py#L42)。

#### 4. 面试官可能追问

- **追问：两个并发请求会串 parent 吗？** 答：应使用异步上下文局部变量而非全局可变 parent，并用并发根测试验证隔离。
- **追问：SSE 创建迭代器后函数返回，trace 就结束了吗？** 答：不能过早结束，要覆盖迭代和关闭；项目 traced 对 async generator 用 finally 关闭源，并记录取消。
- **追问：Trace 导出失败是否让订单失败？** 答：观察系统不应改变业务结果，项目记录 export_errors 并捕获导出错误；事务成功仍需独立验证。

#### 5. 测试与证据

`test_concurrent_roots_and_privacy` 覆盖并发根与隐私；`test_disabled_and_export_failure_do_not_change_result` 覆盖关闭/导出故障；`test_generator_close_and_span_bound` 覆盖生成器关闭和 span 上限。[tests/unit/test_tracing.py:L17](../../tests/unit/test_tracing.py#L17)、[tests/unit/test_tracing.py:L42](../../tests/unit/test_tracing.py#L42)、[tests/unit/test_tracing.py:L57](../../tests/unit/test_tracing.py#L57)。`test_error_records_type_not_exception_content` 检查不导出异常正文。[tests/unit/test_tracing.py:L78](../../tests/unit/test_tracing.py#L78)。本轮只核对测试与源码；全 SQL 自动关联、跨进程统一追踪覆盖率：**未实现/未验证**。
