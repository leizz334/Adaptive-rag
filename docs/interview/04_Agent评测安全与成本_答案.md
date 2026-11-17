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

<a id="q139"></a>
### Q139：Zero-shot、Few-shot、CoT、ReAct和结构化输出分别适合何时用？

#### 1. 标准答案

Zero-shot适合清晰任务，Few-shot示例规范边界，CoT用于分解但不要求暴露内部推理，ReAct结合行动与观察，结构化输出约束接口。按可验证需求选择，示例不能代替授权。

选型可按信息来源与结果消费者分解：只需已有知识且边界清楚，先用 Zero-shot；需要展示分类边界或格式，用经过核验的 Few-shot；需要外部实时事实，使用受控工具与观察；需要机器消费，则叠加 Schema。CoT 是推理提示方法，不等同于可靠计划，也不应要求披露模型内部推理。ReAct 可以用简明行动理由及工具记录实现可审计性。增加示例或回合会提高上下文和调用成本，收益要用留出任务验证。

#### 2. 面试口述版

我会先明确输出要被谁使用。简单分类可零样本，边界模糊时用少量经过核验的示例；复杂任务可要求分解目标和给简明理由，但不依赖公开内部推理。需要外部事实时结合工具观察，机器消费结果则加结构化契约。项目是有边界的图编排，Planner产出计划，代码执行工具再生成，不是无限自由ReAct。JSON模式也不等于参数或事实正确。我会用相同问题比较示例带来的收益与token成本，避免示例把Gold或危险操作暗示给模型，更不会把一种提示方法包装成所有任务最优。

#### 3. Adaptive-RAG实际实现

已实现Planner计划与JSON解析，未实现通用无限ReAct或CoT训练。[app/agents/nodes/planner.py:L55](../../app/agents/nodes/planner.py#L55) [app/providers/json_parser.py:L46](../../app/providers/json_parser.py#L46)

#### 4. 面试官可能追问

- **追问：Few-shot越多越好吗？** 答：示例可能挤占证据并引入偏差。
- **追问：结构正确即可执行吗？** 答：还需权限、实体和业务校验。

#### 5. 测试与证据

test_json_parser_rejects_garbage 检查解析边界。[tests/unit/test_tools_and_parser.py:L34](../../tests/unit/test_tools_and_parser.py#L34) 提示方法全面对照未验证。

<a id="q140"></a>
### Q140：为什么一条提示词不能保证工具调用安全或事实正确？

#### 1. 标准答案

提示词不能建立权限、证明事实或保证事务。使用可信身份、工具白名单、schema、owner校验、确认、幂等和独立结果观察；模型只提出建议。

模型属于概率生成组件，无法执行数据库约束。安全链路应是：认证主体→模型候选计划→白名单和参数校验→对象权限→高风险确认→幂等事务→独立结果核验。每一层承担不同责任，例如 Pydantic 保证字段形状，Owner 校验保证能访问该订单，事务保证提交一致性；任何一层都不能被“模型答应遵守”替代。事实正确还要检查信息来源、时效和引用支持关系。

#### 2. 面试口述版

一条提示词只能影响模型倾向，不能创造后端权限，也无法证明“订单已取消”。即便输出完全符合JSON，订单号也可能错，用户也可能没有权。项目把模型计划交给代码校验与工具执行，危险写入需要确认，最终事实来自工具和已提交状态；生成规则只是其中一层。我的测试会故意让模型选择越权对象、伪造确认和重复请求，检查后端是否挡住，而不是看模型是否说“我遵守规则”。事实也要核证据和单位，裁判故障走安全回退。这样能说明控制点，但不能宣称任何攻击都已防住。

#### 3. Adaptive-RAG实际实现

已实现Tool.parse/run与后端确认机制；单Prompt安全保证未实现。[app/tools/base.py:L61](../../app/tools/base.py#L61) [app/services/chat_service.py:L272](../../app/services/chat_service.py#L272) [eval/goal_scoring.py:L7](../../eval/goal_scoring.py#L7)

#### 4. 面试官可能追问

- **追问：模型自称管理员可通过吗？** 答：不行，身份来自认证。
- **追问：工具返回成功就够吗？** 答：写操作还要核提交状态与副作用。

#### 5. 测试与证据

test_forged_confirmation_and_changed_target_cannot_bypass_action_binding 覆盖绑定。[tests/integration/test_goal_evaluation.py:L120](../../tests/integration/test_goal_evaluation.py#L120) 本轮未运行。

<a id="q141"></a>
### Q141：temperature、top_p、max_tokens、上下文窗口的实际影响？

#### 1. 标准答案

temperature改变分布尖锐度，top_p截取累计概率候选，max_tokens限制输出；上下文窗口限制总输入输出。采样参数不能保证正确，输出上限太低会截断，太高增预留。

对温度 T>0，可把采样概率写作 p(i)=softmax(z_i/T)；top_p 则保留累计概率达到阈值的最小候选集合，再归一化采样。二者都改变随机性，并不新增知识或权限。容量约束通常满足“输入+允许输出≤模型上下文限制”，供应商还可能有独立最大输出限制。max_tokens 是上限而非实耗；对收费准入，应先预留最坏输出成本，再凭可信 usage 结算。

#### 2. 面试口述版

我会把随机性和容量分开。temperature与top_p影响采样，较低温度更适合分类和结构化任务，但零温度不等于绝对可复现；max_tokens是输出上限，不是一定生成数量，上下文窗口还包含输入。项目不同节点显式温度和上限，Provider没有单独暴露top_p配置，不能说都可调。提高输出上限会增加保守费用预留，未必提高答案质量；太低则JSON可能被截断。验证需记录finish_reason和实际usage，并测完整任务，不应只比较回答长短。任何参数变化都要与模型版本和相同输入绑定。

#### 3. Adaptive-RAG实际实现

已实现temperature/max_tokens透传及完整预算；top_p配置未实现。[app/providers/deepseek.py:L51](../../app/providers/deepseek.py#L51) [app/providers/deepseek.py:L63](../../app/providers/deepseek.py#L63) [app/agents/nodes/generate.py:L121](../../app/agents/nodes/generate.py#L121)

#### 4. 面试官可能追问

- **追问：max_tokens等于实耗吗？** 答：不是，上限与usage分开。
- **追问：零温度绝对稳定吗？** 答：不能保证，服务实现与版本也影响。

#### 5. 测试与证据

test_structured_length_finish_is_rejected_without_retry 检查截断。[tests/unit/test_p2_json_reliability.py:L12](../../tests/unit/test_p2_json_reliability.py#L12) 参数收益未验证。

<a id="q142"></a>
### Q142：上下文里工具Schema和检索文档的排序如何影响结果？

#### 1. 标准答案

顺序影响可见性、位置利用、截断与缓存前缀；工具应按相关性与风险筛选，证据保留必要条件。通过位置扰动和同集对照检查，不把顺序当安全边界。

证据顺序的影响包括前后位置偏好、上下文被截断，以及相关材料之间的干扰。先按权限和相关性筛选，再保留问题所需的适用条件、例外与版本；多跳问题不能只取最高分的单一主题。工具目录也应保留必要参数说明，不能为了省 token 去掉枚举或风险描述。公平实验应固定证据集合，只改变顺序，分别检查引用、完整性和工具选择，而不是同时换检索器。

#### 2. 面试口述版

我会先减少无关内容，再调整顺序。工具目录过长会稀释选择，证据关键条件被裁掉则无法回答，单纯把某段放前面不是可靠保证。项目Planner按允许集合生成工具目录，普通检索重排后组装有限证据，生成只取前六块。工具与证据都是应用选择的，不由用户随意注入新的权限。要评估顺序，我会固定内容改变排列，检查工具选择、必要证据利用和token预算，并记录是否影响缓存。当前没有自动排序优化和位置鲁棒性基准，不能说已有最优布局；权限仍由后端决定，不靠“危险工具放最后”。

#### 3. Adaptive-RAG实际实现

已实现allowed目录过滤和有限证据组装，自动顺序优化未实现。[app/agents/nodes/planner.py:L44](../../app/agents/nodes/planner.py#L44) [app/agents/nodes/generate.py:L61](../../app/agents/nodes/generate.py#L61)

#### 4. 面试官可能追问

- **追问：危险工具放末尾安全了吗？** 答：不，必须授权与确认。
- **追问：证据相关性排序够吗？** 答：还要保证多目标与例外覆盖。

#### 5. 测试与证据

test_real_shaped_planner_extra_step_is_pruned_only_for_status_request 检查裁剪边界。[tests/unit/test_p2q_planner.py:L110](../../tests/unit/test_p2q_planner.py#L110) 排列实验未验证。

<a id="q143"></a>
### Q143：Prompt注入文档会不会覆盖系统指令，如何隔离？

#### 1. 标准答案

检索文档是数据，不应升级为指令。分隔和可信度标注、最小上下文、输出校验与后端授权共同防护；规则检测只覆盖明显模式，不能证明任意注入免疫。

直接注入来自用户输入，间接注入可能藏在检索网页、文档或工具返回中。工程上应保持消息角色由服务端构造，外部内容只进入数据区；再限制可调用工具、校验输出与资源归属，并对异常指令做检测。分隔符和正则只能降低部分风险，不构成形式化隔离。安全验收应观察是否泄露私有资料或执行未经授权的操作，不能只看模型是否口头拒绝。

#### 2. 面试口述版

文档里的“忽略前面规则”可能影响模型，所以不能只说系统提示优先就结束。应用要把检索内容明确作为不可信数据，减少无关材料，禁止它改变工具权限或业务事实，并在执行层校验。项目有不可信横幅和查询边界正则检测，生成与裁判提示都限制证据用途，但正则不能识别所有间接注入。更重要的是模型即使被诱导，工具仍需身份、owner和确认。我的验证会把注入放在正文、表格和工具结果里，检查是否发生越权和泄漏；目前不能宣称这些攻击全部已覆盖，也不能把外部内容写进高优先级规则。

#### 3. Adaptive-RAG实际实现

已实现detect_prompt_injection与不可信提示，通用注入免疫未实现。[app/guardrails/injection.py:L19](../../app/guardrails/injection.py#L19) [app/prompts/answer.py:L5](../../app/prompts/answer.py#L5) [app/prompts/faithfulness.py:L3](../../app/prompts/faithfulness.py#L3)

#### 4. 面试官可能追问

- **追问：正则通过就安全吗？** 答：不，间接与变体攻击仍可能存在。
- **追问：为何还需后端权限？** 答：Prompt不能约束数据库实际授权。

#### 5. 测试与证据

test_blocks_ignore_previous_instructions 覆盖明显模式。[tests/unit/test_guardrails.py:L9](../../tests/unit/test_guardrails.py#L9) 全变体覆盖未验证。

<a id="q144"></a>
### Q144：JSON结构化输出总是有效吗？失败、截断如何处理？

#### 1. 标准答案

JSON模式不保证完整、schema符合或语义正确。区分API失败、非法JSON、schema错误和finish_reason=length；有限提取修复后验证，不能用补括号掩盖截断或无限重试。

建议分别记录 transport_error、invalid_json、schema_error、truncated 与 business_validation_error。围栏或前缀提取适合恢复明确存在的 JSON 对象；字段缺失、类型错误或 length 终止则不能猜测补齐业务含义。允许重试时必须有次数、deadline 和逐次费用准入，并保留原失败。结构正确之后，还要核对枚举、实体绑定、Owner、确认与金额单位，不能把解析成功直接当业务成功。

#### 2. 面试口述版

我会把传输、格式、schema和事实四层分开。返回200可能是截断JSON，合法JSON可能缺字段或订单号错误。项目会剥离代码围栏、提取对象、Pydantic验证，并在结构化响应finish_reason为length时拒绝，即使表面JSON完整也不接受。失败后按节点走保守路径，不是无限让模型修复。输出上限要针对任务设计，修复增加请求也受付费门禁。测试应包括围栏、前缀文字、非法类型、截断与矛盾状态，保留原错误分类。格式恢复只能恢复可解析性，不能把缺失业务条件靠猜测补上，更不能据此开放危险工具执行。

#### 3. Adaptive-RAG实际实现

已实现extract_json_object/parse_model和截断拒绝；语义正确仍需业务检查。[app/providers/json_parser.py:L22](../../app/providers/json_parser.py#L22) [app/providers/json_parser.py:L46](../../app/providers/json_parser.py#L46) [app/providers/deepseek.py:L106](../../app/providers/deepseek.py#L106)

#### 4. 面试官可能追问

- **追问：补右括号可接受吗？** 答：不能掩盖缺字段或被截断语义。
- **追问：重试越多越好吗？** 答：成本和风险增加，需预算与上限。

#### 5. 测试与证据

test_json_parser_strips_fence 和 test_structured_length_finish_is_rejected_without_retry 覆盖两类。[tests/unit/test_tools_and_parser.py:L24](../../tests/unit/test_tools_and_parser.py#L24) [tests/unit/test_p2_json_reliability.py:L12](../../tests/unit/test_p2_json_reliability.py#L12) 本轮未运行。

<a id="q145"></a>
### Q145：DeepSeek thinking/non-thinking 模式对结构化输出和延迟有什么影响？

#### 1. 标准答案

思考模式可能增加内部推理、输出结构差异与延迟，是否有收益需按供应商模型版本实测；非思考也不保证JSON正确。分开记录模式、上限、finish和usage。

选型需要先确认具体模型和 API 支持的模式、推理内容字段与计费口径。复杂规划可能从额外推理获益，短分类或严格 JSON 也可能付出更长耗时而无稳定收益。应使用同一任务集、证据、输出约束及重试上限，比较完整率、截断率、延迟分布与费用。这里讨论机制与注明日期的历史配置，不把某次成功推导成当前供应商所有版本的保证。

#### 2. 面试口述版

我只在历史证据范围谈项目结果，不把过去模型行为当今天所有版本规律。二〇二六年十一月十四日真实验收为适配短JSON输出显式使用thinking disabled，普通Provider未配置时保持原请求格式。代码支持可选thinking字段，但没有成对的思考与非思考质量、延迟对照，所以不能声称关闭一定更好或更快多少。实践中要检查推理内容是否占额度、JSON出在哪个字段、输出是否截断，并用相同任务和预算比较。非思考仍会出格式或事实错误，schema和后端安全不应随模式关闭，也不能为演示通过删掉必要裁判节点。

#### 3. Adaptive-RAG实际实现

已实现可选thinking.type，历史Real Dev禁用；模式A/B未验证。[app/providers/deepseek.py:L71](../../app/providers/deepseek.py#L71) [app/config/settings.py:L40](../../app/config/settings.py#L40) [research/docs/agent_engineering_upgrade/deepseek_live_acceptance/DEEPSEEK_LIVE_ACCEPTANCE_REPORT.md:L11](../../research/docs/agent_engineering_upgrade/deepseek_live_acceptance/DEEPSEEK_LIVE_ACCEPTANCE_REPORT.md#L11)

#### 4. 面试官可能追问

- **追问：关闭思考等于不用推理吗？** 答：只是供应商模式，不代表任务无需推理。
- **追问：能直接换更大上限吗？** 答：会增加预留，要授权范围内验证。

#### 5. 测试与证据

test_provider_preserves_actual_model_and_finish_reason 检查返回元数据。[tests/unit/test_p2_json_reliability.py:L39](../../tests/unit/test_p2_json_reliability.py#L39) 本轮无模型调用。

<a id="q146"></a>
### Q146：如何做提示词版本化、A/B对照及回归测试？

#### 1. 标准答案

提示词纳入版本控制，记录模板、模型、参数与数据哈希。A/B只改目标变量，固定工具/环境，开发集调参后留出验收，保留失败与回滚版本。

最小版本单元不只有一段 system 文本，还包括模板变量、示例、输出 Schema、模型及其参数。离线 A/B 适合找机制问题；在线 A/B 还需要随机分组、租户隔离、成本上限与停止条件。对可写工具，不能把同一请求在两个实验分组重复真实执行。每轮保存代码提交和数据哈希，回滚要恢复兼容的配置组合，不能只回滚模板却继续使用不兼容 Schema。

#### 2. 面试口述版

Prompt变更也像代码变更，需要知道改了什么、在哪些问题上改善和退化。我会把模板放Git，记录代码commit、模型、参数与数据版本，用同一冻结问题做配对，不同时换Graph或embedding。项目已有独立Prompt模块、场景哈希和评测契约，但没有完整在线Prompt A/B平台。示例改动特别容易把测试答案泄露进去，因此开发与留出要隔离。回归不仅看流畅度，还看工具参数、拒答、数字与目标完成，失败结果不覆盖。通过离线后才考虑受控灰度，回滚要包含提示和模型配置，不能只记一张分数截图当证据。

#### 3. Adaptive-RAG实际实现

已有Prompt源码和dataset SHA，自动A/B发布平台未实现。[app/prompts/answer.py:L5](../../app/prompts/answer.py#L5) [eval/multiturn.py:L56](../../eval/multiturn.py#L56) [eval/contracts.py:L44](../../eval/contracts.py#L44)

#### 4. 面试官可能追问

- **追问：同分就等价吗？** 答：可能不同失败类型，要逐样本看退化。
- **追问：能反复调留出吗？** 答：会污染，需新未见集。

#### 5. 测试与证据

test_baseline_is_offline_dataset_snapshot 检查基线身份。[tests/unit/test_eval_contracts.py:L24](../../tests/unit/test_eval_contracts.py#L24) 在线A/B未实现。

<a id="q147"></a>
### Q147：如何通过减少无用工具Schema降低Token和延迟？

#### 1. 标准答案

按意图、实体与能力筛最小工具集合，保留必要备选和安全升级；压缩描述但不丢参数约束与风险。目录裁剪只是规划优化，执行仍用完整注册表授权校验。

目录筛选宜使用服务端能力、当前意图和业务实体，不能接受用户自报权限。筛掉无关工具后，仍需保留查询必要事实和澄清歧义的路径；过度裁剪会让模型缺少合法完成手段。评估至少同时报告目录 token、必要工具覆盖率、参数准确性和端到端目标完成。若只优化目录长度，可能少一次查询却多几次失败重试，最终更慢、更贵。

#### 2. 面试口述版

几百工具全放进去会浪费token，也可能让模型选到看似相近却不合适的操作。我会先按意图、实体和场景技能筛目录，保留必要备选，再让模型计划，执行时重新校验。项目Planner已有allowed集合和工具目录过滤，状态查询可裁掉不必要物流事件，但商品、物流等明确子目标不能误删。减少schema不一定线性降费用，缓存和重试也影响，所以需要同集比较工具准确率、必要调用和usage。当前不是动态工具向量搜索平台，不能夸大到自动管理任意规模目录；裁剪失误也可能提高缓存命中却降低任务完成。

#### 3. Adaptive-RAG实际实现

已实现_tool_catalog(allowed)、_allowed_tools与计划净化，动态工具搜索未实现。[app/agents/nodes/planner.py:L44](../../app/agents/nodes/planner.py#L44) [app/agents/nodes/planner.py:L160](../../app/agents/nodes/planner.py#L160) [app/agents/nodes/planner.py:L188](../../app/agents/nodes/planner.py#L188)

#### 4. 面试官可能追问

- **追问：裁剪可作为授权吗？** 答：不能，后端还要校验。
- **追问：少调用一定好吗？** 答：漏掉必要证据会降任务成功率。

#### 5. 测试与证据

test_status_only_skill_does_not_query_shipment_events 和 test_logistics_evidence_remains_available 检查取舍。[tests/unit/test_p2q_planner.py:L85](../../tests/unit/test_p2q_planner.py#L85) [tests/unit/test_p2q_planner.py:L102](../../tests/unit/test_p2q_planner.py#L102) 本轮未运行。

<a id="q148"></a>
### Q148：什么是KV Cache / prompt cache，为什么请求更短不一定更便宜？

#### 1. 标准答案

KV cache复用已计算注意力键值以减少解码重复；prompt cache复用相同前缀计算，命中规则和计价依供应商。更短请求可能破坏前缀命中、增输出或重试，不能只按字符判断费用。

两类缓存的收益要放在完整请求链中计算：输入缓存命中/未命中的计价、输出 token、重试与额外工具调用都可能变化。稳定系统前缀通常更利于前缀复用，但不能为了命中把用户私有内容错误共享。项目检索缓存存候选结果，供应商 prompt cache 复用模型计算，模型 KV 则是推理状态，三者的键、生命周期和隔离边界不同。费用保护应按可验证的保守费率准入，不依赖未承诺的缓存折扣。

#### 2. 面试口述版

我先区分模型内部KV和服务端前缀缓存。KV用于自回归生成时复用历史计算，prompt cache则可能跨请求复用相同前缀；两者不等于项目Redis检索缓存。请求更短未必更便宜，可能打破缓存前缀，或因为删掉schema和证据导致更多重试与更长输出。项目没有自管KV或供应商缓存控制器，预算按保守输入上界，历史费用估算也按未命中上界，不把缓存折扣当保证。我会记录实际usage、可得的命中字段与完整任务成本，现价需另查官方，不能用过去费率声称当前账单；内容压缩还必须保留业务条件。

#### 3. Adaptive-RAG实际实现

项目未实现KV/prompt cache管理；已有RedisRetrievalCache是检索结果缓存。[app/retrieval/cache.py:L59](../../app/retrieval/cache.py#L59) [app/providers/paid_budget.py:L76](../../app/providers/paid_budget.py#L76)

#### 4. 面试官可能追问

- **追问：Redis命中等于模型缓存吗？** 答：不是，缓存对象和层级不同。
- **追问：短请求总省钱吗？** 答：输出、重试与前缀命中可能抵消。

#### 5. 测试与证据

test_grant_net_fee_cap_released_only_by_trusted_settlement 检查费用依据。[tests/unit/test_budget_authorization.py:L66](../../tests/unit/test_budget_authorization.py#L66) 供应商缓存收益未验证。

<a id="q149"></a>
### Q149：什么是Token，它与中文字数/字符数的关系？

#### 1. 标准答案

Token是模型编码序列的单位，与字、字符和字节不一一对应；中文、英文、emoji与JSON开销不同。估算可用于准入，实际usage与供应商计费另核。

应明确四种单位：用户看到的字形、Unicode 码点、UTF-8 字节和 tokenizer token。它们之间没有固定比例；同一文字在不同分词器、版本或序列边界中也可能编码不同。切片的字符上限不能直接等价于模型 token 窗口。输入估算用于提前拒绝明显超限请求，可信 usage 用于事后成本统计，而累计预算是跨请求账本约束，三者解决不同问题。

#### 2. 面试口述版

我不会说一个中文固定等于一个token。分词器按词表把文本编码，中文、数字、英文、emoji和空白组合可能不同，消息结构也有额外开销。项目切片明确按字符，记忆有启发式估算，完整请求准入则用UTF-8字节加余量，两者都不是精确计费token。真正消耗看可信供应商usage，还要分输入和输出。面试中应同时说清单位、单次上下文限制与累计账本预算，不能把三者混用。最早1207实耗和8986预留正是不同统计口径，预留更大不等于供应商多扣；未知usage也不能自动记零。

#### 3. Adaptive-RAG实际实现

已实现字符切片、estimate_tokens启发式和保守请求界限，精确供应商tokenizer未实现。[app/retrieval/chunking.py:L14](../../app/retrieval/chunking.py#L14) [app/memory/budget.py:L28](../../app/memory/budget.py#L28) [app/providers/paid_budget.py:L76](../../app/providers/paid_budget.py#L76)

#### 4. 面试官可能追问

- **追问：emoji一个字符吗？** 答：显示字形、Unicode码点和token也可不同。
- **追问：估算可用于结算吗？** 答：不能，可信usage才可减少预留。

#### 5. 测试与证据

test_complete_serialized_input_and_output_reservation_checked_before_http 检查准入。[tests/unit/test_context_budget.py:L10](../../tests/unit/test_context_budget.py#L10) 精确tokenizer对照未验证。

<a id="q150"></a>
### Q150：为什么同一输入模型输出可能不同？怎么设计稳定回归？

#### 1. 标准答案

差异来自采样、并行数值计算、服务版本与上下文/工具状态变化。冻结输入、模型参数和环境，规则测试确定性，真实模型重复配对报告波动，不把零温度当严格保证。

回归应把“程序契约稳定”与“模型行为波动”分开。Schema、预算原子性和权限测试可用固定响应验证；自然语言回答则按必要事实、引用与目标评分，避免整段字符串匹配。真实模型比较使用相同样本的配对重复，并保存全部失败、模型标识、参数和环境。即使设 seed 或零温度，也不能假设远程服务升级、数值实现和动态批处理完全确定。

#### 2. 面试口述版

我会先确认“同一输入”是否真的一样：历史、工具状态、检索顺序和模型版本都可能变化。即便温度为零，供应商实现与并行计算也不一定绝对确定。项目单元测试用注入Provider或Offline fixture保证机制可复现，真实模型验收则是有限历史记录，没有重复统计。因此稳定回归要分层：纯函数精确断言，模型任务按事实和契约评分，固定数据与参数并重复配对，保留失败率与波动。不能为了稳定就只比整段字符串，也不能挑最好一次。缓存与状态应隔离，Gold不进Prompt，模型升级后重新建立基线。

#### 3. Adaptive-RAG实际实现

已有Offline与注入模型测试、场景哈希，真实模型重复统计未验证。[eval/memory_ablation.py:L50](../../eval/memory_ablation.py#L50) [eval/multiturn.py:L56](../../eval/multiturn.py#L56)

#### 4. 面试官可能追问

- **追问：字符串不同即失败吗？** 答：事实和目标等价可通过，需预定义规则。
- **追问：只报最好一次好吗？** 答：会选择偏差，应报告全部预设重复。

#### 5. 测试与证据

test_scripted_arm_exercises_node_prompts_with_no_paid_tokens 为确定fixture证据。[tests/integration/test_memory_ablation.py:L4](../../tests/integration/test_memory_ablation.py#L4) 真实方差未验证。

<a id="q151"></a>
### Q151：OpenAI兼容API与不同供应商的字段、流式协议可能有什么差异？

#### 1. 标准答案

兼容通常只覆盖部分接口：thinking、工具、JSON、usage、finish、错误体和SSE终止/压缩都可能不同。用契约测试验证具体版本，不能仅因路径相同就认为可无缝替换。

兼容性清单应覆盖角色、工具参数和 tool_call_id、JSON 约束、推理字段、流式 delta、usage、结束标记、错误体、限流与压缩。可用本地传输 fixture 对每种响应边界做契约测试，再进行独立授权的真实冒烟。密钥或端点格式相同只证明能构造请求，不证明业务能力、错误恢复和账本结算一致；缺失的可信费用证据必须保守处理。

#### 2. 面试口述版

我会把“兼容”拆成请求和响应契约。都叫chat/completions，不代表thinking字段、工具回合、JSON模式、usage和流结束完全一样。项目DeepSeek Provider有自己的payload与解析，usage结算还严格检查模型、finish和SSE完成；历史压缩解码差异就造成Provider成功而账本未结算。替换供应商时应先用本地协议fixture覆盖错误、截断、压缩、取消，再在明确授权下做有限真实验证。不能只看一次200就说兼容，更不能因某字段缺失就按零消费。业务事实、权限和幂等仍独立于供应商协议，不能随适配一起放松。

#### 3. Adaptive-RAG实际实现

已实现DeepSeek适配和UsageEvidence，通用多供应商认证矩阵未实现。[app/providers/deepseek.py:L63](../../app/providers/deepseek.py#L63) [app/providers/usage_settlement.py:L226](../../app/providers/usage_settlement.py#L226)

#### 4. 面试官可能追问

- **追问：200就兼容吗？** 答：还需正确字段和完整结束。
- **追问：缺usage怎么办？** 答：保守占用，不伪造结算。

#### 5. 测试与证据

test_provider_preserves_actual_model_and_finish_reason 与压缩测试覆盖契约。[tests/unit/test_p2_json_reliability.py:L39](../../tests/unit/test_p2_json_reliability.py#L39) [tests/unit/test_paid_budget_compression.py:L26](../../tests/unit/test_paid_budget_compression.py#L26) 本轮无HTTP。

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

<a id="q154"></a>
### Q154：如何分别评估检索、Rerank、生成及整个Agent任务？

#### 1. 标准答案

分层评估：粗召回必要证据覆盖，重排固定候选的排序，生成支持/完整/拒答，Agent工具轨迹与已提交业务目标。端到端失败须定位首次出错阶段，不能把局部高分当任务成功。

检索可看 Recall@K/Hit@K，重排在固定候选集上看 MRR/nDCG；生成看事实支持、引用正确与必要信息覆盖；Agent 则核对必要工具、参数、授权和已提交状态。条件评估能帮助归因，例如先提供 Gold 证据观察生成能力，但不能把这个上界当真实端到端结果。各层要共享样本标识，并标记未运行、依赖错误和安全拒绝。

#### 2. 面试口述版

我会先分层再汇总。检索问必要证据是否找齐，重排问给定候选能否前置正确材料，生成问事实有依据且目标答全没有，Agent还要检查工具参数、授权和最终状态。项目有检索指标、答案评分、轨迹和独立目标oracle，但它们不是同一分母。检索高分可能生成漏例外，回答正确也可能工具没执行。比较时固定数据和模型，记录每层输入输出及实际backend，避免把hash链路当真实语义收益。最终业务成功需要全部必要约束满足，成本时延另报，不能用平均LLM评分掩盖未执行或越权副作用。

#### 3. Adaptive-RAG实际实现

已实现metrics、score_answer、score_tools与score_goal，nDCG未实现。[eval/metrics.py:L21](../../eval/metrics.py#L21) [eval/answer_scoring.py:L261](../../eval/answer_scoring.py#L261) [eval/tool_scoring.py:L25](../../eval/tool_scoring.py#L25) [eval/goal_scoring.py:L7](../../eval/goal_scoring.py#L7)

#### 4. 面试官可能追问

- **追问：重排评估需重跑召回吗？** 答：隔离排序时固定候选，端到端再测全链。
- **追问：一个高分能代表全部吗？** 答：不能，各层标签与失败机制不同。

#### 5. 测试与证据

test_query_goal_uses_observed_tool_result_not_answer 检查独立目标。[tests/integration/test_goal_evaluation.py:L11](../../tests/integration/test_goal_evaluation.py#L11) 本轮未运行评测。

<a id="q155"></a>
### Q155：工具选择、参数正确性、执行成功率分别怎么算？

#### 1. 标准答案

工具选择衡量必要工具覆盖与额外调用，参数准确性匹配对象及字段，执行成功率按真正executed调用统计；拒绝与幂等回放单列。声明分母，不能把没调工具的成功率当100%。

例如任务要求查询订单 A 和商品 B，重复查两次 A 不能算覆盖了两项需求，需要预期调用与实际调用一对一匹配。参数比较可容许明确规定的数值等价，但对象 ID、Owner 和确认标识不能模糊匹配。执行成功率应是成功执行数/实际执行数；没有实际执行时应报告不适用，而非制造 100%。轨迹还要检查先后依赖、不必要调用以及等价合法路径。

#### 2. 面试口述版

我会把“选对”“传对”“执行成功”拆开。模型选了get_order但订单号错，选择可能对而参数错；参数对但下游失败，执行又不同。项目score_tools按必需工具计数和一对一参数匹配，避免重复查A满足本应查B；执行成功只统计executed，replayed和denied单列，没有执行时返回None。还会约束多余调用与允许路径。这个细节很重要，用户不需工具时正确拒绝不能算执行失败，但需要工具却没执行也不能算成功。最后必须看实际观察与业务目标，回答里说调用过不算证据，也不应随意删失败调用改善分母。

#### 3. Adaptive-RAG实际实现

已实现score_tools的一对一匹配、额外调用、denied/replayed区分；非仅工具名字符串匹配。[eval/tool_scoring.py:L25](../../eval/tool_scoring.py#L25) [eval/contracts.py:L12](../../eval/contracts.py#L12)

#### 4. 面试官可能追问

- **追问：重复A能满足B吗？** 答：不能，一对一参数覆盖避免此漏洞。
- **追问：无executed为何None？** 答：表示指标不适用，不伪造100%。

#### 5. 测试与证据

test_contract_preserves_actual_argument_and_equivalent_paths 检查契约。[tests/unit/test_eval_contracts.py:L15](../../tests/unit/test_eval_contracts.py#L15) 指标实现可逐行复核，本轮未运行。

<a id="q156"></a>
### Q156：Recall@K、Precision@K、Hit@K、MRR、nDCG的差别？

#### 1. 标准答案

Recall看找齐比例，Precision看返回中相关比例，Hit看至少一条，MRR平均首个相关倒数排名，nDCG按分级相关性与位置折损。声明去重、K、空Gold和评测单位。

对去重后的前 K 项集合 S 和相关集合 G，Recall=|S∩G|/|G|，Precision 常用 |S∩G|/K；若不足 K 项，也有人用实际返回长度，必须声明。Hit 只看交集是否非空，MRR 看首个相关位置的倒数，nDCG 则以 DCG/理想 DCG 比较分级相关排序。项目 Precision 用实际切片长度作分母，MRR 扫描完整给定列表，函数不自动去重；空 Gold 的 Recall 返回 0，这些与其他实现的约定可能不同。

#### 2. 面试口述版

有三条必要证据只找到一条，Hit是一而Recall只有三分之一；返回很多无关内容又会拉低Precision。MRR关心第一次命中多早，无法评价后续证据顺序，nDCG适合分级相关性。项目函数有具体边界：precision分母是实际返回长度而非固定K，recall直接数列表命中未去重，空Gold返回零，mrr扫描完整列表不是MRR@K；nDCG未实现。我会在教学和项目现状间分清，调用前建议去重，无答案另列。不能把这些数字混合横比，尤其文档标签与chunk标签不同，更不能重复ID抬高召回后说效果更好。

#### 3. Adaptive-RAG实际实现

已实现precision/recall/hit/mrr，nDCG未实现；原函数无检索去重。[eval/metrics.py:L14](../../eval/metrics.py#L14) [eval/metrics.py:L21](../../eval/metrics.py#L21) [eval/metrics.py:L31](../../eval/metrics.py#L31)

#### 4. 面试官可能追问

- **追问：K大于返回数怎么算Precision？** 答：当前除实际top长度，需明确区别于固定K定义。
- **追问：空Gold如何评？** 答：当前Recall为0，建议无答案拒答另列，不能说代码已改。

#### 5. 测试与证据

test_precision_at_k_when_k_exceeds_length 与 test_mrr_second_position 检查边界。[tests/unit/test_metrics.py:L65](../../tests/unit/test_metrics.py#L65) [tests/unit/test_metrics.py:L100](../../tests/unit/test_metrics.py#L100) 本轮未运行。

<a id="q157"></a>
### Q157：为什么要有无答案、歧义、越权、工具失败、冲突政策样本？

#### 1. 标准答案

只测正常可回答样本会奖励乱答。无答案、歧义、越权、工具失败和冲突政策分别检验拒答、澄清、授权、故障处理与版本推理，标签及成功动作要预定义。

例如越权订单的成功目标应是拒绝且无数据泄露；无确认的取消请求应提出确认并保持订单不变；缺少政策应承认资料不足而非编造。歧义样本要有可接受澄清，冲突政策要注明版本、适用时间和优先规则。测试集还应按风险分层报告，避免大量简单正常样本掩盖少数高风险失败。

#### 2. 面试口述版

这些样本是检验系统边界，不是额外装饰。没有资料时继续回答会幻觉，歧义时猜订单会误操作，越权时查到别人数据即使答案正确也失败，工具故障应承认不可用，冲突政策要保留不确定。项目已有确认、owner、无证据和故障测试，但不能说所有类别都覆盖完整。构建评测时应为每类写预期动作和禁止副作用，区分正确拒答与基础设施ERROR。若只看正常问题平均分，模型可能通过更积极乱答获得高分。还要让Gold遵守当前用户权限，不能把越权资料当“应该找到”的证据。

#### 3. Adaptive-RAG实际实现

已实现部分边界回归与PASS/FAIL/ERROR/NOT_RUN契约；完整冲突政策集未验证。[eval/contracts.py:L44](../../eval/contracts.py#L44) [app/agents/nodes/faithfulness.py:L94](../../app/agents/nodes/faithfulness.py#L94) [app/retrieval/private.py:L126](../../app/retrieval/private.py#L126)

#### 4. 面试官可能追问

- **追问：拒绝越权会拉低工具成功吗？** 答：应按场景算正确拒绝，调用指标单列。
- **追问：冲突样本Gold是什么？** 答：来源与应说明的冲突，而非硬选一个版本。

#### 5. 测试与证据

test_no_confirmation_and_cross_user_session_do_not_write 检查无副作用。[tests/integration/test_goal_evaluation.py:L63](../../tests/integration/test_goal_evaluation.py#L63) 全类别覆盖未验证。

<a id="q158"></a>
### Q158：如何做BM25/Dense/RRF/Rerank的消融？

#### 1. 标准答案

固定Query、语料、模型、分词、K、改写及缓存，依次比较BM25、Dense、RRF、RRF+Rerank；评价候选与最终输出，记录真实backend和资源，不能让一组额外预算。

消融要说明删掉的是哪个组件、其他条件如何固定。若只有 Rerank 组返回更多候选或使用不同语料，差值就无法归因。既可固定总候选预算比较召回组合，也可在同一候选集上仅切换重排；两种问题需分开。Dense 实际若降级为 hash，实验标签必须写清，不能把离线演示分数说成真实 Embedding 的效果。

#### 2. 面试口述版

我会用同一语料快照和冻结问题逐步加组件，而不是四组各自调到最优再横比。先看BM25与Dense各自漏什么，再看RRF有没有保住必要证据，最后固定融合候选检查重排。项目运行器提供相关入口，但必须记录是否真实embedding和Cross-Encoder，hash或lexical只验证机制。改写、K、缓存与权限也要一致，避免收益来自更多查询或热缓存。质量之外看延迟和token，允许某类问题退化并报告原因。结果按问题配对、保留失败，不拿旧合成数据当线上成功率，也不能认为增加组件一定单调改善。

#### 3. Adaptive-RAG实际实现

已实现eval_retrieval的多路入口，真实模型全面消融未验证。[eval/runner.py:L166](../../eval/runner.py#L166) [app/retrieval/fusion.py:L16](../../app/retrieval/fusion.py#L16) [app/retrieval/reranker.py:L15](../../app/retrieval/reranker.py#L15)

#### 4. 面试官可能追问

- **追问：RRF更好就一定因Dense吗？** 答：可能来自预算或候选变化，需控制变量。
- **追问：如何隔离重排作用？** 答：固定输入候选比较最终必要证据位置。

#### 5. 测试与证据

test_rrf_prefers_docs_high_in_both_lists 为机制测试。[tests/unit/test_rrf.py:L18](../../tests/unit/test_rrf.py#L18) 本轮未做实验。

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

<a id="q160"></a>
### Q160：LLM-as-a-Judge有哪些偏差？如何结合人工和规则验证？

#### 1. 标准答案

LLM裁判有同源、位置、长度、风格和自洽偏差，也会受注入与证据缺失影响。用冻结rubric、盲评/换序、人工双标和精确规则校准，故障单列，不能多数投票替代事实。

人工验证应先定义支持、矛盾、证据不足和漏答的 rubric，再抽取正常、拒答及争议样本双人标注；分歧仲裁用于校准裁判。精确数值、工具参数、权限和数据库提交优先使用程序或独立事实源核对。随机换序、匿名化模型名可减轻部分偏差，但同源模型和同一错误证据仍可能共同犯错，多个裁判一致不等于事实成立。

#### 2. 面试口述版

我会把LLM Judge当有噪声的测量器，而不是法官真理。它可能偏爱长答案、熟悉措辞或自己的模型，也可能和被测模型共享同一错误。项目Judge有结构和错误分类，但没有全量人工校准一致率。金额、状态和提交结果应优先用规则与独立环境，语义支持由Judge辅助，争议人工看来源。评测时固定rubric、隐藏系统身份、打乱答案顺序，记录裁判模型和故障，不能把非法JSON当不支持或把API错误剔除。多个同源裁判一致也可能共同错，尤其政策例外与否定，应有专门人审反例。

#### 3. Adaptive-RAG实际实现

已实现FaithfulnessChecker和独立goal/answer规则，通用裁判校准平台未实现。[app/guardrails/hallucination.py:L49](../../app/guardrails/hallucination.py#L49) [eval/goal_scoring.py:L7](../../eval/goal_scoring.py#L7) [eval/answer_scoring.py:L261](../../eval/answer_scoring.py#L261)

#### 4. 面试官可能追问

- **追问：多裁判一致就可靠吗？** 答：共同训练偏差可能相关，仍需独立证据。
- **追问：Judge错误算答案错吗？** 答：分开标故障，质量不能据此定论。

#### 5. 测试与证据

test_judge_distinguishes_invalid_output_from_api_error 检查分离。[tests/unit/test_p2_json_reliability.py:L66](../../tests/unit/test_p2_json_reliability.py#L66) 人工一致率未验证。

<a id="q161"></a>
### Q161：评测集主要用LLM生成，怎么保证质量及防泄漏？

#### 1. 标准答案

LLM可生成候选问题但Gold需核对来源、可回答性与必要证据；检测模板重复，按来源族切分，冻结哈希，留出集不参与调参。合成与真实来源分层报告。

生成器可从冻结文档提出候选，审核者需独立确认问题有无答案、Gold 证据是否足够，以及是否存在其他合法答案。防泄漏不仅是随机切行，还要按文档族、模板与近重复语义切分，防止同一政策改写同时进入开发和测试集。若不知道供应商训练数据，不能宣称彻底排除预训练污染，只能说明本地调参与留出隔离做到了哪一层。

#### 2. 面试口述版

LLM出题效率高，但可能只出它自己容易回答的表达，答案也会和裁判共享错误。我会把它当候选生成器，人再核原文、编号、条件和无答案标签，去掉无来源事实。开发与留出按来源或模板族切分，不能把同题改写分别放两边。项目现有数据和历史研究里有合成/Offline资料，应明确标签，不声称来自大规模用户日志。Gold不进入服务、Prompt或记忆，哈希冻结后保留失败；发现badcase可加回归集，但新的留出需要未见资料。指标还要按来源分别展示，避免合成题多导致平均分掩盖真实难例。

#### 3. Adaptive-RAG实际实现

已有场景SHA和Gold不传服务约束；完整人工双标生产集未实现。[eval/multiturn.py:L56](../../eval/multiturn.py#L56) [eval/multiturn.py:L76](../../eval/multiturn.py#L76) [eval/memory_ablation.py:L265](../../eval/memory_ablation.py#L265)

#### 4. 面试官可能追问

- **追问：LLM生成答案可直接当Gold吗？** 答：不可，必须核来源和条件。
- **追问：去重只看字符串够吗？** 答：不够，还要模板、语义和文档族。

#### 5. 测试与证据

test_baseline_is_offline_dataset_snapshot 检查来源身份。[tests/unit/test_eval_contracts.py:L24](../../tests/unit/test_eval_contracts.py#L24) 真实流量代表性未验证。

<a id="q162"></a>
### Q162：每次改Prompt/Graph如何跑离线回归与E2E？

#### 1. 标准答案

先做变更影响分析与局部确定测试，再跑冻结离线任务、故障/安全和适当集成；真实E2E需明确模式与授权，保留数据/代码/结果，不能用Mock冒充真实。

变更到检索时，先验证切片、权限与排序，再观察最终引用；变更 Planner 时，先检查工具目录、参数和必需子目标，再跑 HTTP/SSE 与确认链路。固定失败用例应加入回归，不能改 Gold 迎合新输出。发布门禁应包括安全和幂等不退化，模型真实验收与 Mock/Offline 单独记录；文档整理本身不需要启动这些服务。

#### 2. 面试口述版

我会根据改动挑有意义的回归，而不是每次无条件启动所有服务。Prompt改动先查结构和固定样本，Graph改动查路径、状态与必要工具，然后跑冻结离线任务和关键失败边界。项目有unit、隔离业务环境和真实DeepSeek历史验收，三者证据强度不同；MockTransport只证明协议，Offline只证明机制。真实E2E涉及付费与服务，必须在授权范围内，不能为文档验证重新消费。结果记录commit、模型、数据哈希与NOT_RUN，不把历史947或54项说成本轮。上线还应保留回滚配置，但当前没有自动完整发布流水线。

#### 3. Adaptive-RAG实际实现

已有分层测试与eval runner，自动端到端CI发布平台未实现。[eval/runner.py:L566](../../eval/runner.py#L566) [eval/multiturn.py:L67](../../eval/multiturn.py#L67) [eval/contracts.py:L44](../../eval/contracts.py#L44)

#### 4. 面试官可能追问

- **追问：Mock通过可称真实E2E吗？** 答：不能，需标Provider和传输模式。
- **追问：哪些失败必回归？** 答：权限、确认、幂等、截断与证据不足等受影响边界。

#### 5. 测试与证据

test_malformed_case_and_missing_confirmation_cannot_be_success 检查回归契约。[tests/integration/test_multiturn_evaluation.py:L19](../../tests/integration/test_multiturn_evaluation.py#L19) 本轮只文档检查。

<a id="q163"></a>
### Q163：如何设置重试和温度，保证版本间公平？

#### 1. 标准答案

版本比较固定温度、上限、重试策略、模型与环境，逻辑调用与HTTP尝试分开。失败和重试消耗计入结果；重复配对报告分布，不能只给新版本更多机会。

温度为零只能减少采样波动，不能消除模型版本和远程实现变化。应把一次逻辑调用与多次 HTTP attempt 分开，所有尝试的时间和费用都计入；各版本使用相同重试上限、总 deadline 和预算。对相同样本做配对重复，报告完整结果及波动，不能旧版本只试一次、新版本挑最好一次。

#### 2. 面试口述版

我会把重试视为系统行为的一部分。新版本多重试两次，成功率提高但成本和长尾增加，不能和旧版单次结果直接比。温度、模型、Prompt、工具与初始状态都固定，真实服务仍应重复配对，不认为零温度绝对稳定。项目有指数退避和明确非重试错误，真实开发模式也曾限制每次调用只尝试一次；历史不同配置不能混比。预算按HTTP尝试计数，usage未知不能记零。报告要保留失败和总尝试，而不是只展示最终成功答案；确定性fixture用于机制，真实模型波动另测，不把两种结果混成提升。

#### 3. Adaptive-RAG实际实现

已实现with_exponential_backoff与llm_max_retries，真实重复公平对照未验证。[app/core/retry.py:L32](../../app/core/retry.py#L32) [app/config/settings.py:L42](../../app/config/settings.py#L42) [app/providers/deepseek.py:L121](../../app/providers/deepseek.py#L121)

#### 4. 面试官可能追问

- **追问：同用户轮数即同成本吗？** 答：不，节点数和HTTP重试可能不同。
- **追问：API故障可剔除吗？** 答：需预定义并单列，不能只删不利样本。

#### 5. 测试与证据

test_retries_retryable_then_succeeds 与 test_does_not_retry_auth_errors 检查边界。[tests/unit/test_retry.py:L10](../../tests/unit/test_retry.py#L10) [tests/unit/test_retry.py:L27](../../tests/unit/test_retry.py#L27) 本轮未运行。

<a id="q164"></a>
### Q164：质量、P95延迟、Tokens、费用如何做多目标权衡？

#### 1. 标准答案

先设不可违反的安全/正确性约束，再在质量、P95、token和费用的Pareto候选中选方案。按业务类别与风险加权，报告分布和退化，不能平均分抵消越权。

可先规定不得越权、不得误写与最低任务正确性，再在可行集合中寻找质量不降且成本/长尾更好的 Pareto 方案。P95 要明确计时范围并包含失败和排队；均值不能替代长尾。对高风险取消与低风险问候可采用不同策略，但路由本身要验证。若用综合评分，权重和阈值应事先确定，不能看到结果后调权重美化提升。

#### 2. 面试口述版

我先把安全与必要事实作为门槛，不用省钱抵消越权或错误取消。满足约束后再比较质量、P95、usage和费用，寻找适合业务的取舍：简单查询可少工具，复合问题不能为了延迟删证据。项目有延迟和usage字段、预算门禁，但没有经过生产流量验证的多目标调度器。历史四项业务耗时是有限场景，不是SLA或P95。实验应固定数据与并发，报告冷暖缓存、失败和尾部，费用区分估算与账本占用。若缓存命中提高却任务完整性下降，就不是优化成功，必须回到子目标和事实检查。

#### 3. Adaptive-RAG实际实现

已有latency、TokenUsage与费用准入，多目标自动优化未实现。[app/agents/nodes/retrieval.py:L48](../../app/agents/nodes/retrieval.py#L48) [app/providers/deepseek.py:L108](../../app/providers/deepseek.py#L108) [app/providers/paid_budget.py:L617](../../app/providers/paid_budget.py#L617)

#### 4. 面试官可能追问

- **追问：质量与成本如何合成一分？** 答：可业务加权，但先设安全硬约束并公开权重。
- **追问：一次耗时能叫P95吗？** 答：不能，需要足够同口径样本分布。

#### 5. 测试与证据

test_product_price_goal_does_not_accept_name_only_answer 约束完整性。[tests/unit/test_p2s_goal_review.py:L55](../../tests/unit/test_p2s_goal_review.py#L55) 生产Pareto曲线未验证。

<a id="q165"></a>
### Q165：线上badcase如何归因到检索、规划、工具、生成或数据？

#### 1. 标准答案

保留脱敏请求、版本、阶段结果和独立业务状态，定位数据/权限、召回、规划、执行、组装和生成首次偏离点；允许多因，修复后加回归，不靠猜模型。

可采用反事实定位：给生成器正确证据看是否仍错，给执行器合法固定计划看工具是否正常，并核对数据库是否已有错误或权限阻断。需要沿同一 Trace 对齐节点输入摘要、工具参数、返回状态和最终回答；记录应脱敏且避免复制完整私有文档。根因可能同时包含召回漏证据与生成过度推断，应分别修复并保留原失败。

#### 2. 面试口述版

我会从可观察证据还原目标，不先怪模型。先核用户身份和数据，再看路由计划是否包含必要工具、参数是否正确、工具为何拒绝或失败、事务是否提交，最后查证据进入Prompt与答案是否表达。项目有节点Trace、工具执行记录和独立评分，但通用Trace刻意不存原文与参数，要用受控证据，不能为调试泄密。一次失败可能多因，例如工具没查又生成编金额，应分别修。badcase加入开发回归并保留原失败，留出集避免污染。当前没有线上真实用户采样平台，所以只能讲机制和历史案例，不能虚构生产规模。

#### 3. Adaptive-RAG实际实现

已实现tracing、record_tool与独立目标评分，线上自动归因平台未实现。[app/observability/tracing.py:L61](../../app/observability/tracing.py#L61) [app/tools/base.py:L73](../../app/tools/base.py#L73) [eval/goal_scoring.py:L7](../../eval/goal_scoring.py#L7)

#### 4. 面试官可能追问

- **追问：Trace没参数怎么办？** 答：用授权受控证据核对，不放宽通用日志隐私。
- **追问：修一次就删badcase吗？** 答：保留失败和回归，避免重复退化。

#### 5. 测试与证据

test_error_records_type_not_exception_content 检查隐私。[tests/unit/test_tracing.py:L78](../../tests/unit/test_tracing.py#L78) 线上采样规模未验证。

<a id="q166"></a>
### Q166：模型升级如何做shadow / canary / rollback？

#### 1. 标准答案

Shadow只观察不产生真实副作用，Canary限定流量/租户与预算，监控质量、安全和长尾；回滚模型、Prompt、Graph和索引契约，避免重复执行写工具。

Shadow 输出不返回给用户，也不执行写工具；只读副本仍要计入模型费用和隐私范围。Canary 才把少量真实流量交给新版本，需要事先定义错误率、拒答、安全、成本和长尾停止阈值。回滚要考虑已产生的业务副作用、Schema 和索引兼容性，不能指望切回模型撤销订单取消。项目后台 Experience Shadow 也不等于通用模型发布平台。

#### 2. 面试口述版

模型升级不能只改名字后全量开放。先冻结协议和评测，在shadow对相同输入比较，但影子写操作必须禁用或放隔离环境，不能为对照再取消一次订单。通过后按租户或流量小范围canary，设置费用、失败和质量止损，再保留旧配置回滚。项目有可配置Provider、Offline/Real模式与预算，但没有通用模型shadow/canary控制平台；经验模块的shadow也不能当模型灰度证据。回滚要考虑embedding索引空间、工具schema和会话兼容，不能只切API地址。当前真实模型升级收益和流量级发布都未测，方案应明确标成设计。

#### 3. Adaptive-RAG实际实现

项目未实现通用模型shadow/canary；已有Provider配置与预算可作基础。[app/providers/deepseek.py:L29](../../app/providers/deepseek.py#L29) [app/providers/embeddings.py:L213](../../app/providers/embeddings.py#L213) [app/providers/paid_budget.py:L426](../../app/providers/paid_budget.py#L426)

#### 4. 面试官可能追问

- **追问：影子能执行写工具吗？** 答：不能对真实业务重复副作用，需隔离/只观察。
- **追问：回滚只换模型名吗？** 答：还需Prompt、协议和索引版本相容。

#### 5. 测试与证据

test_no_confirmation_and_cross_user_session_do_not_write 为安全边界测试。[tests/integration/test_goal_evaluation.py:L63](../../tests/integration/test_goal_evaluation.py#L63) 模型灰度平台未实现。

<a id="q167"></a>
### Q167：Faithfulness、citation correctness、answer completeness如何人工标注？

#### 1. 标准答案

以原子声明标注支持/不支持/无法判断，引用正确性检查该引用是否支持对应声明，完整性检查全部必要目标。规定例外、数字和部分回答标准，双标仲裁并记录来源。

可以逐句拆成可核对声明，如“可退款”“超过七天仍可处理”“需质量证明”分别核证据。Faithfulness 检查所有事实是否由给定证据支持；citation correctness 检查该编号是否支持其所挂声明；completeness 检查用户所需的金额、条件或多个子目标是否全部覆盖。不同概念不能用单一分数代替，证据不足应与明确矛盾分别标注，并记录标注依据和分歧。

#### 2. 面试口述版

我会先让标注员看到问题、授权证据与明确rubric，把答案拆成可核查声明。Faithfulness看事实是否有依据，citation correctness看指定引用是否支持它，completeness看用户要求是否全覆盖，三者不能混。说“订单已支付”有证据，但漏商品和金额，可能忠实却不完整；引到相关文档也未必支持具体例外。项目已有支持状态、引用ID过滤和目标coverage，但没有全量人工双标数据与一致率。我会让两人独立标，争议回原文仲裁，保留无法判断；不能强制所有样本二选一，也不能让Judge输出直接成为人工Gold。

#### 3. Adaptive-RAG实际实现

部分实现三类机制，完整人工标注平台未实现。[app/guardrails/hallucination.py:L16](../../app/guardrails/hallucination.py#L16) [app/agents/nodes/generate.py:L150](../../app/agents/nodes/generate.py#L150) [eval/answer_scoring.py:L261](../../eval/answer_scoring.py#L261)

#### 4. 面试官可能追问

- **追问：部分答对如何标？** 答：逐目标和声明标注，不能整体一票通过。
- **追问：无引用但事实正确呢？** 答：事实支持与引用覆盖分别记录。

#### 5. 测试与证据

test_product_price_goal_does_not_accept_name_only_answer 检查漏答。[tests/unit/test_p2s_goal_review.py:L55](../../tests/unit/test_p2s_goal_review.py#L55) 双标一致率未验证。

<a id="q168"></a>
### Q168：什么时候评估“没有成功调用工具”，什么时候算“正确拒答”？

#### 1. 标准答案

按任务预期判断：必要工具缺失是失败；无权限、无确认或无资料而正确拒绝可能成功。denied、executed、replayed与未调用分开，用户安全目标和工具成功率各有分母。

应先为任务定义可接受终态。问不存在订单，正确工具返回不存在且回答不编造属于成功；查询存在订单却跳过必要工具通常失败。越权或未确认写操作应验证拒绝且数据库未变，而非只检查拒绝措辞。缺少授权与依赖故障也应区分，不能把系统坏了导致的无动作统一包装成安全成功。

#### 2. 面试口述版

我会先问场景应该做什么，不把“没调用工具”一律判坏。用户要求查已授权订单却没有调用，是缺必要证据；越权取消被拒绝且数据库不变，反而是正确行为；幂等回放也不应算新的执行。项目评测区分denied、executed和replayed，执行成功率没有实际执行时返回None，任务目标另由独立环境检查。正确拒绝还要看理由和下一步，不能遇到任何困难都拒绝。确认缺失、目标歧义和依赖故障也分别记录，不能把ERROR包装成安全成功，更不能因为回答说查过就给工具分。

#### 3. Adaptive-RAG实际实现

已实现工具状态与独立oracle，通用所有场景拒绝rubric仍需数据标注。[eval/contracts.py:L12](../../eval/contracts.py#L12) [eval/tool_scoring.py:L25](../../eval/tool_scoring.py#L25) [eval/goal_scoring.py:L7](../../eval/goal_scoring.py#L7)

#### 4. 面试官可能追问

- **追问：无执行能记100%吗？** 答：当前不适用为None，不伪造。
- **追问：拒绝后仍写库算成功吗？** 答：不算，副作用必须独立核验。

#### 5. 测试与证据

test_no_confirmation_and_cross_user_session_do_not_write 检查拒绝无写入。[tests/integration/test_goal_evaluation.py:L63](../../tests/integration/test_goal_evaluation.py#L63) 本轮未运行。

<a id="q169"></a>
### Q169：统计样本量太小时为什么不能宣称显著提升？

#### 1. 标准答案

小样本波动与选择偏差大，单次差值不能证明显著或可推广。预定义样本、重复与配对分析，报告区间、效果量和失败分布；统计显著也不等于业务重要。

对于独立二项成功率，近似标准误随 sqrt(p(1-p)/n) 下降，小样本常需更合适的精确或 Wilson 区间；同一问题的多轮和改写并非完全独立。版本比较宜使用配对分析或按会话/来源簇 bootstrap，预先定义主指标和停止规则。有限验收能证明某些具体场景走通，不能外推线上成功率或声称因果提升。

#### 2. 面试口述版

四个业务场景通过能说明这四个有限条件，不足以宣称线上接近百分之百。样本少时一两个成功就会让比例大变，反复挑问题或挑最好一次又会放大偏差。项目真实DeepSeek验收二十次HTTP覆盖四项业务，HITL没跑；HTTP数也不是独立业务样本。我要先冻结问题和比较方案，用逐问题配对与重复估计波动，报告区间和具体失败，再判断收益是否具有业务价值。合成与真实来源分开，不能混起来扩大分母。当前没有足够生产样本或显著性研究，因此不能把历史小样本写成普遍提升或SLA。

#### 3. Adaptive-RAG实际实现

已有有限真实报告与离线场景，生产统计显著性未验证。[research/docs/agent_engineering_upgrade/deepseek_business_acceptance/REPORT.zh-CN.md:L9](../../research/docs/agent_engineering_upgrade/deepseek_business_acceptance/REPORT.zh-CN.md#L9) [eval/multiturn.py:L56](../../eval/multiturn.py#L56)

#### 4. 面试官可能追问

- **追问：20HTTP等于20独立样本吗？** 答：不是，多个节点属于同一任务且相关。
- **追问：显著就值得上线吗？** 答：还要效果量、风险、成本与退化。

#### 5. 测试与证据

test_baseline_is_offline_dataset_snapshot 检查证据模式。[tests/unit/test_eval_contracts.py:L24](../../tests/unit/test_eval_contracts.py#L24) 样本量/置信区间实证未验证。

<a id="q170"></a>
### Q170：如何追踪每一轮评测使用的模型、文档版本和代码commit？

#### 1. 标准答案

每轮记录代码commit、数据哈希、模型返回ID、参数、Prompt与索引/文档revision、工具版本和执行模式，产物只追加。区分配置模型与实际返回模型，不以日期目录代替完整血缘。

建议建立 run_id→代码/配置/数据→每个样本→每个 Trace/HTTP attempt 的关联。保留供应商实际返回模型名及服务端配置模型名，文档记录 canonical ID、revision 和内容哈希；Prompt 与工具 Schema 也要可追溯。不要把认证令牌、密钥或未经脱敏文本写进版本清单；模型 usage token 数量则应记录。目录时间戳只能帮助定位，不能替代内容身份和完整的结果来源。

#### 2. 面试口述版

评测结果要能回答“这一分是哪套系统算出来的”。我会记录代码commit、数据哈希、实际模型、温度与重试、Prompt版本、文档和embedding契约，以及Offline、Mock或Real模式。项目多轮加载计算数据SHA，结果有schema与model_evaluation，Memory消融还写git_head；Provider保留实际model和finish。覆盖仍不完整，例如通用索引模型版本登记与自动发布血缘没实现。不能凭目录日期或模型配置名就称可复现，也不能覆盖旧结果。文档写历史947测试时应连到当时报告，而不是说当前代码已重新跑过。

#### 3. Adaptive-RAG实际实现

已实现dataset SHA、git_head记录和实际model解析；统一索引/Prompt血缘平台未实现。[eval/multiturn.py:L56](../../eval/multiturn.py#L56) [eval/memory_ablation.py:L278](../../eval/memory_ablation.py#L278) [app/providers/deepseek.py:L114](../../app/providers/deepseek.py#L114)

#### 4. 面试官可能追问

- **追问：配置模型与返回不同怎么办？** 答：记录并核对差异，不能静默用配置填证据。
- **追问：只留分数截图够吗？** 答：不够，缺数据与版本无法复核。

#### 5. 测试与证据

test_provider_preserves_actual_model_and_finish_reason 检查实际返回。[tests/unit/test_p2_json_reliability.py:L39](../../tests/unit/test_p2_json_reliability.py#L39) 完整血缘自动化未验证。

<a id="q171"></a>
### Q171：高风险操作的评测为什么不能只看LLM评分？

#### 1. 标准答案

高风险操作需可信授权、确认绑定、幂等、事务提交和禁止副作用的独立验证。LLM评分不能证明数据库状态，更不能识别所有跨用户写入；语言质量只是辅助。

模型可能说“取消成功”而事务实际回滚，也可能语言符合预期却修改了另一个用户订单。因此评测要独立读取提交后的目标对象，验证状态变化、金额和禁止修改的对象；同时检查重复确认不会再写。安全拒绝要验证零副作用，未确认提案要验证只是 pending。LLM 可辅助评价解释质量，不能担任授权人或充当数据库事实源。

#### 2. 面试口述版

取消、退款这类操作的成功不能靠Judge说“回答很好”。模型可能说已取消，事务却未提交，也可能取消错订单，甚至重复产生退款。项目目标评估独立看提交后状态、审计与禁止变更，确认还绑定用户、会话和目标，工具轨迹只是其中一层。测试要覆盖伪造确认、重复请求、跨用户和未提交，不能只查最终一句话。真实DeepSeek历史HITL是NOT_RUN，已有单元和隔离集成测试不能改写这个事实。上线前还需受控真实验证和业务审计；我不会用20次模型响应成功替代危险操作端到端成功。

#### 3. Adaptive-RAG实际实现

已实现独立score_goal及确认/事务测试；真实HITL验收尚未运行。[eval/goal_scoring.py:L7](../../eval/goal_scoring.py#L7) [app/services/chat_service.py:L272](../../app/services/chat_service.py#L272) [research/docs/agent_engineering_upgrade/deepseek_business_acceptance/REPORT.zh-CN.md:L15](../../research/docs/agent_engineering_upgrade/deepseek_business_acceptance/REPORT.zh-CN.md#L15)

#### 4. 面试官可能追问

- **追问：事务内看到改了够吗？** 答：不够，独立观察确认提交。
- **追问：Judge可批准退款吗？** 答：不能替代可信审批与业务规则。

#### 5. 测试与证据

test_uncommitted_write_cannot_satisfy_goal 与 test_forged_confirmation_and_changed_target_cannot_bypass_action_binding 覆盖关键边界。[tests/integration/test_goal_evaluation.py:L157](../../tests/integration/test_goal_evaluation.py#L157) [tests/integration/test_goal_evaluation.py:L120](../../tests/integration/test_goal_evaluation.py#L120) 本轮未运行。

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

<a id="q194"></a>
### Q194：P50/P95/P99、QPS、吞吐量、错误率怎么测？

#### 1. 标准答案

P50/95/99是延迟分位，QPS是时间内请求数，吞吐可按任务或token计；错误率声明分母与错误定义。固定负载、并发、预热和计时范围，记录失败及排队，不能只测成功请求。

以稳定计时器记录从接收请求到完成的延迟，并分别统计排队、首事件与最终回答时间。QPS 可区分 offered、accepted 和 completed，吞吐也可用业务任务/秒或输出 token/秒，单位不能混用。压测需固定并发模型、预热和依赖规模，避免闭环客户端隐藏排队效应；P99 需要足够样本，少量成功调用无法支持可靠长尾结论。

#### 2. 面试口述版

我先定义测什么：从客户端发出到最终答案的端到端延迟，还是模型HTTP、首事件或首token？P95不是五次请求取最大，QPS也不等于token吞吐。项目有节点耗时和百分位函数，但当前不是完整负载测试平台，历史四项业务耗时不能变成生产P95。压测要固定硬件、模型、并发与冷暖缓存，记录排队、超时和错误，不只统计成功样本。还要区分SSE进度与最终受验证答案，避免用很快的started事件宣称生成快。未经授权不能为测吞吐大量付费调用，当前文档只解释方法和已有边界。

#### 3. Adaptive-RAG实际实现

已实现percentile近邻索引算法和节点latency，生产负载基准未实现/未验证。[eval/metrics.py:L38](../../eval/metrics.py#L38) [app/services/chat_service.py:L105](../../app/services/chat_service.py#L105)

#### 4. 面试官可能追问

- **追问：P99样本少可靠吗？** 答：非常不稳定，要足够样本并报告方法。
- **追问：SSE首事件即TTFT吗？** 答：不是，可能只是进度。

#### 5. 测试与证据

test_percentile_picks_nearest_index 验证现行分位算法。[tests/unit/test_metrics.py:L125](../../tests/unit/test_metrics.py#L125) 本轮未压测。

<a id="q195"></a>
### Q195：如何用超时预算和取消传播避免长尾请求拖垮服务？

#### 1. 标准答案

设置总deadline并向节点分配剩余预算，连接/读取/池等待分别超时，断连向任务传播取消；清理在受控shield中完成。取消不证明供应商未计费，需保守账本。

单个 HTTP read timeout 不是整个 Agent deadline：多个串行节点与重试仍可能使总耗时很长。应使用单调时钟维护总截止时间，每次调用从剩余时间分配连接、读取和执行额度。取消后在 finally 关闭响应和迭代器，必要清理限定时长，不能大范围 shield 使付费任务继续运行。外部请求是否已计费需由可信传输证据判断，不由本地取消状态推断。

#### 2. 面试口述版

长尾需要全链预算，不是每个节点各给三十秒后叠起来。理想方案有总deadline，后续步骤读取剩余时间，断连取消后台图和模型请求，连接池和事务也要清理。项目Provider有连接、读取、写入和池超时，SSE关闭会取消图任务，路由显式关闭迭代器；但没有统一全链deadline调度器。取消后供应商可能已经消费，所以预算流会标不确定并阻止继续付费，不能当零成本。测试应模拟发送中断、读取失败和关闭异常，确认无悬挂任务、无错误提交，不能只在客户端显示取消就说后端停了。

#### 3. Adaptive-RAG实际实现

已实现HTTP分段超时、task.cancel与迭代器关闭；统一deadline未实现。[app/providers/deepseek.py:L29](../../app/providers/deepseek.py#L29) [app/services/chat_service.py:L145](../../app/services/chat_service.py#L145) [app/api/routes/chat.py:L20](../../app/api/routes/chat.py#L20)

#### 4. 面试官可能追问

- **追问：断连等于未计费吗？** 答：不等，按不确定消费保守处理。
- **追问：shield能无限包业务吗？** 答：不应，只保护必要清理，避免取消失效。

#### 5. 测试与证据

test_asgi_disconnect_closes_body_iterator_and_graph 检查断连。[tests/integration/test_stream_cleanup.py:L25](../../tests/integration/test_stream_cleanup.py#L25) 全链deadline未验证。

<a id="q196"></a>
### Q196：怎样做LLM批处理、并行检索和模型路由而不破坏依赖关系？

#### 1. 标准答案

批处理适合独立文档编码；并行适合无依赖召回/读取，设并发和预算；规划依赖、确认、事务写入不能任意并发。模型路由按能力和风险验证，保留协议兼容。

并行只有在输入已就绪且操作无相互依赖时才合理，例如两个独立只读召回；先选订单再查详情属于依赖边，写操作还涉及确认和事务。并发控制要同时约束 HTTP 连接、CPU/GPU、数据库连接和预算准入，不能只开 Task。批处理能提高资源利用但可能增加单项等待；共享数据库 Session 或让一个失败丢失其他结果也需专门设计。

#### 2. 面试口述版

我先画依赖图。多篇文档编码可批量，BM25与Dense理论上可并行，订单详情依赖确认目标后才能查，取消更不能和读取、审批随便同时做。项目Ingestor批量embed，本地重排也批预测，但Hybrid当前顺序执行两路，不能说已经并行召回。模型主要是配置的Provider，没有通用按任务多模型网关。若增加并发，应限定资源、取消和原子费用准入，不能共享一个不安全数据库Session到多个任务。性能收益需要测，尤其私有检索仍有SQL权限与版本锁，不能为了快绕开依赖。写操作还要保持幂等和提交顺序。

#### 3. Adaptive-RAG实际实现

已实现批embedding/重排，双路并行与动态模型网关未实现。[app/retrieval/ingest.py:L98](../../app/retrieval/ingest.py#L98) [app/providers/reranker.py:L117](../../app/providers/reranker.py#L117) [app/retrieval/hybrid.py:L49](../../app/retrieval/hybrid.py#L49)

#### 4. 面试官可能追问

- **追问：并行一定减半耗时吗？** 答：资源争用、调度和依赖会影响。
- **追问：能共享AsyncSession吗？** 答：不应随意跨并发任务，共享事务需明确设计。

#### 5. 测试与证据

test_atomic_admission_across_processes 检查预算竞争而非并行性能。[tests/unit/test_paid_budget.py:L135](../../tests/unit/test_paid_budget.py#L135) 并行收益未验证。

<a id="q197"></a>
### Q197：Redis或Qdrant不可用如何降级，哪些操作必须fail-closed？

#### 1. 标准答案

按依赖承担的安全语义决定降级：非关键公共缓存可miss回源，私有权限/版本/限流或消费不确定不能静默绕过。公共检索可有限降级，私有应fail-closed并明确错误。

降级策略取决于依赖的职责。可重算的公共缓存故障可回源，公共召回的一路失败可标记部分能力；但 Owner、私有语料版本、认证、幂等和费用准入失败时应拒绝相关操作。空检索与基础设施失败要向上层明确区分，避免生成器把故障误认为“政策不存在”。恢复后还要检查缓存或索引版本，不能因为恢复连接就假定数据一致。

#### 2. 面试口述版

我不会统一说Redis坏了就用内存。若只是公共检索缓存，可在明确边界内降级；若承担私有版本或限流，静默跳过可能破坏安全。项目公共RedisRetrievalCache对Redis get/set命令异常降级，但缓存JSON解析和模型验证在捕获范围外，损坏payload不保证当miss。公共Qdrant导入可回退内存，Hybrid可单路继续；私有检索依赖失败会抛错，不能回退共享语料。付费账本pending或uncertain也必须阻断。应把可用性和授权边界分开，错误要明确，不能伪装正常空答案。现有代码不等于所有故障均做过真实演练，也不能把Mock当真实断网。

#### 3. Adaptive-RAG实际实现

已实现公共缓存降级与私有fail-closed。[app/retrieval/cache.py:L64](../../app/retrieval/cache.py#L64) [app/retrieval/ingest.py:L131](../../app/retrieval/ingest.py#L131) [app/retrieval/private.py:L230](../../app/retrieval/private.py#L230) [app/providers/paid_budget.py:L612](../../app/providers/paid_budget.py#L612)

#### 4. 面试官可能追问

- **追问：私有为何不能共享回退？** 答：会改变授权语料边界。
- **追问：缓存失败都能忽略吗？** 答：先判断是否承载权限/版本一致性。

#### 5. 测试与证据

test_redis_cache_get_degrades_on_error 与 test_private_retriever_never_uses_unscoped_access 检查两侧。[tests/unit/test_retrieval_cache.py:L153](../../tests/unit/test_retrieval_cache.py#L153) [tests/unit/test_p4f_security_contracts.py:L20](../../tests/unit/test_p4f_security_contracts.py#L20) 本轮未故障注入。

<a id="q198"></a>
### Q198：何时使用熔断、退避重试和限流？

#### 1. 标准答案

限流限制进入速率，退避重试处理暂态故障，熔断在持续失败时快速拒绝并探测恢复。它们不能替代费用准入、幂等或权限；重试必须有上限与抖动。

退避可采用有上限的指数等待加随机抖动，在总 deadline 与次数内只重试可恢复故障；限流按用户/资源控制速率与并发。完整熔断通常有 closed/open/half-open 状态，失败窗口达阈值后拒绝，再限量探测恢复。写入重试需幂等，模型 HTTP 的每次尝试均需预算准入；多个层次重试必须协调，不能把供应商已执行但响应丢失当作免费失败。

#### 2. 面试口述版

三者解决不同时间尺度。限流先限制入口，退避在可恢复失败后错峰重试，熔断在连续故障时避免继续压垮下游。项目有速率限制和full-jitter指数退避，区分认证错误与暂态状态，但没有完整熔断状态机，不能把重试叫熔断。付费还要每次HTTP预留，不确定消费不重试，写操作需要幂等。设计时看总deadline和供应商限制，不能每层各重试三次造成乘法放大。恢复也需小量探测，不能一开闸全部流量同时冲入。当前未做生产故障流量演练，所以不报告虚构恢复时间。

#### 3. Adaptive-RAG实际实现

已实现retry与入口限流，完整CircuitBreaker未实现。[app/core/retry.py:L32](../../app/core/retry.py#L32) [app/core/retry.py:L81](../../app/core/retry.py#L81) [app/services/chat_service.py:L182](../../app/services/chat_service.py#L182)

#### 4. 面试官可能追问

- **追问：401要退避吗？** 答：通常是配置/认证问题，修配置而非重试。
- **追问：熔断能控制费用吗？** 答：不能代替逐次原子预算。

#### 5. 测试与证据

test_does_not_retry_auth_errors 和 test_memory_rate_limiter_blocks 覆盖现有机制。[tests/unit/test_retry.py:L27](../../tests/unit/test_retry.py#L27) [tests/unit/test_retry.py:L40](../../tests/unit/test_retry.py#L40) 熔断未实现。

<a id="q199"></a>
### Q199：发生429是否总应该重试？如何控制重试风暴？

#### 1. 标准答案

429可能是短时速率、配额或账单限制，不能总重试。结合错误语义、Retry-After、deadline和预算，限制次数、并发与full jitter；未知消费停止，避免层层重试。

短时间速率超限与长期配额、余额不足可能都表现为 429，应结合可用的错误码和响应头判别。可恢复时遵守 Retry-After 并加抖动，保留全局并发和重试预算；不可恢复或费用不确定则停止。重试不能占用业务事务锁长时间等待，也不能由客户端、网关和 Provider 各自无限叠加。应在 Trace 标记每个 attempt，以便解释总延迟和总费用。

#### 2. 面试口述版

我先看429原因，而不是固定睡一秒。短时限流可在剩余deadline和预算内退避，长期配额或余额不足重试无益。项目将429标记为可重试并用full jitter，但没有完整按供应商错误细类和Retry-After调度；不能声称所有429都处理最优。真实开发验收曾单次尝试以限制消费，预算每个HTTP都计数，未知消费直接阻断。防风暴还要控制入口并发和每层重试，避免Graph、Provider和客户端叠加。错误结果要明确给用户，不静默换账本或重置次数，更不能把重试后成功只算一次请求。

#### 3. Adaptive-RAG实际实现

已实现429重试与抖动，完整Retry-After/语义分类未实现。[app/providers/deepseek.py:L93](../../app/providers/deepseek.py#L93) [app/core/retry.py:L32](../../app/core/retry.py#L32) [app/providers/paid_budget.py:L653](../../app/providers/paid_budget.py#L653)

#### 4. 面试官可能追问

- **追问：每层三次有何问题？** 答：尝试可能乘法放大，费用与长尾飙升。
- **追问：次数可在成功后返还吗？** 答：不能，HTTP已经发生。

#### 5. 测试与证据

test_provider_429_retries_reserve_every_attempt 检查逐次预留。[tests/unit/test_paid_budget.py:L271](../../tests/unit/test_paid_budget.py#L271) 风暴规模测试未验证。

<a id="q200"></a>
### Q200：SSE已发送部分数据后失败，HTTP状态码还能更改吗？

#### 1. 标准答案

响应头发送后HTTP状态码不可再改；用SSE错误事件与终止信号表示失败，客户端不得把断流/部分数据当成功。取消应传播并清理，避免继续写入。

一个可靠的流协议需区分进度、最终答案、业务错误和传输结束；done 只代表结束，不能自动等价成功。响应头尚未发送时可返回普通错误状态，之后只能用约定事件和连接状态表达。客户端需要在断流后标为未完成，不自动把已见片段当最终答案。涉及写操作的结果仍以事务事实为准，错误事件不能撤销已经提交的副作用。

#### 2. 面试口述版

SSE已经开始后，不能再把200改成500，所以应用协议必须明确error和done，前端不能只看HTTP成功。项目路由捕获流异常发error再done，ChatService先发节点进度，最后只公开经过验证的答案，不把模型原始JSON边生成边发给用户。这里的token事件还是最终答案分块，不等于供应商实时token流。断连时关闭迭代器并取消图，事务与预算也要保守。测试需覆盖发送中断、图异常、关闭失败和部分输出，确认不会显示成功或继续消费；不能靠最后补一句错误撤销已经执行的危险操作。

#### 3. Adaptive-RAG实际实现

已实现SSE error/done和显式关闭；不是原始模型逐token透传。[app/api/routes/chat.py:L49](../../app/api/routes/chat.py#L49) [app/services/chat_service.py:L175](../../app/services/chat_service.py#L175)

#### 4. 面试官可能追问

- **追问：done代表成功吗？** 答：只是流结束，须结合error/answer状态。
- **追问：已发部分答案如何撤回？** 答：协议需失败展示，尽量只发验证后最终答案。

#### 5. 测试与证据

test_asgi_disconnect_closes_body_iterator_and_graph 检查关闭。[tests/integration/test_stream_cleanup.py:L25](../../tests/integration/test_stream_cleanup.py#L25) 本轮未启动SSE。

<a id="q201"></a>
### Q201：模型调用成功但usage日志未结算，如何保守处理？

#### 1. 标准答案

业务成功与可信结算独立。完整响应但无合格usage可保留原预留标completed未settled；传输中断/关闭失败则uncertain并阻断。不能用日志或前端统计补造结算。

不能从 Provider 日志中的 token 数直接释放预算，因为业务解析层与账本观察层的完整读取、关闭和信任条件可能不同。若响应确认完成但 usage 不可信，可保持 completed 且未结算，继续占满原预留；若传输或消费状态未知，则 uncertain 并阻断后续准入。排查应保留 attempt ID、原预留和原因，不回填伪造 settlement，也不以付费重放替代缺失的历史证据。

#### 2. 面试口述版

模型有答案不代表费用观察层有可信证据。项目预算流读完并确认关闭后才结算，usage不合格时可标完成但保留全额预留；读取或关闭不确定则标uncertain并阻止继续消费。历史最早五个订单调用Provider成功，但账本没结算，仍占原预留，后十五条才按usage结算。不能说五条都已证明由压缩导致，因为原编码头没保留。排查应保留原失败和账本，不事后补造、返额或付费重跑美化。实际usage估算、账本有效占用和供应商账单是三件事，未知也不能直接记零。

#### 3. Adaptive-RAG实际实现

已实现completed/settled与uncertain区分，日志自报不能释放容量。[app/providers/paid_budget.py:L749](../../app/providers/paid_budget.py#L749) [app/providers/usage_settlement.py:L226](../../app/providers/usage_settlement.py#L226)

#### 4. 面试官可能追问

- **追问：无usage必uncertain吗？** 答：完整确认关闭可completed保留预留；传输不确定才uncertain。
- **追问：能用Trace补结算吗？** 答：不能绕过可信证据契约改历史。

#### 5. 测试与证据

test_decoded_entity_settles_only_after_consumption_and_confirmed_close 覆盖关闭边界。[tests/unit/test_paid_budget_compression.py:L65](../../tests/unit/test_paid_budget_compression.py#L65) 历史五条范围见[research/docs/agent_engineering_upgrade/deepseek_business_acceptance/REPORT.zh-CN.md:L52](../../research/docs/agent_engineering_upgrade/deepseek_business_acceptance/REPORT.zh-CN.md#L52)。

<a id="q202"></a>
### Q202：DeepSeek响应压缩解码不一致会导致什么Bug？

#### 1. 标准答案

观察层若读压缩原字节、Provider读解压内容，会出现业务成功而usage无法验证；重复解压也会失败。共享同一解码实体并处理完整读取/关闭，保留失败与原预留。

压缩体可能是 gzip 或 deflate。若底层预算包装器抓到原始压缩字节，而 HTTP 客户端在另一层解码，预算解析会失败；若又保留旧 Content-Encoding 给上层，还可能触发重复解压。修复应明确只有一个解码实体，预算观察与 Provider 读取同一份内容，并确保只有完整消费、可信结束及确认关闭后结算。这个可复现机制不能证明未保留编码头的所有历史失败都由它造成。

#### 2. 面试口述版

这个Bug的关键是两层看到了不同字节。HTTPX替Provider解压后JSON能解析，预算观察层却可能拿原始压缩内容，导致usage不合格，业务成功但不能结算。项目用本地RED复现并修为同一份解压实体，覆盖gzip、deflate和JSON/SSE，避免重复解压。真实历史后十五次结算成功，最初五次仍保留预留；没有原编码头，不能逐条断言全是压缩导致。这个案例说明不能只查回答或HTTP200，要对齐数据流与关闭时机。修复也不能放松取消和提前关闭边界，更不能事后改旧账使费用看起来一致。

#### 3. Adaptive-RAG实际实现

已实现_DecodedEntityStream共享解码及_BudgetStream消费后结算。[app/providers/paid_budget.py:L690](../../app/providers/paid_budget.py#L690) [app/providers/paid_budget.py:L704](../../app/providers/paid_budget.py#L704) 历史因果限制明确保留。

#### 4. 面试官可能追问

- **追问：为什么不直接信Provider日志？** 答：结算需独立完整可信响应，不靠可缺失日志。
- **追问：修复后五条可返吗？** 答：缺原证据，保留原预留不补造。

#### 5. 测试与证据

test_compressed_provider_success_settles_decoded_usage 为本地回归。[tests/unit/test_paid_budget_compression.py:L26](../../tests/unit/test_paid_budget_compression.py#L26) 历史报告[research/docs/agent_engineering_upgrade/deepseek_business_acceptance/REPORT.zh-CN.md:L54](../../research/docs/agent_engineering_upgrade/deepseek_business_acceptance/REPORT.zh-CN.md#L54)，本轮未重跑。

<a id="q203"></a>
### Q203：如何从Trace定位“订单工具没执行”，而不是猜模型效果不好？

#### 1. 标准答案

沿root查路由、计划、参数净化、权限/确认、工具span、执行记录与事务；没有工具可能是正确拒绝、预算前置阻断或规划缺失，不先归咎模型。

先确认 request/trace 与执行模式，再看 Intent/Router 是否进入 Planner，计划是否包含所需工具，净化是否删除错误或冗余步骤；随后检查 Schema、Owner、确认和预算是否前置拒绝。工具 span 存在也不等于成功，要核对参数、状态、返回值和提交结果。缺少记录时应标记证据不足，不能把最终回答中的“我已查询”当执行证据。

#### 2. 面试口述版

我会先看请求停在哪个节点。Intent没发出可能是预算阻断，Router走DIRECT可能是策略问题，Planner没工具是规划或裁剪，工具被拒绝则查身份、owner、确认和参数，执行后还需查事务。项目有节点和工具span、record_tool、错误分类与独立状态，不能仅看回答说“查不到”就猜模型差。首次真实订单场景实际上在Intent发送前被预算拒绝，工具零执行，这与工具模型能力无关。通用Trace不记录完整参数，需受控证据核对，不能为排障输出隐私。判断完再加精准回归，保留原始失败。

#### 3. Adaptive-RAG实际实现

已实现tracing/record_tool，自动根因诊断未实现。[app/observability/tracing.py:L61](../../app/observability/tracing.py#L61) [app/tools/base.py:L73](../../app/tools/base.py#L73) [app/services/chat_service.py:L321](../../app/services/chat_service.py#L321)

#### 4. 面试官可能追问

- **追问：没tool span一定规划错吗？** 答：可能更早预算、授权或路由终止。
- **追问：回答说调用过算证据吗？** 答：不算，要执行记录和状态。

#### 5. 测试与证据

历史订单预算前置拒绝见[research/docs/agent_engineering_upgrade/deepseek_live_acceptance/DEEPSEEK_LIVE_ACCEPTANCE_REPORT.md:L20](../../research/docs/agent_engineering_upgrade/deepseek_live_acceptance/DEEPSEEK_LIVE_ACCEPTANCE_REPORT.md#L20)；test_caps_block_before_dispatch验证门禁。[tests/unit/test_paid_budget.py:L65](../../tests/unit/test_paid_budget.py#L65) 本轮未运行。

<a id="q204"></a>
### Q204：模型延迟增加2倍，如何拆分排查DNS、TLS、路由、生成和下游工具？

#### 1. 标准答案

拆端到端为排队、DNS、连接/TLS、请求发送、模型prefill/decode、重试和下游工具/数据库；固定输入、输出量和负载配对，先看Trace再补网络观测。

端到端延迟不一定是各段简单相加，因为连接复用和并行会重叠。先按 Trace 定位变慢区段，再增加连接建立、TLS、首字节和连接池等待观测；复用连接时 DNS/TLS 可能没有发生。模型侧还需控制输入、输出 token 与模式，供应商不暴露的 prefill/decode 不能凭客户端总耗时精确拆分。对比应固定负载并查看分位，不以一条请求推断服务退化。

#### 2. 面试口述版

模型调用变慢两倍不一定是生成速度变慢。可能DNS或TLS、连接池排队、网络路由、输出更长、限流重试，也可能慢的是工具或数据库。项目有节点与LLM/HTTP span和分段超时，但没有DNS/TLS阶段自动细分指标，不能假装Trace已直接测出全部原因。我会先比较输入输出usage、尝试次数和各节点耗时，固定问题与输出预算，再在授权环境补连接复用和网络阶段测量。端到端变慢也可能因更完整任务多调用工具，不能只用总耗时断言模型退化，更不能把一次网络异常外推成供应商长期性能。

#### 3. Adaptive-RAG实际实现

已有LLM/attempt与节点耗时，DNS/TLS细分仪表未实现。[app/providers/deepseek.py:L29](../../app/providers/deepseek.py#L29) [app/providers/deepseek.py:L75](../../app/providers/deepseek.py#L75) [app/observability/tracing.py:L151](../../app/observability/tracing.py#L151)

#### 4. 面试官可能追问

- **追问：输出翻倍能直接比延迟吗？** 答：应同时看输出量和任务质量。
- **追问：连接池慢如何识别？** 答：需池等待观测，当前timeout不等于测量指标。

#### 5. 测试与证据

test_concurrent_roots_and_privacy 检查追踪隔离。[tests/unit/test_tracing.py:L17](../../tests/unit/test_tracing.py#L17) 网络分段性能未验证。

<a id="q205"></a>
### Q205：费用限额的并发原子预留如何保证不超扣？

#### 1. 标准答案

发送前同一事务检查剩余容量并写最坏预留，使用持久锁/原子操作防竞争；结算追加且次数不返还。未知消费阻断，账本校验不是抵御root重写的密码学防篡改。

安全顺序是事务中读取有效占用→校验请求数与最坏费用→追加 attempt 预留→提交后才发 HTTP，不能先调用再记账。可信结算只释放原预留与合格实际用量之间的差额，已经发生的 HTTP 次数不返还。SQLite 的 BEGIN IMMEDIATE 可串行化本地写入；重启仍读取同一账本，pending/uncertain 保守阻断。该设计优先安全，不等于高吞吐多地域账务服务。

#### 2. 面试口述版

并发预算不能先读余额再异步扣，否则两个请求都会认为足够。项目SQLite用BEGIN IMMEDIATE把容量检查和pending预留放同一事务，HTTP前完成；可信usage可减少有效费用，原预留仍保留。还要准确说明当前pending或uncertain会全局阻断后续，因此是保守单飞，不是高吞吐多路同时调度。文件权限、指纹和closure witness提供程序一致性边界，不是签名或WORM，不能抵御特权者同时重写多表。并发测试验证准入不超限，但不代表生产跨地域账务。失败应保留记录，不能换账本绕开限制。

#### 3. Adaptive-RAG实际实现

已实现事务原子reserve和全局未决阻断；高吞吐预算调度、密码学不可篡改未实现。[app/providers/paid_budget.py:L183](../../app/providers/paid_budget.py#L183) [app/providers/paid_budget.py:L617](../../app/providers/paid_budget.py#L617) [app/providers/paid_budget.py:L653](../../app/providers/paid_budget.py#L653)

#### 4. 面试官可能追问

- **追问：锁住余额后能并行很多吗？** 答：当前未决全局阻断，不能如此宣称。
- **追问：指纹等于签名吗？** 答：不是，依赖权限和可信管理员。

#### 5. 测试与证据

test_atomic_admission_across_processes 验证竞争。[tests/unit/test_paid_budget.py:L135](../../tests/unit/test_paid_budget.py#L135) 分布式账务规模未验证。

<a id="q206"></a>
### Q206：如何设计安全的灰度发布与回滚？

#### 1. 标准答案

灰度固定发布单元和回滚契约，先离线/隔离验收，再少量租户或流量，监控安全、质量、费用与长尾，阈值触发止损；影子不得真实写，回滚考虑数据迁移与幂等。

发布前记录镜像/代码/模型、Prompt、Schema、数据库迁移与索引版本，明确回滚兼容区间。先隔离验证，再小流量观察，安全问题应立即停止而非用平均成功率抵消。数据库采用兼容迁移有利于回滚，已经写入的数据和业务副作用则需要独立补偿策略。付费授权关闭是费用止损控制，不等同于自动应用回滚或撤销已完成请求。

#### 2. 面试口述版

安全灰度先定义发布的整体：模型、Prompt、Graph、工具schema和索引版本，不能只保存一个镜像名。离线与隔离验收后，才小范围真实流量，设费用、错误、任务质量和延迟止损。项目保留模式配置、预算授权关闭与历史验收，但没有完整自动流量灰度平台，我只能把方案与能力分开。写工具影子不能对真实业务产生二次副作用，回滚也不能撤销已发生的退款，只能停止新操作并按业务补偿。数据库迁移应前后兼容，索引空间不能混。当前没有生产canary数据，不能报告虚构回滚时间或百分比。

#### 3. Adaptive-RAG实际实现

项目未实现自动灰度/回滚控制器；已有显式授权关闭和配置可作基础。[app/providers/paid_budget.py:L479](../../app/providers/paid_budget.py#L479) [app/config/settings.py:L40](../../app/config/settings.py#L40)

#### 4. 面试官可能追问

- **追问：回滚可撤销业务写吗？** 答：不自动等价，需要业务补偿流程。
- **追问：只监HTTP错误够吗？** 答：还需任务完整、权限、副作用与费用。

#### 5. 测试与证据

test_closure_is_permanent_idempotent_and_allows_distinct_later_grant 检查关闭边界。[tests/unit/test_budget_authorization.py:L142](../../tests/unit/test_budget_authorization.py#L142) 生产灰度未验证。

<a id="q207"></a>
### Q207：缓存命中改善但业务任务成功率下降，如何解释？

#### 1. 标准答案

缓存命中只代表复用，不证明结果新鲜、完整或授权正确；可能错误键、过期状态、裁剪必要调用或错误缓存。固定任务检查命中前后证据与目标，按scope/version失效。

常见原因有键缺少 tenant、revision 或模型参数，过期订单状态被复用，空结果/错误被缓存，或为提高命中率删除了必要检索。应对同一冻结任务比较缓存开关，检查命中文档、版本、权限和最终目标，而不仅是响应速度。实时业务事实宜绕过不适合的缓存；私有数据键和命中后二次校验都需保留，避免缓存成为跨用户访问通道。

#### 2. 面试口述版

缓存更高却成功率更低，往往优化了代理指标。可能把旧订单状态复用、不同用户或版本共键，或为省调用删掉必要商品与物流证据。项目公共检索缓存跳过订单类查询，私有键含subject/generation且ID重查canonical，但这些机制不等于所有缓存策略都安全。我要按命中与未命中分别比较任务完整、事实新鲜和权限，再查TTL、键与失效；不能只看响应变快。Planner裁剪也可能让调用更少却漏目标，应保留明确子问题。现有测试覆盖部分失效与绕过，真实业务命中率提升收益尚无生产验证。

#### 3. Adaptive-RAG实际实现

已实现订单查询缓存绕过和私有版本scope，生产优化结论未验证。[app/retrieval/cache.py:L18](../../app/retrieval/cache.py#L18) [app/retrieval/cache.py:L64](../../app/retrieval/cache.py#L64) [app/retrieval/private.py:L225](../../app/retrieval/private.py#L225)

#### 4. 面试官可能追问

- **追问：TTL短就安全吗？** 答：错误scope或键即使短也泄露，需正确身份版本。
- **追问：命中旧ID怎么办？** 答：按当前canonical复核，删除后不可返回。

#### 5. 测试与证据

test_redis_cache_skips_order_queries 与 test_memory_cache_expires_after_ttl 检查现有机制。[tests/unit/test_retrieval_cache.py:L145](../../tests/unit/test_retrieval_cache.py#L145) [tests/unit/test_retrieval_cache.py:L97](../../tests/unit/test_retrieval_cache.py#L97) 本轮未运行。

<a id="q302"></a>
### Q302：Transformer与self-attention基本机制是什么？Q、K、V如何理解？

#### 1. 标准答案

Transformer 通过注意力、前馈网络、残差连接和归一化等模块处理序列，并引入位置信息。输入表示 X 经不同可学习投影得到 Q=XWq、K=XWk、V=XWv；Q 表示当前位置要匹配的信息，K 表示被匹配的位置特征，V 是按相关性汇聚的内容。缩放点积注意力为 `softmax(QKᵀ/√d_k + mask)V`，多头在不同投影子空间并行计算后融合。它是连续向量计算，Q/K/V 不是程序中的数据库查询键值。

自注意力的 Q/K/V 来自同一序列；交叉注意力的 Q 与 K/V 可来自不同序列。自回归生成使用因果 mask，禁止看到未来 token。经典完整注意力的分数矩阵随序列长度平方增长；实际模型可能有其他注意力变体，不能从 API 名字推断内部实现。原理来源：[Attention Is All You Need](https://arxiv.org/abs/1706.03762)。

#### 2. 面试口述版

我把自注意力理解为每个位置根据当前需要，从上下文汇聚相关信息。输入经三个不同投影得到 Q、K、V，Q 和各位置 K 算匹配分数，缩放并做 softmax 后对 V 加权。多头让模型从不同子空间组织信息，位置编码或其他位置机制补充顺序。生成模型还要用因果遮罩，防止读取未来答案。它解释了为什么上下文能够影响输出，但不保证注意到的内容就是真实证据。Adaptive-RAG 调用供应商模型，没有自己实现 Transformer 或训练权重；系统正确性仍要靠检索、Schema 和业务权限校验，不能用注意力机制代替这些控制。

#### 3. Adaptive-RAG实际实现

**项目未实现 Transformer 层或训练。** `LLMProvider` 只声明生成接口，见 [app/providers/base.py:L37](../../app/providers/base.py#L37)；`DeepSeekProvider.generate` 发送 messages 并读取生成结果，见 [app/providers/deepseek.py:L51](../../app/providers/deepseek.py#L51)。这些代码无法证明供应商当前模型的注意力头数、层数或内部权重架构，相关具体数字未验证。

#### 4. 面试官可能追问

- **追问：为什么要除以 √d_k？** 答：在常见假设下点积随维度增大，缩放避免 softmax 过度饱和；这是数值稳定与优化考虑。
- **追问：多头就是多个 Agent 吗？** 答：不是。它们是同一网络内部的向量计算子空间，没有独立业务身份、工具执行或协作协议。
- **追问：注意力权重大能证明引用支持答案吗？** 答：不能。权重不是事实审计，需要核对返回文档、引用标识与具体结论的支持关系。

#### 5. 测试与证据

`test_provider_preserves_actual_model_and_finish_reason` 验证 API 返回的模型标识与终止原因被保留，见 [tests/unit/test_p2_json_reliability.py:L39](../../tests/unit/test_p2_json_reliability.py#L39)。这是 MockTransport 集成契约，不测试网络内部注意力，也没有本轮执行结果。

<a id="q303"></a>
### Q303：Embedding模型与生成模型有什么不同？

#### 1. 标准答案

Embedding 模型把文本映射为适于相似度计算的向量，常用于检索、聚类和去重；训练目标通常强调语义匹配或对比学习。生成模型按条件预测后续 token，输出自然语言或结构化文本。生成模型内部也有 token embedding，但不代表其任意隐层向量可直接替代经过检索训练的句向量模型。

检索时文档与查询必须使用兼容的模型、版本、维度和归一化策略；同样维度不代表同一向量空间。生成器拿到检索证据后负责组织回答，两者可独立更换，但索引与 query 编码需同步迁移。Embedding 相似度只是候选相关性，不是权限或真实性证明。

#### 2. 面试口述版

Embedding 回答的是怎样把文本放到可比较的向量空间，生成模型回答的是给定上下文接下来输出什么。前者适合找候选材料，后者把材料组织成回答，两者并不互相替代。项目把它们拆成独立 Provider，文档入库和查询编码使用同一套向量协议，生成则走 DeepSeek。换 Embedding 即使维度一样，也通常需要重建索引并切换版本，否则新旧向量没有可比较的语义。还要区分真正训练好的向量与离线 hash 降级，hash 只能支持可复现演示，不能称为模型语义能力。最终回答仍要检查引用和当前用户是否有权访问命中文档。

#### 3. Adaptive-RAG实际实现

`LLMProvider` 与 `EmbeddingProvider` 是不同协议，见 [app/providers/base.py:L37](../../app/providers/base.py#L37) 和 [app/providers/base.py:L80](../../app/providers/base.py#L80)。`build_embedding_provider` 按配置选择远程、本地或 hash，见 [app/providers/embeddings.py:L213](../../app/providers/embeddings.py#L213)；`HashEmbeddingProvider` 是确定性替代实现，见 [app/providers/embeddings.py:L33](../../app/providers/embeddings.py#L33)。项目没有训练 Embedding 模型；配置存在不等于当前演示已加载真实权重。

#### 4. 面试官可能追问

- **追问：只换 query 的 Embedding 可以吗？** 答：通常不可以。要与索引使用同一语义空间；迁移可双写双索引验证后切换，不能混用同维度模型。
- **追问：Embedding 分高能直接回答吗？** 答：不能。相似不代表支持结论，仍需文档有效性、权限、重排和证据核验。
- **追问：Cross-Encoder 属于哪一种？** 答：它把 query 与文档一起编码并输出相关性分数，通常用于重排；它既不是离线独立句向量索引，也不是聊天生成器。

#### 5. 测试与证据

`test_injected_bge_m3_encodes` 使用注入的假模型验证编码形状，见 [tests/unit/test_embeddings.py:L36](../../tests/unit/test_embeddings.py#L36)；`test_factory_falls_back_to_hash_in_testing` 见 [tests/unit/test_embeddings.py:L61](../../tests/unit/test_embeddings.py#L61)。这些不下载权重，不证明真实模型检索质量，本轮未运行。

<a id="q304"></a>
### Q304：预训练、SFT、DPO、RLHF、LoRA/QLoRA的适用场景？

#### 1. 标准答案

预训练从大规模语料学习通用表示与语言预测能力，成本和数据治理要求高。SFT 用指令—答案示例学习任务行为、格式与领域表达。经典 RLHF 流程可包含 SFT、偏好数据训练奖励模型，再以强化学习优化策略；DPO 用偏好对直接优化策略相对参考模型的概率关系，通常省去显式奖励模型和在线 RL 环节，但依然依赖高质量偏好数据。

LoRA 是参数高效适配方法：冻结基础权重，训练低秩增量；QLoRA 将冻结的基础模型量化后训练适配器，以降低微调显存。它们与 SFT、偏好目标属于不同维度，可以组合，不能把 LoRA 说成与 SFT 互斥的一种学习目标。参考 [InstructGPT](https://arxiv.org/abs/2203.02155)、[DPO](https://arxiv.org/abs/2305.18290)、[LoRA](https://arxiv.org/abs/2106.09685)、[QLoRA](https://arxiv.org/abs/2305.14314)。

#### 2. 面试口述版

我会先把学习目标和参数更新方式分开。预训练建立通用能力，SFT 用示例教任务行为；偏好优化进一步调整哪种答案更符合目标，经典 RLHF 可训练奖励模型再做强化学习，DPO 则直接用偏好对优化策略。LoRA 和 QLoRA 解决的是怎样降低适配成本，不是新的业务目标，它们可以服务于 SFT 等训练。对这个项目，我会先修数据、工具和检索问题，只有稳定复现的行为缺陷才考虑微调，并准备独立验证集。Adaptive-RAG 当前没有预训练、SFT 或偏好训练流水线，也没有 LoRA 权重产物，不能把调用已经训练好的供应商模型说成自己完成了训练。

#### 3. Adaptive-RAG实际实现

**项目未实现预训练、SFT、DPO、RLHF、LoRA 或 QLoRA。** `DeepSeekProvider` 只构造推理请求，见 [app/providers/deepseek.py:L63](../../app/providers/deepseek.py#L63)；`Settings` 配置模型名和推理参数，见 [app/config/settings.py:L37](../../app/config/settings.py#L37)。本地 Embedding 加载预训练 SentenceTransformer 的位置见 [app/providers/embeddings.py:L130](../../app/providers/embeddings.py#L130)，加载权重不等于训练。没有证据可还原供应商内部训练配方。

#### 4. 面试官可能追问

- **追问：有几百条 Badcase 就应该微调吗？** 答：先按根因分类。越权、索引缺失和事务错误应修系统；可学习且反复出现的格式/行为问题才适合准备训练数据。
- **追问：DPO 不训练奖励模型，就不需要人类偏好吗？** 答：仍需可信偏好对或其他明确来源的排序信号；省去显式奖励模型不等于省去偏好质量要求。
- **追问：LoRA 能持续更新实时订单吗？** 答：不适合。交易状态应实时查数据库，训练不能替代数据新鲜度、访问权限和删除要求。

#### 5. 测试与证据

`test_explicit_non_thinking_mode_reaches_json_and_stream_payloads` 仅检验推理请求载荷，见 [tests/unit/test_deepseek_thinking.py:L14](../../tests/unit/test_deepseek_thinking.py#L14)。项目没有相应训练收敛、偏好收益或适配器评测证据；本轮不训练、不调用模型。

<a id="q305"></a>
### Q305：RAG与微调是替代还是互补？

#### 1. 标准答案

通常互补。RAG 在推理时取回外部知识，适合更新频繁、需要引用、权限隔离和可删除的事实；微调改变模型参数，更适合稳定的风格、领域表达和任务行为。两者都不能天然保证真实性：RAG 会检错或使用恶意文档，微调会遗忘、记错或泛化失败。原始 RAG 工作也讨论了参数记忆与非参数记忆的组合，见 [RAG 论文](https://arxiv.org/abs/2005.11401)。

先用错误归因决定动作：缺证据修检索，引用不忠实修生成约束和核验，固定格式表现不稳可评估微调。决定组合后仍需在同一冻结评测集上比较质量、延迟、成本及权限边界，不把训练集准确率当业务收益。

#### 2. 面试口述版

我通常把 RAG 当作外部事实通道，把微调当作行为适配，两者可以组合。政策更新、文档权限和删除不适合靠重新训练解决，检索更容易提供版本和引用；固定输出格式或领域表达长期不稳时，才考虑高质量示例微调。项目选择先做 RAG 与工具，把政策交给检索，把实时订单交给数据库，再检查答案是否被证据支持。若回答错了，我会先判断是没召回、证据冲突，还是模型没按证据说话，不能见到幻觉就默认微调。当前项目没有微调产物，也没有 RAG 与微调的同条件对照，所以我只能说明设计取舍，不能宣称实测证明两者谁更优。

#### 3. Adaptive-RAG实际实现

`build_graph` 将检索节点接到生成节点，见 [app/agents/graph.py:L65](../../app/agents/graph.py#L65) 与 [app/agents/graph.py:L110](../../app/agents/graph.py#L110)。私有检索以 SQL 主体、有效 chunk 与版本为准，见 [app/retrieval/private.py:L216](../../app/retrieval/private.py#L216)。生成后调用 `faithfulness_node`，见 [app/agents/nodes/faithfulness.py:L79](../../app/agents/nodes/faithfulness.py#L79)。**项目未实现微调流水线或微调效果对照。**

#### 4. 面试官可能追问

- **追问：把公司文档全部 SFT 就不用向量库了吗？** 答：不能据此保证精确记忆、及时更新、引用和按租户删除；业务事实仍需要外部权威来源。
- **追问：RAG 一定比微调便宜吗？** 答：不一定。检索、重排和长上下文都有运行成本；需按数据变化频率、请求量与训练维护成本核算。
- **追问：怎样验证组合有效？** 答：固定检索语料、问题和金标准，分别比较基线、RAG、微调及组合，保持预算一致并单独检查权限与事实错误。

#### 5. 测试与证据

已有 `test_chat_stream_emits_token_and_node_events` 检查最终答案传输一致性，见 [tests/e2e/test_chat_api.py:L50](../../tests/e2e/test_chat_api.py#L50)；它不能代替 RAG/微调消融。项目微调对照证据缺失，本轮仅审阅源码与测试。

<a id="q306"></a>
### Q306：什么是KV Cache，推理时为什么有Prefill和Decode阶段？

#### 1. 标准答案

自回归 Transformer 的 KV Cache 保存各层已处理 token 的 Key/Value，下一步生成时重用，避免重新计算整个前缀。它是推理引擎里的中间张量，不是 Redis 检索缓存、会话数据库或业务记忆。

Prefill 处理输入提示的多个位置、建立缓存并得到下一 token 分布，通常能利用较多并行计算；Decode 逐步扩展序列，每步读取已有缓存并加入新 token 的 K/V，常受内存带宽与批调度影响。KV 显存随序列长度、并发批次、层数、KV 头数、头维度和数据精度增长；GQA/MQA 等架构会改变大小，不能只按总参数量估算。见 [Transformers KV Cache 官方说明](https://huggingface.co/docs/transformers/v4.46.0/kv_cache)。

#### 2. 面试口述版

KV Cache 是模型推理时保存历史位置 Key 和 Value 的缓存。Prefill 先处理整个输入前缀，建立缓存；Decode 每生成一步就重用旧缓存，并追加新位置，所以不用每次把全部前缀重算。它提升生成效率，但长上下文和并发请求会占用大量 KV 显存，吞吐并不是只看权重能否放进显卡。这里还要区分几种缓存：Redis 放检索结果，数据库放会话，供应商前缀缓存也有自己的规则，它们不等于应用掌握 KV 张量。Adaptive-RAG 走远程 API，没有自建推理引擎；能记录外部调用耗时，却不能从它直接拆出供应商真实 Prefill 和 Decode 时间。

#### 3. Adaptive-RAG实际实现

**项目未实现 KV Cache 或推理引擎调度。** `DeepSeekProvider.generate` 只是 HTTP 客户端，见 [app/providers/deepseek.py:L78](../../app/providers/deepseek.py#L78)；`stream` 解析供应商 SSE 增量，见 [app/providers/deepseek.py:L171](../../app/providers/deepseek.py#L171)。`RedisRetrievalCache` 缓存的是文档 chunk JSON，见 [app/retrieval/cache.py:L59](../../app/retrieval/cache.py#L59)，不能把它写成模型 KV 缓存。

#### 4. 面试官可能追问

- **追问：KV Cache 会让模型记住下一次用户请求吗？** 答：不自动保证。跨请求复用取决于引擎与前缀缓存策略，应用仍需显式传历史并做身份隔离。
- **追问：上下文变长只影响 Prefill 吗？** 答：不是。Decode 每步访问的历史缓存也更大，还会影响显存容量与可容纳并发。
- **追问：首 token 慢一定是 Prefill 慢吗？** 答：不一定，还包含网络、排队、鉴权、预处理与可能的模型内部工作；缺少供应商分段指标不能单一归因。

#### 5. 测试与证据

`test_explicit_non_thinking_mode_reaches_json_and_stream_payloads` 检查模拟流与普通请求兼容性，见 [tests/unit/test_deepseek_thinking.py:L14](../../tests/unit/test_deepseek_thinking.py#L14)。它不观察 KV 张量或阶段耗时；项目无自建引擎 Prefill/Decode 基准，本轮未运行。

<a id="q307"></a>
### Q307：什么是Tokenization、最大上下文、输出截断？

#### 1. 标准答案

Tokenization 将文本编码为模型词表中的 token ID；一个 token 不固定等于一个汉字、英文单词或字节。最大上下文是模型允许处理的序列容量，通常需要同时考虑输入、模板开销和输出空间，具体计算以模型接口为准。`max_tokens` 是输出上限，不是免费保证输出到该长度；停止条件、模型上下文或供应商限制也可能让输出提前结束。

截断可能发生在输入预处理或输出生成。结构化输出因 `finish_reason="length"` 截断，即使末尾恰好能解析成 JSON 也不应当作完整业务结果。对策是预算完整请求、先保留实体与必要证据再压缩历史，并显式处理结束原因。

#### 2. 面试口述版

Token 是模型编码单位，不是固定字符数，所以我不会用中文多少字直接等同实际计费 Token。上下文容量还要容纳消息模板、工具描述和输出预留，不能把窗口全塞满再期待继续生成。项目有两层估算：历史压缩用字符启发式，完整发送前按序列化 UTF-8 字节加余量和输出上限做保守检查，实际用量看供应商可信 usage。结构化输出还要检查 finish_reason，length 代表可能截断，不能因为 JSON 看似闭合就执行动作。当前配置预算不是供应商当前窗口的证明，模型升级后还需重新核对接口限制与相同任务的回归结果。

#### 3. Adaptive-RAG实际实现

`estimate_tokens` 是启发式，见 [app/memory/budget.py:L28](../../app/memory/budget.py#L28)；`enforce_request_budget` 检查完整载荷与输出预留，见 [app/memory/budget.py:L14](../../app/memory/budget.py#L14)。`DeepSeekProvider.generate` 在结构化响应且结束原因是 length 时抛截断异常，见 [app/providers/deepseek.py:L106](../../app/providers/deepseek.py#L106)。代码注释中关于 tokenizer 公开状态的说法不作为当前事实依据；项目没有接入精确供应商 tokenizer 的证据。

#### 4. 面试官可能追问

- **追问：`max_tokens=1000` 就一定计费1000吗？** 答：不是，实际生成可能更少；项目预留最大成本，可信 usage 满足条件后再结算。
- **追问：JSON 完整为什么还要拒绝 length？** 答：可能只完成了局部字段或省略后续步骤，语法完整不能证明语义完整，写操作尤其应保守。
- **追问：压缩时先删最旧内容就行吗？** 答：不够。需要保留当前指代的订单实体、确认状态和关键约束；错误删除会让后续工具参数指向错误对象。

#### 5. 测试与证据

`test_complete_serialized_input_and_output_reservation_checked_before_http` 见 [tests/unit/test_context_budget.py:L10](../../tests/unit/test_context_budget.py#L10)；`test_structured_length_finish_is_rejected_without_retry` 包含看似完整 JSON 的截断案例，见 [tests/unit/test_p2_json_reliability.py:L12](../../tests/unit/test_p2_json_reliability.py#L12)。均为已有本地/模拟测试，本轮未运行。

<a id="q308"></a>
### Q308：Temperature和Top-p如何影响概率采样？

#### 1. 标准答案

对 logits z，温度 T>0 时常按 `softmax(z/T)` 重标概率。低温让高概率候选更集中，高温增加分布平坦程度；T 趋近零接近贪心选择，接口允许的具体值与实现应查供应商协议。Top-p 又称 nucleus sampling：按概率排序，保留累计概率达到阈值 p 的最小候选集合，重新归一化后采样。见 [Nucleus Sampling 原论文](https://arxiv.org/abs/1904.09751)。

两者控制不同环节；同时调动会增加归因难度，实践可固定一项再比较另一项。低温不保证事实正确或跨批次逐字确定，数值计算、路由、版本与服务端调度也可能影响结果。业务授权不能靠调低温度实现。

#### 2. 面试口述版

Temperature 调的是概率分布的集中程度，低温更偏向高分候选，高温更分散；Top-p 则动态截取累计概率足够大的候选集合，再在集合里采样。它们不是准确率旋钮，更不是安全开关。项目的意图、规划和判定等结构化路径通常使用低温，目的是减少格式和选择波动，仍然要做 Schema 与业务规则校验。当前 Provider 暴露 temperature，没有显式传 top_p，所以不能声称做过 Top-p 调参。我会一次只改一个参数，在固定问题和证据集上看任务成功率、格式失败率、成本与重复试验差异，而不会把温度为零宣传成绝对可复现。

#### 3. Adaptive-RAG实际实现

`LLMProvider.generate` 接受 temperature，见 [app/providers/base.py:L40](../../app/providers/base.py#L40)；`DeepSeekProvider` 发送 temperature，没有发送 top_p，见 [app/providers/deepseek.py:L63](../../app/providers/deepseek.py#L63)。`FaithfulnessChecker.check` 明确使用 0.0，见 [app/guardrails/hallucination.py:L83](../../app/guardrails/hallucination.py#L83)。接口注释里的“0.0 keeps output deterministic”应理解为降低随机性意图，不是项目验证过的确定性承诺。

#### 4. 面试官可能追问

- **追问：低温模型就不会幻觉吗？** 答：不会。它可能稳定选择一个错误答案，仍需真实证据与外部校验。
- **追问：Top-p 和 Top-k 有何区别？** 答：Top-k 固定候选数量，Top-p 根据当前概率集中程度动态决定数量；它们都不是检索链路的文档 Top-K。
- **追问：怎样做可复现比较？** 答：固定模型标识、提示版本、数据和预算，记录参数并重复运行；即使供应商提供 seed，也要报告残余波动。

#### 5. 测试与证据

`test_judge_allowance_is_explicit_and_no_extra_call` 检查判定调用参数与次数，见 [tests/unit/test_p2_json_reliability.py:L77](../../tests/unit/test_p2_json_reliability.py#L77)。它不构成 temperature/top-p 效果试验；项目无同条件采样参数对照证据，本轮未运行。

<a id="q309"></a>
### Q309：MoE与稠密模型有什么区别？

#### 1. 标准答案

稠密模型通常让每个 token 使用相同的一套层参数；稀疏 MoE 在部分模块中设置多个专家，由路由器对每个 token 选择少量专家计算，再合并结果。于是总参数量可大于单 token 激活参数量，但其他共享层仍参与计算。MoE 中的专家是神经网络子模块，不是业务 Agent 或人工专家。参考 [Switch Transformers](https://arxiv.org/abs/2101.03961)。

MoE 可在相近激活计算下扩大模型容量，但需要处理路由负载不均、专家容量与跨设备通信；总权重仍要存储或调度，因此“激活参数少”不等于低显存、低延迟或低费用。对 API 应用，架构知识只能辅助理解，实际选择仍以任务质量、延迟、费用与服务约束为准。

#### 2. 面试口述版

稠密模型每个 token 通常经过同一套参数，MoE 则在某些层把计算分给多个专家，只激活其中一部分。这样总容量和每次实际计算量能够分开，但没有消除权重存储、专家间通信和负载均衡成本。专家也不是多个会独立调用工具的 Agent，它只是网络内部模块。Adaptive-RAG 不控制供应商模型的专家路由，只调用配置的模型接口，所以我不会根据模型别名猜当前总参数、激活参数或专家数量。比较模型时，我更关注同一业务集上的工具参数正确率、拒答边界和端到端延迟，再结合实际价格与运行条件，避免只凭架构名作结论。

#### 3. Adaptive-RAG实际实现

**项目未实现 MoE 网络或路由训练。** `Settings.deepseek_model` 是供应商模型标识，见 [app/config/settings.py:L39](../../app/config/settings.py#L39)；Provider 原样发送标识并保留返回 model，见 [app/providers/deepseek.py:L64](../../app/providers/deepseek.py#L64) 和 [app/providers/deepseek.py:L117](../../app/providers/deepseek.py#L117)。LangGraph 的条件路由是业务控制流，见 [app/agents/graph.py:L33](../../app/agents/graph.py#L33)，不等于 MoE token 路由。

#### 4. 面试官可能追问

- **追问：MoE 激活参数少，所以显存只需要放激活参数吗？** 答：不能这样推断。未激活专家也需存储或在设备间调度，具体资源取决于部署与并行方案。
- **追问：专家一定分别学会数学、代码和写作吗？** 答：不保证。路由与专长由训练形成，不能把可解释的业务标签当作必然分工。
- **追问：你的 Agent Router 是 MoE 吗？** 答：不是。它决定检索、工具等业务路径，不改变供应商神经网络内部的专家计算。

#### 5. 测试与证据

`test_provider_preserves_actual_model_and_finish_reason` 见 [tests/unit/test_p2_json_reliability.py:L39](../../tests/unit/test_p2_json_reliability.py#L39)。它验证返回元信息保留，不证明模型内部架构。当前具体供应商别名对应的权重/专家数未在本轮验证，没有训练或自建 MoE 性能数据。

<a id="q310"></a>
### Q310：大模型量化（4bit/8bit）对内存和效果的影响？

#### 1. 标准答案

量化用较低位宽近似权重或激活，可减少存储和部分带宽开销。仅从理论权重位数看，4bit/8bit 比 16bit 更小；实际显存还包含缩放参数、未量化层、KV Cache、临时张量及运行框架，不能按位宽比例承诺整机内存缩减。量化权重常在计算时转换或由专门低精度内核处理，支持与速度收益取决于硬件和实现。见 [Transformers bitsandbytes 官方说明](https://huggingface.co/docs/transformers/v4.46.0/quantization/bitsandbytes)。

效果风险包括数值误差、离群值、长文本及任务敏感性；应对目标任务检查工具参数、数学、引用和拒答，而不只看通用分数。QLoRA 是量化基础权重上的适配训练方案，不等于项目已经部署量化推理。

#### 2. 面试口述版

量化主要用较低位宽近似表示参数，能够省权重存储，但不能简单说四位就让整个服务显存变成原来的四分之一。缓存、激活、缩放信息和未量化部分仍占空间，速度还要看硬件有没有合适的内核。效果也不是必然不变，尤其要验证业务关心的数字、参数和边界判断。项目生成模型来自远程 API，应用看不到供应商实际精度，也没有自建四位或八位推理服务。若未来做本地部署，我会在相同数据和并发下比较内存峰值、首 token、吞吐与任务错误率，先通过正确性门槛，再判断省下的资源是否值得引入量化。

#### 3. Adaptive-RAG实际实现

**项目未实现生成模型量化部署。** `DeepSeekProvider` 通过 API 生成，见 [app/providers/deepseek.py:L29](../../app/providers/deepseek.py#L29)。本地 Embedding 的 `_load_sentence_transformer` 与重排 `_ensure_model` 是预训练模型加载，见 [app/providers/embeddings.py:L130](../../app/providers/embeddings.py#L130) 和 [app/providers/reranker.py:L74](../../app/providers/reranker.py#L74)；没有据此证明 4bit/8bit 配置、量化收益或供应商内部精度。

#### 4. 面试官可能追问

- **追问：量化一定更快吗？** 答：不一定。反量化、内核支持、批量和带宽都会影响结果；有时只是模型能放得下。
- **追问：权重量化后 KV Cache 自动也量化了吗？** 答：不是，两者是独立配置与误差来源；需要分别检查引擎支持和质量损失。
- **追问：如何发现业务质量退化？** 答：保留未量化基线，按错误类型对照工具参数、数字和长上下文案例，检查尾部失败而不只平均得分。

#### 5. 测试与证据

`test_cross_encoder_uses_injected_model` 使用假模型验证重排适配器，见 [tests/unit/test_reranker.py:L55](../../tests/unit/test_reranker.py#L55)。它不是量化实验。项目缺少量化前后显存、速度与业务效果证据，本轮没有下载模型或做推理基准。

<a id="q311"></a>
### Q311：推理部署吞吐、首Token延迟TTFT、Tokens/s如何测？

#### 1. 标准答案

先定义测量边界。端到端 TTFT 从客户端发起到收到首个有效生成 token，包含网络和排队；引擎 TTFT 可不含外部链路，不能混比。输出阶段速度可按输出 token 数与生成区间计算，但要说明首 token 是否计入、分母是否扣除 TTFT；流中多个 token 可能合并为一次网络块，不能用 chunk 数冒充 token 数。

吞吐是稳定时间段内成功请求数或有效输出 token 数/秒，同时报告并发、输入输出长度分布、错误率和延迟分位数。区分冷启动与预热、固定并发与固定到达率，避免只统计成功且短的请求。长连接和服务端排队也要计入观测范围。

#### 2. 面试口述版

我会先约定从哪里开始计时，首个什么才算 token。客户端 TTFT 包括网络和排队，引擎 TTFT 是另一口径；Tokens/s 也要明确是否扣除首 token 时间，不能把收到的数据块数当作模型 Token。压测要固定输入输出长度分布、并发或到达率，同时看成功吞吐、错误率和延迟分位数。项目的 SSE 先发节点进度，最终答案经过校验后才分段发送，所以第一个 started 或 token 事件都不能直接当供应商原始 TTFT。现有指标能看请求与阶段耗时，但没有自建推理引擎基准，我不会用一次历史演示耗时推导最大吞吐或线上容量。

#### 3. Adaptive-RAG实际实现

`REQUEST_LATENCY` 与 `STAGE_LATENCY` 是请求/阶段 Histogram，见 [app/observability/metrics.py:L10](../../app/observability/metrics.py#L10)。`ChatService.stream` 在校验并持久化后按答案字符切片发送，见 [app/services/chat_service.py:L175](../../app/services/chat_service.py#L175)。Provider 的流式方法存在，见 [app/providers/deepseek.py:L127](../../app/providers/deepseek.py#L127)，但当前前端聊天流不等于该供应商原始 token 直通。**项目未实现独立 TTFT/Tokens/s 压测报告。**

#### 4. 面试官可能追问

- **追问：第一条 SSE started 代表首 token 吗？** 答：不是，它只表示流程启动，模型可能还未完成推理，甚至尚未发出生成请求。
- **追问：一个请求每秒50 token，十并发就是500吗？** 答：不能线性推断。共享计算、内存带宽、排队和限额会改变速度，必须测稳态整体吞吐。
- **追问：为什么只报平均延迟不够？** 答：平均值掩盖慢请求与失败。需要分位数、超时率、输入长度与并发条件，才能判断用户体验和容量。

#### 5. 测试与证据

`test_chat_stream_emits_token_and_node_events` 断言拼接片段等于最终答案，见 [tests/e2e/test_chat_api.py:L50](../../tests/e2e/test_chat_api.py#L50)。它是离线协议测试，不是性能基准；当前吞吐、供应商 TTFT 与线上容量均未在本轮验证。

<a id="q312"></a>
### Q312：开源模型与API模型如何从成本、隐私、延迟选择？

#### 1. 标准答案

按约束和总成本比较。远程 API 降低模型部署与升级负担，但要考虑实际调用量、输入输出费用、配额、网络尾延迟、数据处理条款与可用性。本地开放权重方案可控制数据路径与版本，代价是硬件、利用率、运维、扩容和质量保障；开放权重也不自动意味着任意商业用途，需核对具体许可证。

在同一业务集合上比较工具选择、格式、检索证据使用、延迟与失败恢复；费用按真实请求放大、多轮和重试核算。隐私需要梳理日志、遥测和下载链路，本地模型不自动让整个系统离线。没有流量、合同和性能证据时，只能提出评估框架，不能断言某种方案最便宜。

#### 2. 面试口述版

我会先看数据能否出域，再看任务质量、延迟和长期总成本。API 适合快速接入和变化负载，但费用要按实际模型请求次数计算，不能只看一条用户消息；本地模型可控制数据与版本，却需要承担显卡、利用率、维护和扩容，许可证也要核对。项目生成接 DeepSeek，Embedding 与重排有本地可选适配，离线演示还有确定性替代路径，这几者的能力和证据必须分开。如果要迁移，我会固定任务集比较工具参数、引用和拒答表现，再测冷启动、尾延迟和资源成本。当前没有证明本地方案更省钱，也不能把调用私有知识库误称为数据完全没有发给供应商。

#### 3. Adaptive-RAG实际实现

`build_container` 根据配置选择 DeepSeek 或 Offline Provider，见 [app/services/container.py:L128](../../app/services/container.py#L128)；`build_embedding_provider` 选择远程、本地或 hash，见 [app/providers/embeddings.py:L213](../../app/providers/embeddings.py#L213)。`FaithfulnessChecker.check` 会把证据与工具文本放入模型请求，见 [app/guardrails/hallucination.py:L68](../../app/guardrails/hallucination.py#L68)，因此“私有”指访问隔离，不自动等于远程模型不见数据。项目未部署自托管生成大模型，也没有 API/本地 TCO 对照。

#### 4. 面试官可能追问

- **追问：只要模型本地运行就没有数据外发吗？** 答：不是。还要检查向量 API、遥测、日志和更新下载，按完整数据流验证。
- **追问：低流量为什么自建可能更贵？** 答：硬件与运维是固定成本，低利用率下单请求摊销高；API 按量付费可能更合适，但需实际价格与流量核算。
- **追问：切换模型只改 model 名称够吗？** 答：不够。上下文、JSON、思考模式、错误码与输出语义可能不同，需要兼容契约和业务回归。

#### 5. 测试与证据

`test_testing_env_skips_bge_m3_download` 见 [tests/unit/test_embeddings.py:L47](../../tests/unit/test_embeddings.py#L47)；`test_testing_env_skips_download` 见 [tests/unit/test_reranker.py:L69](../../tests/unit/test_reranker.py#L69)。这些验证测试模式行为，不是当前生产成本或隐私条款证据。本轮没有模型推荐采购、付费调用或部署比较。

<a id="q313"></a>
### Q313：模型能力、工具调用协议与API兼容性为什么要分开验证？

#### 1. 标准答案

模型能力关注能否理解意图、分解任务、选择正确工具与参数；工具协议关注名称、Schema、调用标识、参数类型及结果如何关联；API 兼容性关注端点、认证、消息字段、结构化输出、流式结束标记、超时和错误行为。三个维度可独立失败：HTTP 200 不保证参数正确，能写出工具名也不保证符合调用协议，协议完全兼容也不证明业务安全。

因此先做适配器契约，再做合法与恶意参数回归，最后在真实依赖和明确预算下验证业务效果。MockTransport 可以固定响应验证传输与异常映射，不能证明模型会自主选对工具或供应商当前可用。

#### 2. 面试口述版

我会把这三件事分别验。接口通了只说明请求能传过去，模型能写工具名也不代表参数对，更不代表有权执行。协议层要查 Schema、标识和结果关联，能力层要看真实问题能否选对工具，业务层还要看数据库结果和权限。项目主要让模型生成 JSON 计划，再由服务端注册表、Pydantic 和 Executor 校验执行，并不是已经接入供应商原生 tools 字段。MockTransport 能检查消息和思考模式兼容，不能替代真实模型规划效果；真实验收也只覆盖当时的场景，HITL 仍未运行。我会保留这几层独立证据，避免把兼容接口宣传成全部能力已验证。

#### 3. Adaptive-RAG实际实现

`DeepSeekProvider.generate` 发送 messages 与可选 response_format，没有发送 tools，见 [app/providers/deepseek.py:L63](../../app/providers/deepseek.py#L63)。`planner_node` 获取受限计划，见 [app/agents/nodes/planner.py:L339](../../app/agents/nodes/planner.py#L339)；`Tool.parse` 验证参数，见 [app/tools/base.py:L61](../../app/tools/base.py#L61)；`executor_node` 执行注册工具与幂等路径，见 [app/agents/nodes/executor.py:L120](../../app/agents/nodes/executor.py#L120)。项目提供工具 Schema 导出并不等于 Provider 已使用原生 tools 协议。

#### 4. 面试官可能追问

- **追问：OpenAI-compatible 为什么仍可能不兼容？** 答：兼容通常只是某个子集，思考参数、JSON 限制、流结束和错误码可能不同，要按实际使用字段逐条验证。
- **追问：Mock 都通过为什么真实还会错？** 答：Mock 固定了答案，不能覆盖模型规划波动、真实网络或供应商行为；真实业务测试还需校验副作用与费用。
- **追问：工具参数合法为什么仍拒绝执行？** 答：Schema 只约束结构，身份、订单归属、状态、确认和预算是独立执行条件。

#### 5. 测试与证据

`test_explicit_non_thinking_mode_reaches_json_and_stream_payloads` 见 [tests/unit/test_deepseek_thinking.py:L14](../../tests/unit/test_deepseek_thinking.py#L14)，属 MockTransport 契约；历史真实验收四项 PASS/HITL NOT_RUN 见 [2026-11-15 报告:L9](../../research/docs/agent_engineering_upgrade/deepseek_business_acceptance/REPORT.zh-CN.md#L9)。本轮未调用模型，也不把历史结果扩大为所有工具能力通过。

<a id="q314"></a>
### Q314：为什么模型输出不保证JSON正确？

#### 1. 标准答案

普通语言生成按 token 概率输出，不天然执行 JSON 语法或业务 Schema。提示要求 JSON 仍可能出现 Markdown、前后说明、未闭合括号、重复字段、错类型或截断。供应商 JSON 模式可能约束语法，但不等于满足完整业务 Schema，更不等于字段真实或有权执行；具体保证要查对应接口。

处理应分层：检查结束原因与完整性，解析 JSON，再做严格 Schema 和业务验证。只允许有限、可审计的格式修复或重试；不能把缺失订单号猜出来，也不要用 `eval` 执行模型文本。高风险动作应拒绝不完整输入，保留失败类型和 trace。

#### 2. 面试口述版

提示模型输出 JSON 只是要求，不是解析器保证。它可能加代码块、漏字段、给错类型，或者因为输出上限截断；即便 JSON 模式保证语法，也不能保证订单号真实或业务获准。项目先检查结束原因，再提取 JSON 对象，用 Pydantic 验证，最后走服务端权限和状态规则。解析器允许去除代码围栏、提取对象，但不能替模型补出关键业务事实。尤其 length 截断，即使表面能解析也会拒绝。我的处理重点是把格式错误、API 错误和业务拒绝区分开，并限制重试，避免一边反复收费，一边把错误输出修成看似合法的危险操作。

#### 3. Adaptive-RAG实际实现

`extract_json_object` 处理围栏、JSON 对象与解析错误，`parse_model` 再做模型校验，见 [app/providers/json_parser.py:L22](../../app/providers/json_parser.py#L22) 与 [app/providers/json_parser.py:L46](../../app/providers/json_parser.py#L46)。`DeepSeekProvider` 对结构化 length 结束拒绝，见 [app/providers/deepseek.py:L106](../../app/providers/deepseek.py#L106)。当前解析器不是重复键拒绝器或完整 JSON Schema 约束解码器；不能把认证注册表的重复键防护扩展为所有模型 JSON 都有同样保障。

#### 4. 面试官可能追问

- **追问：正则截取大括号是不是可靠 JSON 解析？** 答：不是。只能作为受限提取步骤，后面仍必须用 JSON 解析器和 Schema；嵌套、字符串大括号等会使简单正则不可靠。
- **追问：为什么不能自动补缺失 order_id？** 答：它是业务实体，猜测可能误操作其他订单；应澄清或拒绝，不能当格式修复。
- **追问：JSON 正确但字段是幻觉怎么办？** 答：去权威工具或数据库验证，按可信身份筛选；语法与 Schema 不能证明事实存在。

#### 5. 测试与证据

`test_structured_length_finish_is_rejected_without_retry` 验证完整外观与不完整 JSON 都不能绕过截断检查，见 [tests/unit/test_p2_json_reliability.py:L12](../../tests/unit/test_p2_json_reliability.py#L12)。`test_judge_distinguishes_invalid_output_from_api_error` 见 [tests/unit/test_p2_json_reliability.py:L66](../../tests/unit/test_p2_json_reliability.py#L66)。已有模拟测试，本轮未运行。

<a id="q315"></a>
### Q315：为什么LLM Judge可能和被评模型有共同偏差？

#### 1. 标准答案

Judge 与被评模型可能共享训练语料、架构倾向或相似偏好，因而共同相信某个错误事实；还可能偏爱更长、更像自身风格或位于某个位置的答案。换成另一模型可降低部分相关性，但不保证独立和正确。有关位置、冗长度与自我偏好的研究见 [Judging LLM-as-a-Judge](https://arxiv.org/abs/2306.05685)。

应把可程序验证项交给规则、SQL 和引用核验；主观项使用明确 rubric、匿名与交换顺序，抽样人工复审并检查分歧。Judge 出错、格式无效和证据不足应独立统计，不能默认作通过，也不能把“两个模型都同意”当作真实性证明。

#### 2. 面试口述版

Judge 也是模型，它可能和被评模型学过相似数据、偏爱相似表达，甚至一起相信同一个错误。它还可能更喜欢长答案或靠前选项，所以高一致率不等于客观正确。项目把答案和实际证据送给 FaithfulnessChecker，但生成与检查复用了同一个 Provider，这种相关性必须承认。我的改进方向是先用数据库、引用 ID 和规则验证可确定部分，再对主观项给清晰评分标准，交换顺序并人工抽查分歧。当前系统还把判定 API 失败、无效输出和证据不足分开，避免失败默认为通过；不过这些防护不等于已经消除了 Judge 的共同偏差。

#### 3. Adaptive-RAG实际实现

`build_graph` 将同一个 llm 传给生成节点与 `FaithfulnessChecker`，见 [app/agents/graph.py:L58](../../app/agents/graph.py#L58) 和 [app/agents/graph.py:L78](../../app/agents/graph.py#L78)。`FaithfulnessStatus` 区分证据与基础设施状态，见 [app/guardrails/hallucination.py:L16](../../app/guardrails/hallucination.py#L16)；`faithfulness_node` 对无效判定或 API 失败使用安全结果，见 [app/agents/nodes/faithfulness.py:L121](../../app/agents/nodes/faithfulness.py#L121)。**项目未实现独立异构 Judge 集成与系统性偏差校准。**

#### 4. 面试官可能追问

- **追问：用两个相同模型投票能消除错误吗？** 答：不能保证。相关错误会一起出现，重复采样也不等于独立证据。
- **追问：换更强的 Judge 就不用人工了吗？** 答：仍需校准。关键业务、分歧与低置信样本应人工复核，客观事实优先由程序验证。
- **追问：Judge 调用失败怎么算质量分？** 答：单列失败率，不能当 supported，也不能悄悄剔除后抬高成功率；要明确分母与降级行为。

#### 5. 测试与证据

`test_judge_distinguishes_invalid_output_from_api_error` 验证状态分离，见 [tests/unit/test_p2_json_reliability.py:L66](../../tests/unit/test_p2_json_reliability.py#L66)；`test_judge_allowance_is_explicit_and_no_extra_call` 见 [tests/unit/test_p2_json_reliability.py:L77](../../tests/unit/test_p2_json_reliability.py#L77)。这些不测 Judge 对人工标注的一致性或共同偏差，本轮未运行。

<a id="q316"></a>
### Q316：什么任务应交给传统规则/SQL而不是LLM？

#### 1. 标准答案

需要精确、稳定、可审计结果的任务优先交给确定性代码：身份与权限、金额运算、库存约束、订单状态机、唯一性、事务、幂等、预算准入及精确查询。LLM 适合理解自然语言、提出有限计划和组织证据，不应凭文本决定授权、退款金额或数据库提交成功。

分工可以是“模型建议意图与参数，Schema 验证形状，服务端验证事实和权限，SQL 事务执行动作，模型解释结果”。规则也应有版本、测试与可观察性；涉及模糊语义的环节可由模型辅助，但最终高风险不变量不能交给模型自由判断。

#### 2. 面试口述版

我的边界是需要精确和必须执行的不变量交给代码，语言理解和表达交给模型。订单归属、金额、是否允许取消、幂等与预算都不能靠提示词保证；模型可以提出查哪个订单，但查询和写入必须在服务端按当前身份执行。项目 Planner 输出有限计划，Executor 校验工具和确认状态，Repository 查询真实订单，事务最后统一提交。模型说已取消并不算证据，只有工具执行与数据库状态才算。另一个例子是配额，必须在共享存储里原子准入，不能让模型估计用户还剩多少。项目有库存字段，但没有完整下单扣库存流程，所以这部分只能作为设计原则讲。

#### 3. Adaptive-RAG实际实现

可信身份绑定见 `bind_identity` [app/core/auth.py:L114](../../app/core/auth.py#L114)；所有者约束见 `OrderRepository.get_visible_order` [app/repositories/order_repository.py:L37](../../app/repositories/order_repository.py#L37)。`cancel_order` 检查允许状态并写审计，见 [app/repositories/order_repository.py:L123](../../app/repositories/order_repository.py#L123)；执行器处理确认与幂等，见 [app/agents/nodes/executor.py:L165](../../app/agents/nodes/executor.py#L165)。**项目未实现完整的下单原子扣库存事务**，不能从 `ProductRow.inventory` 推导它已存在。

#### 4. 面试官可能追问

- **追问：模型已经判断用户是管理员，为什么还不行？** 答：身份与角色必须来自可信认证结果，模型文本和客户端字段都不能授予权限。
- **追问：规则很多会不会失去灵活性？** 答：固定不变量保护底线，模型在允许范围内处理语言变化；规则与模型各有职责，不必让所有意图都硬编码。
- **追问：模型答复成功但事务提交失败怎么办？** 答：不能发布成功结论；统一传播或转换为错误。SSE 进度不算完成证明，客户端需等待最终结果。

#### 5. 测试与证据

`test_order_is_scoped_to_owner` 见 [tests/integration/test_orders.py:L50](../../tests/integration/test_orders.py#L50)；`test_confirming_an_ineligible_cancel_cannot_mutate_or_write_audit` 见 [tests/unit/test_p4_independent_review.py:L26](../../tests/unit/test_p4_independent_review.py#L26)。这些验证已有权限/状态边界的断言，不是库存超卖测试，本轮未运行。
