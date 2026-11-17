# Agent 与 LangGraph 答案

本文件覆盖 Agent、LangGraph 与多 Agent 专题。本轮只读核对源码和既有测试定义，未运行模型、业务服务或数据库；历史验证与本轮检查分别说明。

<a id="q014"></a>
### Q014：Agent 与普通 LLM 应用、RAG、Workflow 的本质区别是什么？

★ 核心60

#### 1. 标准答案

普通 LLM 应用主要把输入映射为输出；RAG 在生成前增加可追溯外部证据，但检索本身不等于自主决策。Workflow 的次序、分支和终止条件由代码预先定义；Agent 把部分任务分解和动作选择交给模型，并利用环境反馈决策。它们可以组合，不能靠是否用了 LangGraph 或调用一次工具判定。工程上应说明模型能决定什么、执行器强制什么，以及失败时如何终止。

#### 2. 面试口述版

我会从控制权来区分。普通问答是模型直接生成，RAG 是先找证据再生成，Workflow 规定步骤和分支，Agent 把一部分任务拆解与工具选择交给模型。在 Adaptive-RAG 里这些并存：问候走直答，政策走检索，订单业务进入规划和执行。模型只提出计划，工具目录、实体约束、权限、确认和终止仍由代码控制。所以更准确的描述是固定图里包含受约束的 Agent 分支，而不是整个系统完全自主。这样既能处理组合问题，也能把取消订单这样的动作留在可审查的业务边界内。

#### 3. Adaptive-RAG实际实现

已实现混合编排。[build_graph](../../app/agents/graph.py#L45) 为 DIRECT、SINGLE、MULTI、AGENT、REFUSE 配置路径；[Planner.create_plan](../../app/agents/nodes/planner.py#L55) 生成工具计划。execute_tools 后直接进入生成，没有观察后回到 planner 的通用循环。项目未实现开放式自主 Agent 或生产多 Agent 团队。

#### 4. 面试官可能追问

- **追问：用了检索就算 Agent 吗？** 答：不算，固定检索后生成属于 RAG Workflow，需看是否把动作选择交给模型。
- **追问：为何不让模型直接取消订单？** 答：模型输出是不可信建议，取消必须经过服务端确认、权限和幂等校验。
- **追问：怎样证明 Agent 值得使用？** 答：同任务比较成功率、目标覆盖、工具选择、费用和延迟，并单列风险动作。

#### 5. 测试与证据

既有离线单测 [test_order_goes_agent](../../tests/unit/test_adaptive_router.py#L14) 检查路由；[test_real_shaped_planner_extra_step_is_pruned_only_for_status_request](../../tests/unit/test_p2q_planner.py#L110) 使用自定义 Provider 验证裁剪。本轮未运行，不能推导真实模型或线上 SLA。

<a id="q015"></a>
### Q015：Workflow 和 Agent 的优缺点是什么？什么时候用哪一个？

★ 核心60

#### 1. 标准答案

Workflow 流程确定、成本可估算、易测试审计，但开放任务的组合分支容易膨胀。Agent 适合输入多样、步骤难穷举的任务，却增加选择错误、调用波动和恢复难度。选型看任务不确定性与错误代价：稳定规则和资金操作优先确定流程；动态拆解的读任务可以使用受限规划。实践中常用确定骨架加局部模型决策；是否值得增加自主性，应由业务成功率、成本和失败案例决定。

#### 2. 面试口述版

我按任务的不确定性和错误代价选择。问候和明确政策检索不需要每次自由规划，用固定路径更便宜，也更容易定位失败。用户同时问订单金额、商品和物流时，模型规划能减少手写组合分支，但执行器必须验证所需工具与目标订单。涉及取消和退款，确认与事务仍走确定流程。项目采用固定图加受约束规划，模型失败可以退回 Skill 或读证据查询。它的收益需要和增加的 Schema、评测及安全维护成本一起比较，不能因为框架叫 Agent，就假设效果一定比 Workflow 好。

#### 3. Adaptive-RAG实际实现

已实现确定图与规划组合。[_route_after_complexity](../../app/agents/graph.py#L33) 选择固定路径；[Planner.create_plan](../../app/agents/nodes/planner.py#L55) 使用 Skill 目录和 JSON 计划，模型异常时退化。写确认在 [planner_node](../../app/agents/nodes/planner.py#L339) 单独处理。源码说明设计取舍，没有证明 Agent 全面优于 Workflow。

#### 4. 面试官可能追问

- **追问：何时完全不用 Agent？** 答：步骤稳定、规则明确且无需语义拆解时，确定流程更直接。
- **追问：模型规划失败怎么办？** 答：当前捕获模型输出或供应商异常后使用匹配 Skill，否则走知识或读证据回退。
- **追问：Agent 一定省代码吗？** 答：不一定，减少组合分支的同时增加校验、预算和评测成本。

#### 5. 测试与证据

既有离线 [test_greeting_goes_direct](../../tests/unit/test_adaptive_router.py#L7) 与 [test_status_only_skill_does_not_query_shipment_events](../../tests/unit/test_p2q_planner.py#L85) 覆盖简短路径及按需选工具。本轮只读核对，未重跑性能或模型对照实验。

<a id="q016"></a>
### Q016：LangGraph 为什么适合你的系统？为什么不用纯 Python if/else？

★ 核心60

#### 1. 标准答案

LangGraph 适合需要共享状态、条件路由和清晰执行边界的流程。显式图把阶段与跳转关系分开，便于逐节点测试和解释失败位置。纯 Python if/else 没有能力缺陷，简单流程使用它更直接；分支、状态和观测需求增加后，框架可减少编排样板。代价是额外依赖和框架语义，必须理解状态合并与持久化配置，不能把框架支持的能力当成项目已实现的功能。

#### 2. 面试口述版

这个系统有拒答、直答、检索、规划执行和忠实度检查，所以需要把阶段和跳转关系明确表达。LangGraph 提供共享 State 和条件边，便于观察是意图、检索还是工具阶段失败。纯 Python 完全能实现同样功能；如果只有两三步，我会优先简单代码。当前使用图主要为了维护和验证，不是框架天然让答案更正确。还要明确一个边界：项目只调用普通 compile，没有配置持久 checkpointer，因此不能把 LangGraph 支持的断点恢复能力当成已经完成的项目功能，也没有图与 if/else 的性能对照结果。

#### 3. Adaptive-RAG实际实现

已实现 [build_graph](../../app/agents/graph.py#L45) 的具名节点与条件边，[ChatService._stream_updates](../../app/services/chat_service.py#L336) 消费 updates。项目未实现图检查点持久化：[graph.compile()](../../app/agents/graph.py#L117) 没有 checkpointer。框架是编排选择，不是恢复或吞吐提升的实测证据。

#### 4. 面试官可能追问

- **追问：if/else 有什么做不了？** 答：没有本质限制，图主要让复杂编排显式化，并复用执行接口。
- **追问：用了图就能续跑吗？** 答：还要持久 checkpointer、线程标识和副作用去重，项目尚未配置该链路。
- **追问：怎样检验流式与普通请求一致？** 答：比较最终答案、工具事件及状态变化，流中的节点事件不应改变业务语义。

#### 5. 测试与证据

既有 Offline 集成测试 [test_service_graph_sse_privacy_and_disabled_parity](../../tests/integration/test_agent_tracing.py#L14) 覆盖服务、真实图和 SSE。本轮未运行，也没有 LangGraph 与 if/else 的性能实验。

<a id="q017"></a>
### Q017：LangChain 与 LangGraph 的定位和联系？

★

#### 1. 标准答案

LangChain 提供模型、工具和检索等应用组件；LangGraph 强调有状态执行与图编排。可以组合，也可在图节点直接调用自定义 Provider。选择依据是复用价值、契约和维护成本，使用框架不自动获得持久恢复或业务安全。

#### 2. 面试口述版

我按组件层和执行层解释：LangChain 提供模型应用组件，LangGraph 负责状态、节点和路由。项目直接用 StateGraph 编排自己的分类器、检索器、工具与 Provider，并没有把订单业务交给通用 Agent。这样复用图执行接口，又保留权限和确认边界。两者可以组合，但不需要为了框架完整性把所有模块重新包装。是否引入更多组件，要检查能减少多少适配代码、是否改变消息和错误契约，以及现有测试能否验证一致行为。当前没有两个方案的成本对照，也不能把依赖多寡当成质量证据。

#### 3. Adaptive-RAG实际实现

已实现 [build_graph](../../app/agents/graph.py#L45) 注入自定义组件，[ChatService](../../app/services/chat_service.py#L52) 组织业务调用。项目未实现额外的 LangChain 高层自主 Agent。图恢复能力仍受 [Q016](#q016) 所述限制。

#### 4. 面试官可能追问

- **追问：必须绑定使用吗？** 答：不必，图节点可以调用普通 Python 和自定义 Provider。
- **追问：为什么不直接复用完整 Agent？** 答：需要核对其权限、写确认和状态契约，框架选择不能绕过业务约束。

#### 5. 测试与证据

静态核对源码；既有 Offline [test_service_graph_sse_privacy_and_disabled_parity](../../tests/integration/test_agent_tracing.py#L14) 覆盖当前图服务。本轮未运行，无框架性能对照。


<a id="q018"></a>
### Q018：StateGraph 的 Node、Edge、Conditional Edge、State 分别是什么？

★ 核心60

#### 1. 标准答案

Node 是接收当前 State 并返回局部更新的计算单元；Edge 定义执行关系；Conditional Edge 根据状态计算下一节点；State 是一次图执行共享的数据契约。START、END 表示入口与终止。返回列表并不天然追加，合并策略由字段和 Reducer 决定。节点应围绕可观测职责拆分，路由函数尽量无副作用，不能把业务写操作藏在条件判断中。图结构也不自动带来循环、并发或持久恢复。

#### 2. 面试口述版

可以把图看成带数据契约的流程。State 保存问题、意图、检索证据、工具结果和答复；Node 完成一个阶段并返回更新；普通 Edge 规定下一步；条件边按状态选择分支。项目从安全检查开始，经过意图和复杂度路由，选择直答、检索、规划或拒答。比如 AGENT 进入 plan_tasks，随后 execute_tools，再生成并检查答案。关键不是方框数量，而是每个方框有明确输入输出、每条分支可验证，正常回答和拒答都能到达收尾节点。当前没有并行扇出或返回规划节点的循环，不能从框架名称推断这些能力。

#### 3. Adaptive-RAG实际实现

已实现 [AgentState](../../app/agents/state.py#L13) 和 [build_graph](../../app/agents/graph.py#L61) 的节点注册；[_route_after_complexity](../../app/agents/graph.py#L33) 返回路径名。普通边连接检索到生成、规划到执行；拒答进入 compact_memory。项目未实现并行 fan-out 或通用重规划回路。

#### 4. 面试官可能追问

- **追问：Node 必须调用模型吗？** 答：不必，规则校验、工具执行和记忆整理都可由代码完成。
- **追问：条件边可直接写数据库吗？** 答：不建议，把副作用放在可审计执行节点，使路由可复现。
- **追问：拒答为何还进入 Memory？** 答：统一当前轮消息收尾与压缩，不代表允许业务执行。

#### 5. 测试与证据

既有 [test_service_graph_sse_privacy_and_disabled_parity](../../tests/integration/test_agent_tracing.py#L14) 使用 Offline 服务检查真实图及节点事件。边关系经静态核对，本轮未运行，也未验证并行调度。

<a id="q019"></a>
### Q019：LangGraph 的 State 如何定义、更新与合并？Reducer 何时需要？

★ 核心60

#### 1. 标准答案

State 应区分业务输入、中间证据、控制字段和输出，并表达字段是否可缺失。Node 返回局部字典，未返回字段保留，返回字段按各自合并规则更新。没有 Reducer 的字段按更新替换；需要聚合多节点输出时才定义 Reducer，并考虑顺序、重复及并发冲突。消息追加也须有预算，避免无限累积。TypedDict 提供类型契约，外部输入和模型输出仍须运行时 Schema 校验。

#### 2. 面试口述版

项目用 total=False 的 TypedDict 定义 State，允许各阶段只填自己的字段。意图节点更新 intent 和 latency，执行器更新工具结果与步数，生成节点补最终答案。当前列表没有配置追加 Reducer，返回哪个键就替换哪个键；Memory 节点显式构造消息并控制压缩，避免隐式追加无限放大上下文。如果以后把多个读工具并行执行，就要重新定义结果如何聚合、重复如何消除，以及同键冲突如何处理，不能沿用串行假设。另外，TypedDict 不会自动拦住模型错误参数，计划和工具输入还要用 Pydantic 做运行时校验。

#### 3. Adaptive-RAG实际实现

已实现 [AgentState](../../app/agents/state.py#L13)，注释明确局部更新替换字段、没有无限追加 Reducer。[intent_node](../../app/agents/nodes/router.py#L22) 返回局部更新；[memory_node](../../app/agents/nodes/memory.py#L13) 显式构造 messages。项目未实现并发结果 Reducer；并行扩展需设计稳定去重键和合并规则。

#### 4. 面试官可能追问

- **追问：为什么不用 add_messages？** 答：当前选择显式控制历史和压缩；这不意味着该 Reducer 不可用。
- **追问：原地修改 State 内对象安全吗？** 答：应注意可变对象别名，返回新值更易推理；并行前必须审查这种共享。
- **追问：TypedDict 能校验模型参数吗？** 答：不能，当前计划通过 parse_model，工具参数通过 input_model 校验。

#### 5. 测试与证据

既有 [test_recent_user_entity_only_and_selective_node_views](../../tests/unit/test_context_builder.py#L13) 检查选择性上下文；[test_service_graph_sse_privacy_and_disabled_parity](../../tests/integration/test_agent_tracing.py#L14) 覆盖图与状态投影。本轮未运行，无并行 Reducer 测试结论。

<a id="q020"></a>
### Q020：你们的 Intent、Router、Retrieval、Generate、Faithfulness 和 Memory 节点为何这样分？

★ 核心60

#### 1. 标准答案

拆分应对应职责和失败边界：Intent 判断业务语义，Router 选择执行策略，Retrieval 获取证据，Generate 表达答案，Faithfulness 检查答案是否受证据支持，Memory 管理后续上下文。同一售后意图可能询问政策或操作订单，因此分类不能直接等同策略。拆分有利于独立评测与定位，但增加状态契约和模型调用成本，应避免只为增加节点数量而拆分。

#### 2. 面试口述版

六个节点分别回答：用户在问什么、该走哪条路、证据在哪里、如何表达、有没有超出证据、下一轮保留什么。最重要的是意图与策略分开，同样问退货，通用规则可以检索，具体订单则可能需要工具。生成消费本轮证据，忠实度负责检查和有限修正，记忆负责整理上下文，不把旧状态当最新业务事实。项目还有前置的上下文选择和摘要准备，不能误以为所有记忆都在末尾处理。这样出现错误时，可以区分分类、证据、执行和表达的问题；但每增加一次模型检查，也要计入延迟与成本。

#### 3. Adaptive-RAG实际实现

已实现节点注册 [build_graph](../../app/agents/graph.py#L61)；[router_node](../../app/agents/nodes/router.py#L31) 选择策略，[faithfulness_node](../../app/agents/nodes/faithfulness.py#L79) 对待确认等场景跳过检查。前置记忆在 [ChatService._initial_state](../../app/services/chat_service.py#L188)，收尾在 [memory_node](../../app/agents/nodes/memory.py#L13)。

#### 4. 面试官可能追问

- **追问：为什么意图不直接决定策略？** 答：业务类别和执行复杂度不同，一般政策与特定订单操作需要不同路径。
- **追问：忠实度失败会无限重写吗？** 答：不会，self_correct_answer 最多重写一次并复查，仍失败则保守回退。
- **追问：旧订单状态能直接用于下轮吗？** 答：不能，记忆提供实体线索，当前状态仍需本轮授权工具查询。

#### 5. 测试与证据

既有 [test_general_return_policy_does_not_request_order_tools](../../tests/unit/test_adaptive_router.py#L27) 检查策略边界；[test_self_correct_rewrites_unsupported_answer](../../tests/unit/test_self_correct.py#L27) 使用测试 Provider 验证修正。本轮未运行，单测不等于真实模型裁判质量。

<a id="q021"></a>
### Q021：工具调用是由 LLM 规划还是由图中的代码决定？如何划分控制权？

★ 核心60

#### 1. 标准答案

模型负责提出候选动作和参数，代码决定哪些工具可见、哪些计划有效、哪些操作可执行。边界包含白名单、Schema、实体来源、权限、预算、确认及幂等。模型输出不携带最终授权，自然语言“确认”也不能替代服务端审批对象。图安排阶段，执行器逐步校验，业务仓储继续检查资源归属与当前状态。声明了工具 Schema 不代表供应商原生 Function Calling 链路已接通。

#### 2. 面试口述版

我把控制权分成建议、校验和执行。模型看到 Skill 缩小后的目录，输出 JSON 计划；代码校验工具名、参数和订单来源，执行器再按风险处理。写操作先产生结构化提案，确认后服务端读取原提案，使用原工具和参数，避免模型在确认时改变目标。数据库仍检查资源归属和业务状态。当前不是供应商原生 tools 自动循环，而是文本 JSON 计划的受约束执行。这样模型保留拆解组合读任务的灵活性，权限、预算和不可逆动作由确定代码掌握。代码也必须为自己的校验规则建立测试，不能只靠 Prompt 要求模型听话。

#### 3. Adaptive-RAG实际实现

已实现 [Planner._tool_catalog](../../app/agents/nodes/planner.py#L44)、[_sanitize_plan](../../app/agents/nodes/planner.py#L188) 和 [executor_node](../../app/agents/nodes/executor.py#L120)。确认时 [planner_node](../../app/agents/nodes/planner.py#L339) 使用 confirmed_action 重建单步计划。当前 [DeepSeekProvider.generate](../../app/providers/deepseek.py#L51) 请求没有 tools 参数。

#### 4. 面试官可能追问

- **追问：模型能发明工具吗？** 答：工具名必须属于注册表与允许目录，否则被 sanitize 剔除。
- **追问：确认时用户提出另一个目标怎么办？** 答：已有结构化确认只作用于原提案，新目标需要新提案，不能覆盖原参数。
- **追问：Schema 合法就能执行吗？** 答：不能，还需权限、归属、业务状态、确认和幂等校验。

#### 5. 测试与证据

既有离线 [test_real_shaped_planner_extra_step_is_pruned_only_for_status_request](../../tests/unit/test_p2q_planner.py#L110) 验证计划约束；[test_cancellation_needs_explicit_request_and_confirmation](../../tests/unit/test_action_confirmation.py#L25) 验证原参数恢复。本轮未运行或请求真实模型。

<a id="q022"></a>
### Q022：ReAct 的 Thought/Action/Observation 循环是什么？与固定流水线有何区别？

★ 核心60

#### 1. 标准答案

ReAct 用推理指导动作选择，执行 Action 获取 Observation，再利用观察决定下一步或结束。不同于固定流水线，它的后续步骤会被环境反馈改变，适合证据逐渐显现的任务；代价是调用次数、失败传播和延迟更难预测。工程审计应记录动作与结果，无需依赖展示模型私有思维链。循环必须有预算和明确终止条件，危险动作仍受外部权限与确认控制。

#### 2. 面试口述版

ReAct 的关键是根据工具观察重新决定下一步，而不是在 Prompt 里写上三个英文词。比如查物流失败后，模型根据观察选择查订单或请用户补信息；固定流水线则预先规定回退。项目里要区分概念和实现：当前先生成有限计划，再顺序执行，读失败有代码回退，结果交给生成，图不会回到规划节点。因此它不是完整的逐步 ReAct 循环，而是有界规划执行。这个选择控制了客服延迟和调用成本。未来若增加观察后重规划，要先补总预算、重复读处理、终止条件和写审批绑定，再用任务成功率验证收益。

#### 3. Adaptive-RAG实际实现

部分实现 Agent 式规划；项目未实现通用 ReAct 回路。[build_graph](../../app/agents/graph.py#L110) 为 plan_tasks → execute_tools → generate_answer；[execute_with_fallback](../../app/agents/nodes/executor.py#L60) 是代码定义的读回退，不是模型观察后重规划。应称有界 Plan-and-Execute，不能宣称无限自主思考。

#### 4. 面试官可能追问

- **追问：读失败换工具为何不算 ReAct？** 答：这里由代码确定回退关系，没有把观察交回模型重新选动作。
- **追问：不展示 Thought 如何审计？** 答：记录工具、参数摘要、结果状态、策略和终止原因即可。
- **追问：加入循环先做什么？** 答：先限制总调用、时间和 Token，再验证去重及副作用安全。

#### 5. 测试与证据

既有 [test_read_tool_falls_back_to_knowledge](../../tests/unit/test_executor_fallback.py#L37) 验证固定回退；[test_deterministic_business_rejection_never_repeats_owner_lookup](../../tests/unit/test_p2q_planner.py#L44) 验证业务拒绝不绕路。本轮未运行，没有 ReAct 对照实验。

<a id="q023"></a>
### Q023：如何限制 Agent 最大迭代轮数、避免死循环、重复工具调用？

★ 核心60

#### 1. 标准答案

预算要覆盖总轮数、单轮工具数、时间和 Token，并在外部调用前检查。去重不能只看工具名，应结合规范化参数、目标及结果是否成功。成功的相同读可在本轮复用；临时失败允许受限修复；权限或确定业务拒绝不应绕路重试。写操作必须由业务幂等与事务去重，内存集合不足。预算耗尽时应交代未完成子目标，不能伪造成功；循环退出也应有可观测原因。

#### 2. 面试口述版

当前图没有回到 planner 的循环，所以主要风险是有限计划中的重复调用。模型计划最多保留六步，执行器检查 max_tool_calls 和 max_agent_steps，再按工具加参数指纹去掉成功读的重复项。写操作前清空读缓存，避免写后继续用旧状态；确定性的越权或不存在也不能换个接口绕过，临时读失败保留有限回退。写入另靠确认 ID 和数据库幂等记录。这里还要讲清边界：step_count 在执行结束才累加，单次循环主要靠 max_tool_calls 约束，不能说已经具备跨多轮重规划的统一总预算或完整截止时间。

#### 3. Adaptive-RAG实际实现

已实现 [_sanitize_plan](../../app/agents/nodes/planner.py#L188) 的六步裁剪；[executor_node](../../app/agents/nodes/executor.py#L120) 有次数限制、seen_reads、read_cache 和 hidden_orders。max_agent_steps 比较传入 step_count，本轮 calls 最后合入。项目未实现跨 ReAct 多轮的统一截止时间；写重复另由幂等仓储处理。

#### 4. 面试官可能追问

- **追问：同一工具不同订单能去重吗？** 答：不能，指纹含参数，两个订单是不同证据目标。
- **追问：失败读也一律缓存吗？** 答：不应，临时失败应允许有限修复，确定业务拒绝才应阻止绕路。
- **追问：写后查询可复用旧结果吗？** 答：不能，写操作是新鲜度屏障，当前代码清空读缓存与去重集合。

#### 5. 测试与证据

既有 [test_transient_read_failure_keeps_fallback_and_fresh_next_turn](../../tests/unit/test_p2q_planner.py#L63) 验证跨轮重读；[test_repeating_one_target_does_not_cover_two_distinct_required_targets](../../tests/unit/test_tool_scoring_v2.py#L115) 验证多目标计分。本轮静态核对，未重跑边界测试。

<a id="q024"></a>
### Q024：LangGraph 的条件路由如何实现？如何处理无效路由输出？

#### 1. 标准答案

条件路由读取经校验的状态，输出有限目标名并通过显式映射关联节点。模型类别要先通过 Schema，再映射路径。缺失、非法和低置信度应区别处理；异常通常应拒绝、澄清或保守回退，不能拼接任意节点名。路由计算宜无副作用。

#### 2. 面试口述版

项目先获取结构化意图与复杂度，再用代码把策略映射为图节点，不让模型任意输出一个名称就跳转。缺失策略默认 SINGLE，但这不代表任何非法值都有安全回退：当前映射直接按枚举取值，异常 State 混入未知内容仍可能报错。我会如实说明这个边界，改进时在入口校验，并为不可识别策略定义明确拒绝或澄清。条件边只负责判断，业务写交给执行器。测试应覆盖全部合法路径、字段缺失和损坏值，而不是一个正常订单查询通过，就推断整个路由对异常状态都健壮。

#### 3. Adaptive-RAG实际实现

已实现 [_route_after_complexity](../../app/agents/graph.py#L33) 与 [build_graph](../../app/agents/graph.py#L100) 的固定映射；缺失值默认 SINGLE，未知值没有全面保护。[ComplexityResult](../../app/schemas/agent.py#L17) 约束模型输出。项目未实现任意损坏 State 的统一恢复。

#### 4. 面试官可能追问

- **追问：默认路径会掩盖错误吗？** 答：可能，应记录默认触发原因，非法值不宜静默当正常检索。
- **追问：能直接采用模型节点名吗？** 答：仍需有限白名单和类型校验，不能开放任意跳转。

#### 5. 测试与证据

既有离线 [test_greeting_goes_direct](../../tests/unit/test_adaptive_router.py#L7) 与 [test_order_goes_agent](../../tests/unit/test_adaptive_router.py#L14) 覆盖合法策略。本轮未运行，也不等于非法 State 测试完备。


<a id="q025"></a>
### Q025：Command、Send 及并行分支在什么场景使用？

#### 1. 标准答案

Command 可组合状态更新与路由，也可用于中断恢复；Send 按运行时数据给目标节点分发不同输入，适合动态 map-reduce。固定独立工作也可用普通边并行。汇聚需明确 Reducer、失败策略和共享预算。[官方 Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api) 给出这些机制的区别。

#### 2. 面试口述版

节点既要更新状态又决定下一跳，可以考虑 Command；按运行时子任务动态分发输入，可以考虑 Send。两个固定独立的读任务则未必需要动态机制。关键难点在结果汇聚：如何去重、一个分支失败是否保留其他证据、预算如何共享，以及是否有依赖或副作用。项目当前没有 Command、Send 或并行工具节点，因此这些只能作为设计说明。若增加并行，我会先选独立只读能力，定义稳定结果键和失败策略，再比较总延迟、配额与排队影响。当前 State 没有对应 Reducer，不能把串行实现直接并发化。

#### 3. Adaptive-RAG实际实现

项目未实现 Command/Send 和图上并行分支。[build_graph](../../app/agents/graph.py#L45) 使用普通节点和条件边；[AgentState](../../app/agents/state.py#L13) 无并行聚合 Reducer。建议先设计结果合并与预算，不把框架支持当已落地。

#### 4. 面试官可能追问

- **追问：Send 就是多 Agent 吗？** 答：不是，它是分发机制，目标也可以是普通函数。
- **追问：并行必然快吗？** 答：不一定，配额、排队、失败与汇聚都可能抵消收益。

#### 5. 测试与证据

静态核对当前图；既有 [test_service_graph_sse_privacy_and_disabled_parity](../../tests/integration/test_agent_tracing.py#L14) 只覆盖现有串行 Offline 链路。本轮未运行，无 Command/Send 项目测试。


<a id="q026"></a>
### Q026：什么是 Plan-and-Execute？与 ReAct 比较延迟、可控性、失败恢复。

#### 1. 标准答案

Plan-and-Execute 先规划一组步骤再执行，便于提前审查和控制预算，但面对未知观察可能失效；ReAct 按每次观察决定后续动作，适应性较好却增加模型往返。二者都应有界，也可组合有限重规划。固定代码 fallback 不等于模型观察后再规划。

#### 2. 面试口述版

当前更准确的名称是有界 Plan-and-Execute：先根据问题和目录生成计划，再顺序执行，最后组织答案。好处是可以提前校验工具、参数与风险，延迟比较容易估计；缺点是后续计划不能充分适应未知观察。项目用读回退和保守回答应对失败，没有回到规划节点。它也不是一定比 ReAct 便宜，错误计划会浪费工具与生成调用。我会在同任务上比较成功率、模型往返、实际工具事件及总耗时。如果任务确实依赖前一步观察，再考虑有限重规划，同时保留原审批目标、参数和幂等约束。

#### 3. Adaptive-RAG实际实现

已实现 [Planner.create_plan](../../app/agents/nodes/planner.py#L55)、[executor_node](../../app/agents/nodes/executor.py#L120)；[execute_with_fallback](../../app/agents/nodes/executor.py#L60) 为固定读回退。项目未实现观察后模型重规划，区别见 [Q022](#q022)。

#### 4. 面试官可能追问

- **追问：后一步参数依赖前一步怎么办？** 答：需要显式依赖解析或有限重规划，当前不能声称支持任意动态依赖。
- **追问：可以重跑整个计划吗？** 答：写操作先查幂等结果，不能盲目重放；读也需考虑新鲜度。

#### 5. 测试与证据

既有测试 Provider [test_real_shaped_planner_extra_step_is_pruned_only_for_status_request](../../tests/unit/test_p2q_planner.py#L110) 与工具替身 [test_read_tool_falls_back_to_knowledge](../../tests/unit/test_executor_fallback.py#L37) 验证当前机制。本轮未运行，无模式间延迟对照。


<a id="q027"></a>
### Q027：反思 Reflection 节点什么情况下能提升质量，什么情况下只是浪费 Token？

#### 1. 标准答案

Reflection 需要可靠失败信号和可验证修正，如工具错误、遗漏目标或证据不支持的断言。没有新证据的自评可能强化偏差并浪费 Token。应限制次数，分开候选生成与批准，以冻结集和实际环境状态衡量净收益；不能未经审核把经验变成生产规则。

#### 2. 面试口述版

反思前先问有没有新信息。工具错误类型、缺失目标或不支持断言能指导具体修正；只让同一模型再想一遍，可能把错误写得更自信。项目生产图有忠实度检查和最多一次改写，不是无限 Reflection；另有隔离经验模块把结构化失败转成候选，也不代表生产会自动学习。我会记录修正前后的证据、工具与环境状态，把额外 Token 和成功收益一起比较。高风险操作中反思只能建议，不能生成审批或扩大权限。没有新证据、连续无改善或达到预算就应停止，并明确未解决目标。

#### 3. Adaptive-RAG实际实现

部分实现：[self_correct_answer](../../app/agents/nodes/faithfulness.py#L21) 至多一次改写；[reflect](../../app/experience/reflection.py#L141) 生成隔离经验候选。项目未实现生产自动反思学习回路，候选不自动批准，也不是多 Agent 自我进化。

#### 4. 面试官可能追问

- **追问：同模型自评有何风险？** 答：共享偏差，需工具/环境事实及独立冻结评测约束。
- **追问：什么时候该停？** 答：无新证据、无改善或预算耗尽时停止，不能用重复思考代替证据。

#### 5. 测试与证据

既有 [test_self_correct_rewrites_unsupported_answer](../../tests/unit/test_self_correct.py#L27) 用测试 Provider；[test_verified_structural_failure_reflects_safe_principle](../../tests/unit/test_s1ex_reflection.py#L17) 是隔离经验单测。本轮未运行，不证明真实反思净收益。


<a id="q028"></a>
### Q028：如何做动态工具选择与工具集合裁剪？

#### 1. 标准答案

选工具先按可信权限过滤，再按任务能力召回候选，向模型提供少量相关描述和完整 Schema，执行前再次校验。裁剪必须保留所有子目标所需能力，不能因强分类丢掉陌生任务。工具召回、最终选择和授权安全应分别评估；不确定不能成为扩大写权限的理由。

#### 2. 面试口述版

我把权限过滤和相关性过滤分开。项目用 Skill 触发词与意图映射缩小目录，同时根据问题保留订单、商品、物流等读能力，模型在候选中规划，执行前再验证注册名、参数和实体来源。风险是裁剪过头，比如只留下订单头而丢掉物流轨迹，或只适配熟悉表达而遗漏新子目标。因此不能只看目录变短，要看必需工具是否仍可选、全部目标有没有证据。当前没有向量化工具搜索。规模增加后可以增加检索层，但仍要先限权、保留必要能力，并在无匹配时澄清，而不是把全部写工具重新暴露。

#### 3. Adaptive-RAG实际实现

已实现 [match_skill](../../app/skills/loader.py#L37)、[_allowed_tools](../../app/agents/nodes/planner.py#L160)、[_sanitize_plan](../../app/agents/nodes/planner.py#L188)。当前是 Skill 与能力规则裁剪，项目未实现语义工具搜索。规模设计见 [Q329](#q329)。

#### 4. 面试官可能追问

- **追问：先语义召回再授权可以吗？** 答：执行前必须授权，可见目录也应尽量先限制，相关不等于有权。
- **追问：如何发现裁剪过度？** 答：用多目标和陌生表达检查必需工具召回与实际目标覆盖。

#### 5. 测试与证据

既有测试输出 [test_real_model_keeps_capabilities_for_unrecognized_additional_obligations](../../tests/unit/test_p2r_decision.py#L243) 和离线 [test_logistics_evidence_remains_available](../../tests/unit/test_p2q_planner.py#L102) 检查能力保留。本轮未运行。


<a id="q029"></a>
### Q029：如何在图上实现失败重试、fallback、超时与终止条件？

#### 1. 标准答案

把失败分成可重试传输错误、确定业务拒绝和不确定副作用。重试设置上限、退避与总截止时间；fallback 必须保持业务语义和权限；写请求不确定时先查结果。图中终止既可由明确结束边，也可由预算判断完成。框架重试、供应商重试与工具重试是不同层，不能叠加失控。

#### 2. 面试口述版

我先分类失败，再决定在哪一层处理。供应商短暂超时或限流可以有限退避，参数错误和越权不该重试；读工具暂时失败可走语义明确的回退，但回退查到订单头不能当成物流轨迹完成。写工具超时必须先查实际结果和幂等记录，不能直接换工具补写。当前图没有重规划循环，执行器按有限计划和次数结束，生成后忠实度最多修正一次。完整跨图截止时间与统一取消尚未实现，因此不能说所有层都受一个总超时控制。后续应把预算贯穿模型、工具和回退，防止每层单独重试放大总耗时。

#### 3. Adaptive-RAG实际实现

部分实现：[execute_with_fallback](../../app/agents/nodes/executor.py#L60) 处理读回退，[executor_node](../../app/agents/nodes/executor.py#L147) 限制次数；[DeepSeekProvider.generate](../../app/providers/deepseek.py#L51) 有供应商错误处理。项目未实现图级统一总截止时间，普通图路径最终到 END。

#### 4. 面试官可能追问

- **追问：越权能换个工具再试吗？** 答：不能，确定业务拒绝不能通过回退绕开。
- **追问：各层三次重试有何问题？** 答：可能乘法放大调用与费用，需共享总预算并明确重试责任层。

#### 5. 测试与证据

既有 [test_deterministic_business_rejection_never_repeats_owner_lookup](../../tests/unit/test_p2q_planner.py#L44) 与 [test_transient_read_failure_keeps_fallback_and_fresh_next_turn](../../tests/unit/test_p2q_planner.py#L63) 分别验证拒绝和暂态回退。本轮未运行。


<a id="q030"></a>
### Q030：Graph State 与数据库持久会话、LLM Context 有何区别？

#### 1. 标准答案

Graph State 是一次执行的工作数据；数据库会话保存跨请求的原始事件或业务记录；LLM Context 是某次模型请求实际序列化进去的内容。三者既不等量也不等权。持久化消息不代表模型读到，State 字段也不保证保存或进入 Prompt。应分别验证保存、恢复、选择和最终请求预算。

#### 2. 面试口述版

我用三张清单来区分：数据库实际保存什么，图当前持有什么，模型这次真正看到了什么。数据库可能有几十轮消息，State 只加载部分窗口；规划器或生成器又只获得选择后的实体、摘要和当前证据，不会自动看到 State 全部字段。项目 M0 即使加载二十条消息，也不能由此说每个节点都用了历史。反过来，State 中的工具结果不一定全部持久保存为检查点。排障要追到实际 Prompt 和来源边界，同时避免把原文写入公开 Trace。这个区分能解释为什么“数据库有订单号”仍可能无法消解指代。

#### 3. Adaptive-RAG实际实现

已实现 [ChatService._initial_state](../../app/services/chat_service.py#L188) 从 SQL 构建 State；[SelectedContext.prompt_context](../../app/memory/context.py#L57) 选择节点输入；[ChatService._persist](../../app/services/chat_service.py#L347) 保存消息与摘要。项目未实现整个 State 的图检查点持久化，参见 [Q124](03_Tool_MCP_Memory_HITL_答案.md#q124)。

#### 4. 面试官可能追问

- **追问：State 有 secret 会自动进入模型吗？** 答：不会自动，但任何序列化路径都需白名单，不能依赖未使用字段碰巧安全。
- **追问：聊天保存成功是否说明下轮能用？** 答：不说明，还要验证读取窗口、选择器和实际节点输入。

#### 5. 测试与证据

既有 Recording Provider [test_generation_prompt_uses_current_tools_and_excludes_assistant_claims](../../tests/unit/test_context_builder.py#L54) 检查真实输入；[test_state_projection_has_no_raw_prompt_arguments_or_credentials](../../tests/unit/test_web_workbench.py#L34) 检查投影。本轮未运行。


<a id="q031"></a>
### Q031：什么是 checkpoint 和 thread_id，如何断点恢复？

★ 核心60

#### 1. 标准答案

Checkpoint 保存图的状态和执行进度，thread_id 把同一逻辑执行的检查点关联起来，不等于用户身份或权限。恢复需要持久存储、正确线程配置、可序列化状态及恢复入口，还要处理工具执行与检查点写入之间的崩溃窗口。外部副作用仍需幂等或事务，不能假设恢复只执行一次。保存会话消息只支持重建上下文，不等于恢复任意节点位置；恢复请求也必须校验线程归属。

#### 2. 面试口述版

我先区分保存聊天历史、保存业务提案和保存图检查点。LangGraph checkpoint 可以记录执行进度，thread_id 用来找到同一线程，但它不是用户授权。项目当前有数据库会话与可跨实例读取的待确认提案，确认时重新构造一次请求；图只是普通 compile，没有持久 checkpointer 或 interrupt/resume。所以不能说项目已支持任意节点断点恢复。若补齐这项能力，需要选持久检查点存储、把线程绑定验证身份，并测试工具成功但检查点尚未写入的崩溃窗口。否则即使恢复了状态，也可能重复取消或退款。

#### 3. Adaptive-RAG实际实现

项目未实现 LangGraph checkpoint/thread_id 恢复：[build_graph](../../app/agents/graph.py#L117) 无 checkpointer，[ChatService._invoke](../../app/services/chat_service.py#L321) 直接 ainvoke(state)。已实现 [ChatService._persist_pending](../../app/services/chat_service.py#L256) 和 [_load_confirmation](../../app/services/chat_service.py#L272) 的 SQL 提案恢复，不能混称图断点。

#### 4. 面试官可能追问

- **追问：session_id 能当 thread_id 吗？** 答：可作为映射的一部分，但须绑定身份与检查点存储，当前图没有这样配置。
- **追问：有聊天历史为何不能续跑节点？** 答：历史不包含完整执行游标、待执行任务及中间状态，只能重建新请求。
- **追问：checkpoint 保证写工具恰好一次吗？** 答：不能，外部写与检查点之间仍可能崩溃，需要业务幂等。

#### 5. 测试与证据

既有 SQLite 集成 [test_confirmation_survives_service_replacement_and_binds_identity](../../tests/integration/test_durable_confirmation.py#L25) 检查业务提案跨实例和归属；[test_uncommitted_proposal_cannot_be_confirmed](../../tests/integration/test_durable_confirmation.py#L61) 检查回滚提案。它们不是 LangGraph 恢复测试，本轮未运行。

<a id="q032"></a>
### Q032：interrupt 与 resume 如何实现 HITL？恢复后如何防重复执行？

#### 1. 标准答案

图级 HITL 以持久 checkpointer 保存状态，interrupt 暂停等待输入，再用同一线程与 Command(resume=...) 恢复。恢复会涉及节点重新执行，因此中断前副作用应避免或幂等。审批对象仍须由服务端保存并绑定主体及原参数，不能以 resume 内容自动授权。[官方 interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) 说明暂停与恢复机制。

#### 2. 面试口述版

概念上先给图配置持久检查点，在审批节点 interrupt 返回可展示提案，用户确认后用原 thread_id 和 resume 输入恢复。不能忽略节点可能重新执行，特别是中断前已经发出的外部动作，必须单独去重或先查结果。项目当前不是这条路径：只有 SQL 保存待确认动作，确认后新请求加载原记录并重建单步计划，没有 LangGraph interrupt 或 resume。因此我会把框架方案与已实现业务 HITL 分开讲。未来接图恢复时也不能删掉现有身份、TTL 和幂等检查，检查点只保存进度，不会替代审批安全。

#### 3. Adaptive-RAG实际实现

项目未实现 LangGraph interrupt/resume：[build_graph](../../app/agents/graph.py#L117) 普通 compile。已实现 [ChatService._load_confirmation](../../app/services/chat_service.py#L272) 和 [planner_node](../../app/agents/nodes/planner.py#L339) 从 SQL 原提案恢复业务执行。详细业务流程见 [Q175](03_Tool_MCP_Memory_HITL_答案.md#q175)。

#### 4. 面试官可能追问

- **追问：resume=True 就代表获批吗？** 答：不能，必须先验证调用者及所批准的原动作。
- **追问：中断前发邮件安全吗？** 答：恢复可能重执行，应把副作用移到批准后或用稳定幂等记录。

#### 5. 测试与证据

既有 SQLite [test_confirmation_survives_service_replacement_and_binds_identity](../../tests/integration/test_durable_confirmation.py#L25) 只验证业务提案恢复，不是图恢复。本轮未运行；历史真实 HITL 仍为 NOT_RUN。


<a id="q033"></a>
### Q033：多节点并发读写共享 State 会有什么冲突？

#### 1. 标准答案

多个节点同时更新同键可能触发冲突或不确定覆盖；列表合并也可能重复、丢序或放大状态。应尽量让分支写独立键，以确定且符合语义的 Reducer 聚合结果，明确重复和失败处理。可变对象共享还会绕过表面合并契约。数据库连接与事务不能因为同在 State 就安全共享。

#### 2. 面试口述版

并行不是把两个协程放进去就结束。若同时改 tool_results，结果可能冲突；直接追加又可能重复，按完成顺序合并也不一定符合计划顺序。应让每个分支返回带稳定目标键的结果，由汇聚节点按规则去重、排序，并保留失败。预算和取消也要共享约束，数据库会话不能随意跨并发任务使用。当前项目图是串行，AgentState 没有并行 Reducer，所以我不会说已经解决了这些问题。新增并发前先把可变 latency 等对象更新改为清晰契约，测试结果与调度顺序无关，再讨论并行收益。

#### 3. Adaptive-RAG实际实现

项目未实现多节点并发写 State。[AgentState](../../app/agents/state.py#L13) 默认替换字段，[executor_node](../../app/agents/nodes/executor.py#L147) 顺序执行。建议用分支独立输出与汇聚节点，而非直接并发修改现有列表；现有上下文身份隔离也不等于 State 合并已安全。

#### 4. 面试官可能追问

- **追问：Reducer 用列表相加够吗？** 答：未必，还要考虑重放重复、目标键和确定顺序。
- **追问：一个 AsyncSession 能给两个任务共用吗？** 答：不能仅凭异步就认为安全，应按数据库库的事务并发约束隔离会话。

#### 5. 测试与证据

既有 [test_request_identity_context_isolated_and_reset](../../tests/unit/test_long_term_memory.py#L69) 只测 ContextVar 身份并发隔离，不测图 State 合并。本轮未运行，没有并行图测试证据。


<a id="q034"></a>
### Q034：图执行到一半进程崩溃，恢复时已发出的外部动作如何判定？

#### 1. 标准答案

崩溃恢复先区分未派发、已确认失败、成功已持久化和结果不确定。外部请求发出后未落结果不能当未执行，需通过幂等键或供应商查询核对；无法确定则暂停并交人工，不能盲目重放。业务状态、审计和动作结果应有一致提交边界。检查点只记录已保存进度，不保证外部动作恰好一次。

#### 2. 面试口述版

最危险的是外部动作已经成功，但进程在保存结果前崩溃。恢复时仅看本地没有成功记录就再发一次，可能重复退款。所以要记录稳定动作 ID、派发状态和可查询的外部引用；同键重试或状态查询确认结果，仍不确定就停止。项目当前本地订单写、审计与幂等用同一数据库事务，降低本地提交窗口，但没有通用外部动作恢复协议，也没有图检查点。付费模型账本对 pending 和 uncertain 会阻止继续派发，这是特定调用的保守机制，不能扩展宣称所有业务工具都已具备同样的恢复能力。

#### 3. Adaptive-RAG实际实现

部分实现：[IdempotencyRepository](../../app/repositories/idempotency.py#L14) 保存本地动作结果，[ChatService._commit](../../app/services/chat_service.py#L343) 提交。项目未实现通用外部业务动作状态机或图恢复；同一确认重放见 [Q176](03_Tool_MCP_Memory_HITL_答案.md#q176)，不同动作并发仍需另审查。

#### 4. 面试官可能追问

- **追问：找不到幂等结果能直接重发吗？** 答：不能，若请求可能已经发出，应先查询外部实际结果。
- **追问：本地事务可以回滚外部退款吗？** 答：不可以，需要外部幂等或补偿/对账方案。

#### 5. 测试与证据

既有 SQLite [test_refund_is_idempotent_and_transactional](../../tests/integration/test_orders.py#L34) 检查本地事务；[test_unknown_and_uncertain_attempts_fail_closed](../../tests/unit/test_paid_budget.py#L152) 只测模型付费账本。本轮未运行，无外部退款恢复验收。


<a id="q035"></a>
### Q035：静态 Workflow 能不能使用 LangGraph？为什么二者不是互斥选项？

#### 1. 标准答案

Workflow 描述控制权由预设规则决定，LangGraph 是表达和执行这种控制流的工具。固定顺序、条件分支甚至确定的有限循环都可用图实现；是否 Agent 取决于模型是否选择动作，而非用了什么框架。应避免为简单流程引入不必要复杂度，但也不应把静态图与框架视为互斥。

#### 2. 面试口述版

静态 Workflow 完全可以用 LangGraph。Workflow 描述谁决定步骤，LangGraph 提供节点、状态和边，两者不是同一维度。项目有固定安全检查和收尾路径，也有模型参与的规划分支，所以整体并不是纯自主 Agent。即使把规划器换成完全确定的 Skill 模板，仍然可以保留同一张图。选择框架的理由是边界、观测和维护，不是为了让产品获得一个 Agent 标签。面试时我会沿一条政策查询路径画出固定节点，再说明订单分支哪里允许模型建议，哪里由代码硬约束，这比笼统说“全链路自主”更可验证。

#### 3. Adaptive-RAG实际实现

已实现 [build_graph](../../app/agents/graph.py#L89) 的预设边和条件边；[Planner.create_plan](../../app/agents/nodes/planner.py#L71) 在 Offline 模式使用确定 Skill 计划。项目证明图可容纳固定流程，未证明所有请求都需要模型规划。选型比较见 [Q015](#q015)。

#### 4. 面试官可能追问

- **追问：条件边一定是 Agent 决策吗？** 答：不是，可以完全由代码读取枚举或规则决定。
- **追问：去掉 LLM 后图还成立吗？** 答：可以，只要节点输入输出契约保持一致。

#### 5. 测试与证据

既有离线 [test_greeting_goes_direct](../../tests/unit/test_adaptive_router.py#L7) 和 [test_cancellation_needs_explicit_request_and_confirmation](../../tests/unit/test_action_confirmation.py#L25) 体现确定路由及模板规划。本轮未运行。


<a id="q036"></a>
### Q036：如何在单 Agent 与多 Agent 之间做技术取舍？

#### 1. 标准答案

优先单 Agent，只有任务可分解、上下文或权限确需隔离且存在独立验证/并行收益时再拆多 Agent。多角色名称不代表收益，拆分会增加通信、重复上下文、汇聚和错误传播。评估应固定目标，比较端到端成功、安全、成本和延迟，保留简单方案作为对照。

#### 2. 面试口述版

我先从单 Agent 加工具开始，除非有明确证据说明需要拆分。比如独立资料分析可以并行，或审查角色确需与执行权限分开；但客服一次查订单、查物流通常不值得让多个模型互相协调。拆分会重复发送上下文，还要解决冲突、预算和最终责任，可能比单模型更慢。项目 Planner 和 Executor 是模块职责，不是两个独立自主 Agent，更没有生产团队协作验证。因此我会把多 Agent 作为未来备选设计，先在固定任务上对照单 Agent，检查是否真的提高目标覆盖，同时保证工作节点不能通过通信获取额外权限。

#### 3. Adaptive-RAG实际实现

项目未实现生产多 Agent 团队。[build_graph](../../app/agents/graph.py#L45) 编排单次共享 State，[Planner](../../app/agents/nodes/planner.py#L39) 与 [executor_node](../../app/agents/nodes/executor.py#L120) 是同服务模块。扩展取舍见 [Q317](#q317)，不能称已经实施 Supervisor/Worker。

#### 4. 面试官可能追问

- **追问：Planner/Executor 为什么不算两个 Agent？** 答：当前 Executor 按代码执行计划，没有独立模型决策循环。
- **追问：多 Agent 会降低幻觉吗？** 答：未必，可能共享偏差或传递错误，需独立证据验证。

#### 5. 测试与证据

既有 [test_service_graph_sse_privacy_and_disabled_parity](../../tests/integration/test_agent_tracing.py#L14) 只验证当前 Offline 单图。本轮未运行，没有单/多 Agent 对照或生产团队数据。


<a id="q037"></a>
### Q037：何时值得用自研轻量 orchestrator 而不是框架？

#### 1. 标准答案

流程短、执行语义清晰、无需复杂图恢复且框架适配成本较高时，自研轻量 orchestrator 可以更直接。必须把类型契约、错误、取消、观测和副作用边界算进维护成本，不能只比较初始代码量。若需要持久恢复和复杂并行，重写成熟机制可能更昂贵。迁移应保持业务契约并用回归证据决定。

#### 2. 面试口述版

如果流程只有少量固定步骤、团队能清楚维护错误和取消语义，自研一个轻量编排器可能更直接。但我不会只用几十行 if/else 和一个框架依赖比较成本，后续的状态、追踪、重试、权限及恢复都要有人负责。项目当前已经用 LangGraph，业务能力通过 Provider、工具与仓储分离，暂时没有迁移证据。若要替换，先保持相同输入输出和工具事件，选几条代表路径对照，再评估维护成本。尤其现有图也没配置持久检查点，不能把尚未使用的高级功能当成不可替换理由，也不能宣称换成自研就自动更快。

#### 3. Adaptive-RAG实际实现

已实现的编排入口是 [build_graph](../../app/agents/graph.py#L45)，业务调用在 [ChatService._invoke](../../app/services/chat_service.py#L321)。项目未实现替代 orchestrator 或迁移基准；接口分离只是可替换性基础，不是已完成替换的证据。

#### 4. 面试官可能追问

- **追问：什么信号说明框架过重？** 答：大量绕过框架的适配、升级成本高而核心能力几乎未用，应具体度量。
- **追问：迁移最容易漏什么？** 答：异常、流式取消、状态合并、预算与副作用重放语义。

#### 5. 测试与证据

既有 [test_service_graph_sse_privacy_and_disabled_parity](../../tests/integration/test_agent_tracing.py#L14) 可作为当前行为参考，本轮未运行；没有自研编排器对照测试。


<a id="q317"></a>
### Q317：单Agent与多Agent怎么权衡，什么情况下不值得拆分？

★

#### 1. 标准答案

多 Agent 只有在任务可独立验证、上下文或权限需隔离、并行收益足以抵消协调成本时才值得。短流程、高耦合状态和单一证据来源常更适合单 Agent 加工具。角色数量不是质量指标，应比较端到端成功、安全、费用与延迟，并保留简单方案作为基线。

#### 2. 面试口述版

我不会按任务看起来复杂就拆 Agent，先看能否独立分工与验证。客服查订单、商品和物流通常是同一用户目标，用单 Agent 加结构化工具就能完成；拆成几个模型会重复上下文，还要汇聚冲突和承担错误传递。真正需要不同专业上下文、独立审查或可并行资料分析时，才考虑多 Agent。项目目前没有生产团队协作，Planner 和 Executor 只是模块分工，所以我只能讲选型原则。若实验，应固定任务和预算，对照单 Agent，检查新增角色是否带来可量化成功收益，以及是否守住每个角色的工具权限与最终责任。

#### 3. Adaptive-RAG实际实现

项目未实现多 Agent 生产团队。[build_graph](../../app/agents/graph.py#L45) 是单次图，[Planner](../../app/agents/nodes/planner.py#L39) 与 [executor_node](../../app/agents/nodes/executor.py#L120) 不构成独立自主协作网络。相关控制权见 [Q036](#q036)。

#### 4. 面试官可能追问

- **追问：什么情况下不值得拆？** 答：任务短、状态强耦合、证据同源或成本预算紧时。
- **追问：独立评审 Agent 一定更可靠？** 答：不一定，共享模型与证据可能共享偏差，仍需外部验证。

#### 5. 测试与证据

既有 [test_service_graph_sse_privacy_and_disabled_parity](../../tests/integration/test_agent_tracing.py#L14) 只测当前 Offline 单图。本轮未运行，无单/多 Agent 对照数据。


<a id="q318"></a>
### Q318：Supervisor/Worker、Planner/Executor、辩论与并行专家模式区别？

★

#### 1. 标准答案

Supervisor/Worker 由主管分派并汇总；Planner/Executor 分离任务设计与执行；辩论让多个候选互相质询，需外部裁判；并行专家同时处理独立视角，再汇聚证据。它们是协作模式，可组合但带来不同调度和权限成本。命名两个节点不等于实现多个独立 Agent。

#### 2. 面试口述版

四种模式的差异是控制权和验证方式。主管模式决定谁做什么，规划执行分离计划与动作，辩论强调候选互相质询，并行专家追求独立工作同时进行。辩论若没有外部证据，可能只是几个模型互相强化；并行若任务强依赖，也可能先并行再返工。项目名义上有 Planner 和 Executor，但后者是确定代码，没有独立模型循环，不是完整多 Agent 团队。未来选模式应先定义消息契约、目标和终止条件，再比较协调成本，不能把模式都堆上去。我更愿意先保持单图，只有可验证收益时再增加角色。

#### 3. Adaptive-RAG实际实现

部分实现职责分离：[Planner.create_plan](../../app/agents/nodes/planner.py#L55) 生成计划，[executor_node](../../app/agents/nodes/executor.py#L120) 运行工具。项目未实现 Supervisor/Worker、辩论或并行专家团队，也未验证这些模式在客服任务上优于当前设计。

#### 4. 面试官可能追问

- **追问：Executor 没模型还能叫 Agent 吗？** 答：应按实际行为说明，这里是代码执行器，不夸成独立决策 Agent。
- **追问：辩论怎么防止集体幻觉？** 答：要求引用独立证据并外部验证，不能只按多数投票。

#### 5. 测试与证据

既有 [test_real_shaped_planner_extra_step_is_pruned_only_for_status_request](../../tests/unit/test_p2q_planner.py#L110) 与 [test_read_tool_falls_back_to_knowledge](../../tests/unit/test_executor_fallback.py#L37) 验证模块，不验证多 Agent 协作。本轮未运行。


<a id="q319"></a>
### Q319：多Agent共享状态、Memory和工具权限如何隔离？

★

#### 1. 标准答案

多 Agent 应分别获得最小上下文、独立工作状态和工具能力，跨角色交换结构化证据而非全部原始历史。共享 Memory 按可信主体与用途隔离，写入需版本和审核；主管不能凭消息为下级扩大权限。需要统一预算、关联 ID、取消和审计，防止信息经汇聚或日志旁路泄露。

#### 2. 面试口述版

如果以后拆多个 Agent，我会先隔离权限再谈共享记忆。每个角色只拿必要任务和工具，结果用带来源的结构化产物交换，不把全量用户历史和服务凭证广播。共享记忆仍按真实用户与租户限权，写经验不能自动变成其他 Agent 的指令。主管分配任务也不能赋予自己没有的权限。项目当前只有单图状态与受限偏好隔离，没有多 Agent Memory 总线，所以这些是设计方案。可复用现有身份绑定、上下文白名单和工具风险控制，但还要新增角色级能力与并发契约，单用户隔离单测不能替代团队安全测试。

#### 3. Adaptive-RAG实际实现

项目未实现多 Agent 状态/Memory 总线。已有 [PreferenceMemory._scope](../../app/memory/long_term.py#L72)、[ToolContext](../../app/tools/base.py#L16)、[SelectedContext.prompt_context](../../app/memory/context.py#L57) 提供单请求边界，不能据此宣称角色间隔离已落地。

#### 4. 面试官可能追问

- **追问：主管发来的消息算授权吗？** 答：不算，执行角色仍需可信服务端能力与资源检查。
- **追问：共享全部历史更方便吗？** 答：会增加泄露、注入与费用，应按任务最小化传递。

#### 5. 测试与证据

既有 [test_tenant_user_isolation_and_revoke_deletes_values](../../tests/unit/test_long_term_memory.py#L56) 和 [test_request_identity_context_isolated_and_reset](../../tests/unit/test_long_term_memory.py#L69) 仅测内存主体边界。本轮未运行，无多 Agent 安全验证。


<a id="q320"></a>
### Q320：两个Agent并发写同一文件或数据库怎样避免冲突？

★

#### 1. 标准答案

优先通过所有权分区减少共享写，同文件由单写者或受控补丁汇聚；数据库使用事务、唯一约束、版本条件更新与必要锁。稳定业务幂等键防重复，但不同动作键不能自动解决同资源竞争。操作系统文件锁、Git 分支与数据库锁解决不同问题，应设计冲突检测和人工可审查的合并。

#### 2. 面试口述版

两个 Agent 同时改一个文件，最简单的办法通常是先分工，避免共享写；需要合并时用补丁和单一汇聚者审查，不能谁最后保存就覆盖谁。数据库则用事务、版本或条件更新保护资源，同动作重试用幂等，但两个不同动作 ID 仍可能竞争同一订单。项目没有多 Agent 写协调器，当前提案行锁只约束同审批记录，不能推成任意资源并发安全。未来应明确资源所有者、冲突策略和回滚边界，文件合并也要保留双方变化并运行相关检查。多 Agent 的速度收益不应建立在静默覆盖或重复业务操作上。

#### 3. Adaptive-RAG实际实现

项目未实现多 Agent 文件协调。已有 [ChatService._load_confirmation](../../app/services/chat_service.py#L272) 的提案行锁和 [IdempotencyRepository.put](../../app/repositories/idempotency.py#L30) 的唯一键冲突处理；不等于不同动作针对同资源已全面串行化。

#### 4. 面试官可能追问

- **追问：Git 分支能解决数据库竞争吗？** 答：不能，代码隔离和运行时资源锁是不同层。
- **追问：每个 Agent 用不同幂等键就安全？** 答：不够，不同键可能针对同资源，需要业务状态并发约束。

#### 5. 测试与证据

既有 Offline/SQLite [test_pending_confirmation_replay_and_unrelated_orders](../../tests/integration/test_goal_evaluation.py#L30) 只测同动作顺序重放。本轮未运行，无多 Agent 文件竞争或 PostgreSQL 同资源并发测试结论。


<a id="q321"></a>
### Q321：多Agent会增加哪类Token、延迟和错误传播成本？

★

#### 1. 标准答案

多 Agent 成本包括重复系统提示与历史、任务分派、消息通信、候选重试、汇总和独立验证。延迟取决于关键路径，不能简单按并行数相除；错误可能经摘要和汇聚被放大。应按最终任务统计总调用、Token、重试、安全和成功率，避免各角色局部指标很好但总体失败。

#### 2. 面试口述版

多 Agent 不只是把一次调用拆成几份。每个角色都要读角色指令和任务背景，主管还要分派和汇总，失败会增加通信与重做。并行只能缩短独立工作段，关键路径、配额和最终验证仍串行。错误也可能在角色间转述后丢掉来源，最后被包装成共识。项目没有多 Agent 成本基准，所以不能报节省百分比。若做实验，我会按完整业务目标汇总所有角色的 Token、工具和重试，和同预算单 Agent 比较成功与安全，而不是只展示某个专家更快。只有净收益明确，才值得承担额外调度和排障复杂度。

#### 3. Adaptive-RAG实际实现

项目未实现多 Agent 成本归集。已有 [LatencyBreakdown 所在状态](../../app/agents/state.py#L48)、[record_tool](../../app/observability/execution.py#L20) 与 [AttemptLedger.reserve](../../app/providers/paid_budget.py#L653) 记录单应用执行或付费尝试，不能当多团队分布式计费网关。

#### 4. 面试官可能追问

- **追问：并行三角色延迟会缩三倍吗？** 答：不会自动如此，关键路径、配额与汇总仍决定总耗时。
- **追问：局部准确率都高为何总体仍失败？** 答：任务依赖、接口误解和错误传播会累积，需端到端测量。

#### 5. 测试与证据

既有 [test_grant_counts_every_http_retry_against_twenty_attempts](../../tests/unit/test_budget_authorization.py#L254) 测单账本派发计数。本轮未运行，无多 Agent 成本/延迟对照。


<a id="q322"></a>
### Q322：Agent-to-Agent协议与MCP是什么关系？

#### 1. 标准答案

A2A 关注独立 Agent 间围绕任务与产物的协作；MCP 关注应用连接工具和上下文能力。一个 Agent 可通过 MCP 用工具，再通过 A2A 与其他 Agent 协作。二者不自动提供相同执行或信任边界，协议接通不代表任务正确或获得授权。[A2A 官方说明](https://a2a-protocol.org/latest/topics/a2a-and-mcp/) 将其视为互补。

#### 2. 面试口述版

我把 MCP 看成能力接入层，A2A 看成 Agent 之间的任务协作层。一个客服 Agent 可以通过工具查订单，再与另一个独立业务 Agent 协作；但协议连通不意味着对方输出可信，也不替代身份、权限和任务结果核验。项目现在只有 MCPToolProxy 和简化远端调用，没有 A2A Agent Card、任务消息或产物协作实现。因此不能把节点之间传 State 叫作已落地 A2A。未来如果确需跨系统 Agent 合作，要先定义任务契约、取消和状态查询、数据最小化及最终责任，不能只加通信协议就期待质量提高。

#### 3. Adaptive-RAG实际实现

项目未实现 A2A。[MCPToolProxy](../../app/mcp/adapter.py#L16) 适配工具，[build_graph](../../app/agents/graph.py#L45) 只是本地图编排；节点间 State 传递不构成 A2A。现有 MCP 远端也不是完整标准协议栈，边界见 [Q118](03_Tool_MCP_Memory_HITL_答案.md#q118)。

#### 4. 面试官可能追问

- **追问：把另一个 Agent 包成工具就等于 A2A 吗？** 答：不等于，只说明暴露了可调用接口，任务协作协议语义另需实现。
- **追问：接协议后能信对方结论吗？** 答：不能，仍要证据、权限和结果验证。

#### 5. 测试与证据

既有 [test_mcp_proxy_is_function_calling_tool](../../tests/unit/test_mcp.py#L21) 仅测本地工具代理。本轮未运行，没有 A2A 互通或跨 Agent 业务测试。


<a id="q323"></a>
### Q323：什么是Skill的渐进披露，适合哪些工具集合？

#### 1. 标准答案

渐进披露先提供简短能力索引，再按任务加载匹配 Skill 的步骤、参考资料和必要工具 Schema，减少无关上下文。适合目录大、任务领域分明的集合，但需保证候选召回和权限过滤，避免只加载熟悉任务。披露策略与执行授权分离，动态加载不能扩大权限。

#### 2. 面试口述版

渐进披露不是把所有 Skill 文本一起塞进 Prompt，而是先让系统看到简短目录，匹配任务后再加载详细步骤和工具。它适合工具多但任务领域有边界的场景，可以减少 Token 与干扰。项目当前 loader 每次读取定义，再按触发词或意图选一个 Skill，规划只注入该 Skill 的格式化上下文；这有选择性，但不是完整索引、检索、按需加载多层资料的架构。我会如实称部分思想相近。未来需要记录匹配来源、版本与加载预算，并验证陌生表达和多目标任务不会因为少披露而丢能力，加载到的 Skill 也不能授权写操作。

#### 3. Adaptive-RAG实际实现

部分实现选择性注入：[load_skills](../../app/skills/loader.py#L21) 读取全部 JSON，[match_skill](../../app/skills/loader.py#L37) 最多匹配一个，[_format_skill](../../app/agents/nodes/planner.py#L180) 格式化。项目未实现大型 Skill 索引或资料按需分层加载。

#### 4. 面试官可能追问

- **追问：只披露一个 Skill 有何风险？** 答：组合任务可能跨领域，应验证必要能力不被遗漏。
- **追问：Skill 文件可信就能跳确认吗？** 答：不能，任务知识不提供执行授权。

#### 5. 测试与证据

既有 [test_match_skill_by_trigger](../../tests/unit/test_skills.py#L4)、[test_match_skill_by_intent_when_no_trigger](../../tests/unit/test_skills.py#L11) 为离线匹配测试。本轮未运行，无大规模渐进披露成本基准。


<a id="q324"></a>
### Q324：长任务如何做断点续跑、取消、checkpoint和进度可视化？

#### 1. 标准答案

长任务需持久任务状态、步骤水位、版本、可重入执行与明确取消语义；checkpoint 保存进度，副作用结果另有幂等记录。进度展示来源于已提交事实，不能模型编百分比。取消分为停止后续派发与补偿已执行动作，超时不等于撤销。恢复应先核对实际状态再选择下一步。

#### 2. 面试口述版

长任务要把计划状态和执行证据写在可恢复存储，步骤完成后记录水位，重启先核对哪些动作已提交。取消也要讲清楚：停止后续工作不代表撤销已经发出的外部操作。进度界面应展示真实阶段和未完成目标，不让模型随便报百分比。项目当前有 SSE 节点事件、工作台安全快照和待确认动作取消，但没有长任务调度器、持久图检查点或通用任务恢复。工作台 Trace 还是带 TTL 的内存存储，不能当长期任务账本。因此我会把现有观测和未来长任务能力分开，后者还需状态机、租约、取消与副作用恢复测试。

#### 3. Adaptive-RAG实际实现

部分实现 [ChatService._stream_updates](../../app/services/chat_service.py#L336)、[WorkbenchStore](../../app/observability/workbench.py#L20)、[cancel_action](../../app/api/routes/workbench.py#L82)。项目未实现长任务调度、durable graph checkpoint 或通用执行取消；取消待确认提案不等于撤销已执行动作。

#### 4. 面试官可能追问

- **追问：关掉 SSE 就算取消吗？** 答：不一定，断开展示与停止后台/外部动作是不同事件。
- **追问：Trace 可以拿来续跑吗？** 答：当前是有限投影和内存 TTL，缺完整执行状态，不能替代检查点。

#### 5. 测试与证据

既有 [test_cancel_rejects_foreign_completed_and_repeat](../../tests/unit/test_web_workbench.py#L102)、[test_trace_store_bounds_ttl_owner_and_defensive_copy](../../tests/unit/test_web_workbench.py#L16) 检查工作台范围。本轮未运行，无长任务恢复验收。


<a id="q325"></a>
### Q325：什么是Sandbox？与RBAC、审批的区别？

#### 1. 标准答案

Sandbox 限制程序可使用的文件、网络、进程及计算资源；RBAC 规定主体可访问的能力；审批表达对特定动作的确认。三者互补，互不替代。即使有批准，代码也不应获得无限系统权限；即使在沙箱内，读取他人数据也可能越权。隔离需具体配置与攻击验证，不能只凭容器名称判断。

#### 2. 面试口述版

我会用三个问题区分：RBAC 问谁有权做，审批问这次动作是否同意，Sandbox 问执行程序实际上能碰到什么。一个已批准的退款程序也不应能读整台主机或随意出网；反过来，在容器里读取别人的订单仍是业务越权。项目有用户/admin 角色、订单归属、写确认和工具风险控制，但没有任意代码执行沙箱，所以我不能把 Docker 运行等同安全隔离完成。未来如果接代码 Agent，要单独限制挂载、网络、凭证、进程和资源，并测试逃逸与超限，不能只增加一个批准按钮就开放所有命令。

#### 3. Adaptive-RAG实际实现

部分实现 [Principal](../../app/core/auth.py#L20)、[assert_permitted](../../app/tools/permissions.py#L10) 与 [ChatService._load_confirmation](../../app/services/chat_service.py#L272)。项目未实现代码执行 Sandbox 或细粒度企业 RBAC；现有部署形态不证明操作系统隔离完备。

#### 4. 面试官可能追问

- **追问：有沙箱还需审批吗？** 答：需要，沙箱降低执行范围，不判断用户是否同意业务副作用。
- **追问：管理员操作可绕沙箱吗？** 答：不应默认如此，高权限身份也需限定执行环境和审计。

#### 5. 测试与证据

既有 [test_admin_only_server_role_and_empty_registry_fails_closed](../../tests/unit/test_trusted_auth.py#L99)、[test_destructive_requires_confirmation](../../tests/unit/test_tools_and_parser.py#L18) 只测应用权限。本轮未运行，无沙箱逃逸测试。


<a id="q326"></a>
### Q326：代码执行Agent如何防命令注入和越权文件访问？

#### 1. 标准答案

代码 Agent 应避免拼接 shell，把参数作为结构化值传递，限制命令与工作目录，解析后验证路径和符号链接，禁止访问秘密及系统目录。运行在低权隔离环境，限制出网、进程、时间和资源；危险操作仍需明确范围与审批。字符串转义不能替代能力白名单和执行隔离。

#### 2. 面试口述版

最直接的原则是不把用户文本拼进 shell。能用结构化文件或数据库接口就用接口，需要执行命令时限制可执行文件、参数和工作目录；路径要检查解析后的真实位置，还要考虑符号链接和路径穿越。代码运行环境应使用低权凭证、最少挂载和受控出网，并限制时间与资源。项目业务 Agent 没有任意命令执行工具，所以这些是未来设计，不是当前已实现的安全沙箱。不能把本次文档编辑环境的命令工具当成 Adaptive-RAG 产品能力。若以后新增代码工具，先做隔离与越界测试，再考虑模型便利性，不能让模型自己决定可访问目录。

#### 3. Adaptive-RAG实际实现

项目未实现产品内代码执行 Agent。[build_tool_registry](../../app/tools/factory.py#L28) 注册的是业务工具，[Tool.run](../../app/tools/base.py#L73) 也不提供系统级沙箱。上述命令/路径隔离属拟议方案，不能用当前订单参数校验替代。

#### 4. 面试官可能追问

- **追问：把命令用 JSON 包起来就安全？** 答：不一定，若后续仍拼接 shell，危险字符仍可能被解释。
- **追问：只检查路径字符串前缀够吗？** 答：不够，需规范化真实路径并考虑分隔符、链接与竞态。

#### 5. 测试与证据

既有 [test_registry_has_fifteen_tools](../../tests/unit/test_tool_registry.py#L4) 只检查当前业务目录，不证明命令执行安全。本轮未运行，无产品代码沙箱测试。


<a id="q327"></a>
### Q327：怎么检测Agent路径震荡或无限自我反思？

#### 1. 标准答案

检测重复路径和无进展应结合状态签名、工具参数指纹、目标覆盖变化、连续失败和预算。不要仅按重复工具名判循环，同工具不同目标或失败修复可能合理。达到无改善阈值、总轮数、时间或费用上限就终止并交代未完成项，反思也须有新证据才能继续。

#### 2. 面试口述版

路径震荡的关键是没有增加有效证据或目标进展，比如路由来回切换、相同参数重复成功读、反思多轮却没有任何新观察。应记录状态签名和目标覆盖变化，再结合总次数、时间与 Token 截止。项目目前没有路由循环或无限反思，计划最多六步、执行器去重成功读，忠实度最多一次改写；所以不能说已经部署路径震荡检测器。未来增加重规划时，要允许不同订单和临时失败修复，不能粗暴禁掉同工具重复。触发停止后应明确哪些目标缺证据，而不是用一段流畅答案掩盖预算耗尽。

#### 3. Adaptive-RAG实际实现

部分实现 [_sanitize_plan](../../app/agents/nodes/planner.py#L224)、[executor_node](../../app/agents/nodes/executor.py#L147)、[self_correct_answer](../../app/agents/nodes/faithfulness.py#L21) 的有界机制。项目未实现通用路径签名、进展评分或震荡检测，现有无循环图不能证明该检测能力。

#### 4. 面试官可能追问

- **追问：同工具重复就算死循环吗？** 答：不一定，不同目标或临时失败修复可能必要，应看参数与有效观察。
- **追问：反思次数少是否质量更差？** 答：要看净收益，无新证据的多轮反思可能只增加成本与偏差。

#### 5. 测试与证据

既有 [test_exact_same_turn_read_is_dispatched_once_but_next_turn_is_fresh](../../tests/unit/test_p2r_decision.py#L175)、[test_transient_failed_read_does_not_suppress_next_bounded_planned_attempt](../../tests/unit/test_p2r_decision.py#L258) 验证有界重复。本轮未运行，无路径震荡专门实验。


<a id="q328"></a>
### Q328：Agent自学习/经验记忆为什么需要离线评测、审核与灰度？

#### 1. 标准答案

经验可能带有错误归因、特定样本泄漏、过期工具契约或注入，自动投入生产会放大一次失败。应分离候选生成、来源验证、离线适用性评测、审核、兼容检查与受控灰度，配备失效和回滚。审核标签不等于人类批准，隔离实验也不能推成生产学习收益。

#### 2. 面试口述版

一次失败不代表已经知道普遍规律。模型可能把偶然现象归因为错误规则，也可能把测试答案或用户隐私写入经验。项目经验模块只接受有验证失败证据的结构化候选，限制通用目录文本，并检查来源、适用条件、版本和有效期；隔离 Planner 召回还要求独立验证与许可，最多两条。这不是生产自动学习，也不是人类批准。离线测试先看安全冲突和未见场景，再决定是否值得受控试用；当前不能说已经完成生产灰度。新模型或工具契约变化后经验还要重新评估，不能因为 Git 版本接近就继续沿用。

#### 3. Adaptive-RAG实际实现

部分实现 [reflect](../../app/experience/reflection.py#L141)、[select_isolated](../../app/experience/isolated.py#L47)、[check_compatibility](../../app/experience/compatibility.py#L44)。项目未将经验注入生产图，也未实施生产自动学习/灰度；MODEL_REVIEWED 不等于 human_approved 或 production_approved。

#### 4. 面试官可能追问

- **追问：兼容检查通过能自动批准吗？** 答：不能，check_compatibility 明确 approval_granted=False。
- **追问：用旧失败样本通过就够吗？** 答：不够，需要独立适用性与安全样本，避免只记住原案例。

#### 5. 测试与证据

既有 [test_qualified_planner_only_max_two_and_shadow_message_identity](../../tests/unit/test_s1ex_isolation.py#L30)、[test_isolated_entry_refuses_production_or_unverified_scope](../../tests/unit/test_s1ex_isolation.py#L96)、[test_compatibility_never_approves_and_changed_contract_denies](../../tests/unit/test_s1ex_reflection.py#L42) 为隔离单测。本轮未运行。


<a id="q329"></a>
### Q329：工具目录有几百项，如何设计Tool Registry和动态搜索？

#### 1. 标准答案

大目录应区分注册与发现：Registry 维护稳定名称、版本、Schema、风险和授权绑定；搜索层按权限、业务域和语义召回候选，按需加载详情。执行始终回到注册表校验，搜索结果不可动态创造执行代码。需监测候选召回、误选、Schema Token、延迟和版本漂移。

#### 2. 面试口述版

Registry 是可信执行目录，搜索只是帮助发现。几百工具时，我会让注册项有稳定 ID、版本、用途、Schema、风险和授权策略，先按权限过滤，再关键词或语义检索，最后加载少量完整定义。模型搜到的描述不能直接成为可执行函数，仍要回注册表校验。项目当前 Registry 是内存字典，Skill 和能力规则缩范围，没有大型搜索索引或版本化动态发现。它足以服务现有规模，但不能说已经支持百工具检索。扩展时还要测必需能力召回和多目标覆盖，防止只优化目录 Token，却把关键工具从候选里裁掉。

#### 3. Adaptive-RAG实际实现

已实现 [ToolRegistry](../../app/tools/registry.py#L9) 的 register/get/all/names，和 [Planner._tool_catalog](../../app/agents/nodes/planner.py#L44)。项目未实现版本化大型工具搜索、语义索引或授权动态发现；目录裁剪实现见 [Q028](#q028)。

#### 4. 面试官可能追问

- **追问：搜索返回未知工具怎么办？** 答：不可直接执行，应只允许解析到已注册、已授权的稳定能力。
- **追问：注册同名工具会怎样？** 答：当前字典会覆盖，应在规模化设计中增加重复名和版本治理，不能假定已拒绝冲突。

#### 5. 测试与证据

既有 [test_registry_has_fifteen_tools](../../tests/unit/test_tool_registry.py#L4) 检查基础目录；[test_model_remains_primary_for_unrecognized_evidence_goal_and_catalog_has_schema](../../tests/unit/test_p2r_decision.py#L132) 检查候选 Schema。本轮未运行，无百工具基准。


<a id="q330"></a>
### Q330：模型换代后Graph/工具Schema/Memory如何兼容？

#### 1. 标准答案

换模型要版本化 Prompt、输出 Schema、工具风险及记忆格式，先做协议与安全回归，再比较成功、成本和延迟。不要把供应商 JSON 兼容等同语义一致，旧摘要与经验也可能不适用。支持双读/迁移和明确回滚，无法验证兼容时拒绝召回旧经验，不能自动扩大权限。

#### 2. 面试口述版

换模型不是只改 model 字符串。分类、规划 JSON、工具选择和忠实度判断都可能变，记忆摘要与旧经验的适用性也要重新确认。项目 Provider 接口便于替换，结构化 Schema 和工具执行边界能复用，隔离经验还有工具及安全函数契约哈希，但这些不保证新模型效果相同。应冻结多目标、越权、指代、确认和坏输出场景，先做无付费替身协议测试，再在明确授权预算内跑真实对照。旧经验兼容只是必要条件，不自动批准生产。当前没有多模型热切换和完整状态迁移框架，回滚也应保持旧版本资料与结果可追溯。

#### 3. Adaptive-RAG实际实现

部分实现 [LLMProvider](../../app/providers/base.py#L37)、[parse_model](../../app/providers/json_parser.py#L46)、[SummaryEnvelope](../../app/memory/summary_state.py#L17) 的版本字段；[runtime_contracts](../../app/experience/compatibility.py#L14) 校验经验相关契约。项目未实现自动模型迁移、热切换或生产兼容保证。

#### 4. 面试官可能追问

- **追问：接口同名就能无缝切换吗？** 答：不能，JSON 遵循、语义、计费与流式行为都需重新验证。
- **追问：工具哈希相同就能复用经验吗？** 答：只说明所检查契约没变，不证明新模型收益或授予批准。

#### 5. 测试与证据

既有 [test_json_parser_rejects_garbage](../../tests/unit/test_tools_and_parser.py#L34)、[test_compatibility_never_approves_and_changed_contract_denies](../../tests/unit/test_s1ex_reflection.py#L42) 检查局部契约。本轮未运行，无新模型迁移实测。


<a id="q331"></a>
### Q331：什么时候需要Model Gateway和多模型路由？

#### 1. 标准答案

多供应商、多模型且需统一认证、配额、观测、计费和故障策略时可考虑 Gateway；简单单供应商应用用 Provider 抽象即可。路由按任务难度、质量门槛、隐私与费用选择，fallback 不能绕过预算或悄悄降低安全。网关成为共享关键依赖，也需版本、隔离与故障策略。

#### 2. 面试口述版

只有一个供应商和少量调用时，我会先用清晰 Provider 接口，不急着搭 Gateway。当多个应用共用多模型，需要统一配额、费用、路由和观测，网关才有明确价值。模型路由也不能只选最便宜，分类、规划和生成的质量门槛不同，隐私与工具协议可能限制可选模型。项目当前容器选择 DeepSeek 或 Offline，并有付费预算传输层，但没有多供应商 Gateway、动态质量路由或熔断集群。Offline 是明确模式，不应在真实服务失败时偷偷假装真实回答。未来 fallback 要保持授权、预算与结果标识，不能为可用性绕过安全门槛。

#### 3. Adaptive-RAG实际实现

项目未实现 Model Gateway 或多供应商动态路由。[build_container](../../app/services/container.py#L128) 选择注入 Provider、DeepSeek 或 Offline；[BudgetedTransport](../../app/providers/paid_budget.py#L785) 控制付费派发。它是单路径预算机制，不是多模型网关。

#### 4. 面试官可能追问

- **追问：Gateway 与 Provider 接口有什么不同？** 答：接口主要隔离代码依赖，Gateway 通常还承担跨应用集中策略与运行服务。
- **追问：真实失败可静默切 Offline 吗？** 答：不应把替身冒充真实模型，需明确模式和失败原因，遵循授权策略。

#### 5. 测试与证据

既有 [test_real_dev_missing_key_fails_without_offline_fallback](../../tests/unit/test_real_agent_dev.py#L208)、[test_offline_mode_is_public_and_reports_no_credentials](../../tests/unit/test_runtime_modes.py#L68) 检查模式边界。本轮未运行，无多供应商网关验证。
