# Agent 与 LangGraph 答案

本文件先交付清单中的核心题。本轮只读核对源码和既有测试定义，未运行模型、业务服务或数据库；历史验证与本轮检查分别说明。

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
