# Python、异步与 FastAPI 答案

项目事实以本轮基准源码为准；Python 以 3.11 语义说明，依赖范围见 [pyproject.toml:L7](../../pyproject.toml#L7)。本页引用已有测试说明覆盖意图，不表示本轮执行过测试、启动服务或调用模型。

<a id="q208"></a>
### Q208：进程、线程、协程区别？Python GIL影响什么？

★ 核心题

#### 1. 标准答案

进程有独立地址空间，隔离好但启动、内存和进程间通信成本较高；线程共享进程内存，由操作系统调度，需要锁保护共享状态；协程由事件循环协作调度，适合大量可异步等待的网络 IO。协程在单线程上并发，并不自动实现 CPU 并行。

CPython 3.11 的 GIL 限制同一解释器内多个线程同时执行 Python 字节码。阻塞 IO 通常释放 GIL，部分数值计算扩展也会释放，因此“线程完全不能并行”不准确。GIL 也不能替代业务锁，多步读改写仍可能竞态。3.13 起可选 free-threaded 构建属于另一个运行条件；项目没有采用该构建的证据。参考 [Python 3.11 threading](https://docs.python.org/3.11/library/threading.html) 与 [Python 3.13 free threading](https://docs.python.org/3.13/howto/free-threading-python.html)。

#### 2. 面试口述版

我会先区分并发与并行：进程适合隔离和纯 Python 的多核计算，线程适合同步阻塞 IO，协程适合支持异步接口的大量等待。项目按 Python 3.11 理解 GIL，同一解释器的多个线程不能同时执行 Python 字节码，但等待网络以及某些释放 GIL 的扩展可以重叠。GIL 不保证业务操作原子，例如检查余额再扣款仍需事务。Adaptive-RAG 主要等待模型和数据库，所以主链路用异步；同步 Qdrant 操作通过线程卸载，避免卡住 SSE。若未来解析计算耗尽 CPU，我会评估进程池或独立任务服务，再根据序列化成本和实际压测决定。

#### 3. Adaptive-RAG实际实现

`ChatService.chat` 使用异步会话及图调用，见 [app/services/chat_service.py:L88](../../app/services/chat_service.py#L88)。私有向量集合初始化用 `asyncio.to_thread`，见 `build_retrieval` [app/services/container.py:L95](../../app/services/container.py#L95)；这用于卸载同步调用，不能据此声称纯 Python CPU 工作获得多核加速。项目未实现通用进程池或 CPU 任务调度平台。

#### 4. 面试官可能追问

- **追问：有 GIL 还需要锁吗？** 答：需要。检查容量、读取计数再写回是多步业务操作；线程锁、异步锁或数据库事务分别解决各自作用域的竞态。
- **追问：协程比线程始终更快吗？** 答：不是。异步库和大量等待才有优势；单个很短的同步函数强行切线程可能只增加调度成本。
- **追问：多个 API worker 能共享 Python 字典限额吗？** 答：不能。每个进程有自己的字典，因此项目敏感入口使用 Redis 原子准入；测试内存限流只适用于受限离线场景。

#### 5. 测试与证据

已有 `test_asgi_disconnect_closes_body_iterator_and_graph` 模拟 ASGI 断连并断言迭代器关闭、轨迹取消，见 [tests/integration/test_stream_cleanup.py:L25](../../tests/integration/test_stream_cleanup.py#L25)。它证明所测取消路径的断言存在，不是 GIL 性能基准，也不是本轮运行结果。内存限流的 `asyncio.Lock` 可核对 [app/infra/rate_limit.py:L28](../../app/infra/rate_limit.py#L28)。

<a id="q209"></a>
### Q209：async/await、事件循环与Task是如何工作的？

★ 核心题

#### 1. 标准答案

调用 `async def` 函数得到协程对象，不会自动运行。`await` 驱动可等待对象，未完成的异步等待让出控制权，事件循环运行其他就绪任务，IO 就绪后恢复。`Task` 包装并调度协程，`asyncio.create_task` 允许与当前任务并发推进；连续两次 `await f()` 默认仍是顺序执行。`await` 遇到已经完成的结果时不一定发生调度切换。

取消通过向协程注入 `CancelledError` 协作实现；应用应在 `finally` 清理资源并继续传播取消。超时不是强制杀掉任意同步工作，线程中的函数也不会因取消等待自动停止。参考 [Python 3.11 Coroutines and Tasks](https://docs.python.org/3.11/library/asyncio-task.html)。

#### 2. 面试口述版

我把事件循环理解为就绪任务的调度器。调用异步函数只是创建协程，真正 await 或创建 Task 后才开始执行。任务遇到尚未完成的异步 IO 会挂起，事件循环就能服务其他聊天；如果在里面一直算或同步阻塞，其他任务仍要等。项目流式聊天创建一个图执行 Task，通过 Queue 把节点事件交给响应迭代器，消费者与生产者可以并发推进。这个 Task 必须由请求拥有：断连时要取消并等待退出，数据库和 trace 也要清理。我不会随手 create_task 后丢掉引用，否则异常、任务寿命和请求取消都容易失去管理。

#### 3. Adaptive-RAG实际实现

`ChatService.stream` 的 `_run_graph` 生产节点事件，`asyncio.create_task` 启动生产者，消费者 `await queue.get()`；`finally` 取消并等待未结束任务，见 [app/services/chat_service.py:L114](../../app/services/chat_service.py#L114) 与 [app/services/chat_service.py:L137](../../app/services/chat_service.py#L137)。当前 Queue 没设置 `maxsize`，不能声称已实现有界背压。路由用 `aclosing` 关闭嵌套流，见 [app/api/routes/chat.py:L49](../../app/api/routes/chat.py#L49)。

#### 4. 面试官可能追问

- **追问：`await a(); await b()` 会并发吗？** 答：不会，b 在 a 完成后开始；独立工作可用 TaskGroup 或明确持有的 Task，但要处理失败取消和资源上限。
- **追问：为什么取消后还要 await task？** 答：`cancel()` 只是发出取消请求；等待它结束才能确认清理完成，并回收其异常。
- **追问：Queue 会自动防止内存增长吗？** 答：无界 Queue 不会。应按事件规模设置容量或合并低价值事件，并定义慢客户端超时；这是可改进设计，不是现有保证。

#### 5. 测试与证据

`test_route_iterator_close_finalizes_owned_trace_without_context_leak` 在读取首个事件后关闭迭代器，断言 trace 为 cancelled 且无运行中 span，见 [tests/integration/test_stream_cleanup.py:L10](../../tests/integration/test_stream_cleanup.py#L10)。`test_asgi_disconnect_closes_body_iterator_and_graph` 覆盖响应发送时的断连，见 [tests/integration/test_stream_cleanup.py:L25](../../tests/integration/test_stream_cleanup.py#L25)。这里只审阅测试，没有重跑。

<a id="q210"></a>
### Q210：CPU密集任务与IO密集任务如何选async、线程、进程？

★ 核心题

#### 1. 标准答案

先通过 CPU 利用率、事件循环延迟和外部等待定位瓶颈。异步 HTTP、异步数据库客户端用 async；只有同步接口的网络、磁盘调用可用受限线程池；纯 Python CPU 密集计算通常用进程池或外部计算 worker。释放 GIL 的数值扩展可能在线程中并行，但仍需衡量底层线程数和 GPU/内存竞争。

卸载不是无限提交：并发上限应与连接池、模型配额及机器容量匹配。进程池需要处理启动、数据序列化和取消边界；大型模型每进程加载会放大内存。`to_thread` 的典型用途是阻塞 IO，见 [Python 3.11 to_thread](https://docs.python.org/3.11/library/asyncio-task.html#asyncio.to_thread)。

#### 2. 面试口述版

我的选择依据是任务在等什么。模型 HTTP 和数据库查询主要等网络，就沿用异步客户端；同步文件解析或 Qdrant 客户端则放到线程，保护事件循环。纯 Python 大量计算会受 GIL 限制，要考虑进程池或独立服务。模型推理还要看底层是否释放 GIL、是否使用 GPU，以及每个 worker 复制模型的内存代价。Adaptive-RAG 的文档解析和重排预测已有线程卸载，但这只能说明没有直接在事件循环执行对应同步函数，不能说明吞吐已经达标。我会限制提交数量，测请求尾延迟和机器资源，再决定是否拆出计算任务服务。

#### 3. Adaptive-RAG实际实现

`KnowledgeIngestor.load` 将 `parse_path` 交给线程，见 [app/retrieval/ingest.py:L79](../../app/retrieval/ingest.py#L79)。`CrossEncoderRerankProvider.rerank` 卸载 `_predict`，见 [app/providers/reranker.py:L107](../../app/providers/reranker.py#L107)。`DeepSeekProvider` 使用 `httpx.AsyncClient`，见 [app/providers/deepseek.py:L29](../../app/providers/deepseek.py#L29)。项目未实现 Celery 或统一进程池，不能把候选架构说成既有部署。

#### 4. 面试官可能追问

- **追问：把 CPU 工作放 to_thread 就能用满多核吗？** 答：纯 Python 通常不能；主要收益是避免直接阻塞循环。能否并行取决于扩展释放 GIL 等条件。
- **追问：为什么不每个请求开一个进程？** 答：启动和加载模型昂贵，容易耗尽内存；应复用受限 worker，并控制队列和超时。
- **追问：客户端取消会停掉线程推理吗？** 答：通常只取消等待。正在执行的线程函数需协作停止或等待完成；强隔离和可终止需求应另作进程设计。

#### 5. 测试与证据

已有本地适配器测试 `test_qdrant_local_adapter_roundtrip_not_real_service` 验证 Qdrant 客户端在内存模式下的写读契约，见 [tests/unit/test_p4b_dependency_contracts.py:L35](../../tests/unit/test_p4b_dependency_contracts.py#L35)；它不验证线程池性能或远程 Qdrant。本题没有 CPU/IO 吞吐对比证据，本轮未运行性能测试。

<a id="q211"></a>
### Q211：async函数中使用同步requests或time.sleep为什么会卡住？

★ 核心题

#### 1. 标准答案

异步函数仍在事件循环线程执行普通 Python 代码。同步 `requests` 等待响应、`time.sleep` 等待时间时没有把控制权交还事件循环，导致同一循环上的请求处理、心跳、超时和取消回调延后。`time.sleep` 可能释放 GIL，但事件循环所在的那个线程仍睡眠，因此其他 Python 线程可以运行不代表事件循环能推进。

应使用 `httpx.AsyncClient`、`asyncio.sleep` 等异步接口；只有同步库可用时以受限 `to_thread` 或 executor 卸载，并给同步调用自身设置超时。把函数改名为 async 或在外面加一次 await 不会使内部阻塞代码变成异步。

#### 2. 面试口述版

async 不是自动并发开关，里面的同步代码仍占着事件循环线程。比如请求里 requests 等十秒，同一循环的其他聊天和 SSE 心跳都可能停十秒；time.sleep 即使释放 GIL，也没有让事件循环那个线程继续工作。我的优先修法是异步 HTTP 客户端和 asyncio.sleep，如果第三方库只有同步接口，再通过受限线程卸载，并保留连接、读取超时。项目 DeepSeek 调用用 AsyncClient，Qdrant 等同步调用有 to_thread。排查时我会观察事件循环延迟和请求阶段耗时，避免把本地阻塞误判成模型服务慢，也不会用增加 worker 掩盖根因。

#### 3. Adaptive-RAG实际实现

`DeepSeekProvider.generate` 等待 `self._client.post`，并将 HTTPX 超时映射为领域错误，见 [app/providers/deepseek.py:L78](../../app/providers/deepseek.py#L78)。超时分 connect/read/write/pool 配置，见 [app/providers/deepseek.py:L34](../../app/providers/deepseek.py#L34)。私有检索的同步向量搜索用线程卸载，见 [app/retrieval/private.py:L254](../../app/retrieval/private.py#L254)。这些是具体路径，不能扩大为全仓库不存在任何阻塞点。

#### 4. 面试官可能追问

- **追问：同步 def 路由与 async def 有何不同？** 答：FastAPI 会在线程池执行普通同步路由；但在 async 路由内部直接调用同步函数，不会自动把这个调用转入线程。
- **追问：`await asyncio.sleep(0)` 能修复长计算吗？** 答：它可协作让出执行权，但不减少 CPU 需求；在长循环后才调用也无法消除之前的阻塞。
- **追问：给 to_thread 外面套超时够吗？** 答：不够。超时后线程可能还在请求；同步库也需设置自身超时，并限制线程数量，避免后台积压。

#### 5. 测试与证据

`test_explicit_non_thinking_mode_reaches_json_and_stream_payloads` 使用 HTTPX MockTransport 检查普通与流式请求，见 [tests/unit/test_deepseek_thinking.py:L14](../../tests/unit/test_deepseek_thinking.py#L14)。它不访问真实 DeepSeek，也不测真实网络延迟；本轮未运行该测试。异步任务与线程行为可查 [Python 3.11 官方任务文档](https://docs.python.org/3.11/library/asyncio-task.html)。

<a id="q230"></a>
### Q230：FastAPI Depends为什么不用直接调用函数？何时创建/释放依赖？

★ 核心题

#### 1. 标准答案

`Depends` 声明依赖图，由 FastAPI 解析参数、处理子依赖、按请求缓存同一依赖结果并支持 `dependency_overrides`。普通函数调用适合纯内部逻辑，但不会自动接入这些框架能力。依赖返回什么、是否新建对象取决于 provider；Depends 不等于全局单例，也不保证依赖返回对象线程安全。

`yield` 依赖在进入时创建资源、退出时清理；清理时机与版本有关。项目约束 FastAPI `>=0.115.0,<0.116`，该范围在路由返回后、响应发送前执行 yield 退出代码。0.118.0 改为响应发送后；不要给此项目套用后来的 `scope` API。版本史见 [FastAPI Advanced Dependencies](https://fastapi.tiangolo.com/advanced/advanced-dependencies/#dependencies-with-yield-and-streamingresponse-technical-details)。

#### 2. 面试口述版

Depends 的价值是把请求相关的组装和生命周期声明给框架。鉴权、请求模型和容器依赖可以组合，测试也能覆盖替换；如果直接调用函数，就要自己管理子依赖和参数。不过它不会自动把所有对象变成单例。项目的 get_container 只是取启动时创建的容器，鉴权依赖负责绑定可信身份。数据库 Session 并没有用 Depends yield 注入，而是 ChatService 在请求和流迭代器内部用上下文管理器持有。这里特别要看 FastAPI 版本：项目是 0.115 系列，yield 依赖在发送响应前已清理，不能让后续 SSE 迭代继续依赖已释放的会话。

#### 3. Adaptive-RAG实际实现

`get_container` 返回 `request.app.state.container`，`authenticated_payload` 依赖 `get_principal`，见 [app/api/dependencies.py:L12](../../app/api/dependencies.py#L12)。容器在 lifespan 构造并在结束时关闭，见 [app/main.py:L30](../../app/main.py#L30)。`request_session` 用 ContextVar 绑定当前会话并在 finally 重置，见 [app/core/request_scope.py:L27](../../app/core/request_scope.py#L27)。`ChatService.stream` 在自身 async with 内使用 Session，见 [app/services/chat_service.py:L110](../../app/services/chat_service.py#L110)。

#### 4. 面试官可能追问

- **追问：同一个请求重复依赖会调用多次吗？** 答：默认复用相同依赖调用的缓存结果；`use_cache=False` 可要求重新求值。跨请求不依赖这个缓存共享资源。
- **追问：ContextVar 意味着可以让多个 Task 并发操作同一 Session 吗？** 答：不意味着。它隔离绑定，不改变 AsyncSession 的并发使用约束；并行独立事务应分别创建会话。
- **追问：SSE 断连后谁负责释放？** 答：服务迭代器拥有会话与图 Task，路由显式关闭嵌套迭代器，finally 取消任务、退出会话和重置上下文。

#### 5. 测试与证据

可信身份绑定测试 `test_verified_subject_replaces_omitted_client_identity_without_mutation` 见 [tests/unit/test_trusted_auth.py:L32](../../tests/unit/test_trusted_auth.py#L32)。流释放测试 `test_asgi_disconnect_closes_body_iterator_and_graph` 见 [tests/integration/test_stream_cleanup.py:L25](../../tests/integration/test_stream_cleanup.py#L25)。这里是源码与测试审阅，未重跑。依赖范围见 [pyproject.toml:L9](../../pyproject.toml#L9)。

<a id="q232"></a>
### Q232：FastAPI项目Router、Service、Repository、Schema如何分层？

★ 核心题

#### 1. 标准答案

Router 处理 HTTP 输入、身份依赖、协议响应；Service 编排业务步骤、权限上下文及事务边界；Repository 封装查询与写入；Schema 声明跨边界的数据契约。ORM 模型负责持久化映射，不应直接等同对外响应。分层的目的是让业务规则和存储细节能独立验证，而不是每张表机械创建四套类。

事务通常由用例的上层统一提交，Repository 可 flush，但不随意各自 commit，否则“退款记录、订单状态、审计”会出现部分成功。领域异常由 API 层转换为统一错误格式；流式响应头发送后，则需要用流内错误事件表达失败。

#### 2. 面试口述版

我把 Router 控制在协议适配层：校验输入、拿可信身份和容器，再调用 Service。Service 编排限流、上下文、图执行与持久化，并决定一次业务事务何时提交；Repository 负责数据库读写，Schema 负责输入输出边界。项目聊天路由比较薄，真正流程在 ChatService；退款仓储只 flush，由外层统一提交，避免退款插入成功但订单状态没改。这样的拆分方便替换模型和测试仓储，不过项目不是每个用例都有一个独立 Service，工具也会经请求会话调用仓储。我会按真实职责介绍，不能把目录名字当作已经实现完整领域驱动架构的证据。

#### 3. Adaptive-RAG实际实现

`chat` 路由只传入 payload 与 trace，见 [app/api/routes/chat.py:L31](../../app/api/routes/chat.py#L31)；`ChatService.chat` 管理用例和提交，见 [app/services/chat_service.py:L88](../../app/services/chat_service.py#L88)。`OrderRepository.create_refund` 插入退款、更新订单、写审计并 flush，见 [app/repositories/order_repository.py:L62](../../app/repositories/order_repository.py#L62)。请求/响应 Schema 与 `OrderRow` 分离，见 [app/schemas/chat.py:L18](../../app/schemas/chat.py#L18) 和 [app/repositories/models.py:L15](../../app/repositories/models.py#L15)。

#### 4. 面试官可能追问

- **追问：Repository 能包含业务判断吗？** 答：可包含持久化必需的不变量，但复杂业务决策应集中在用例或领域规则；例如可见订单查询应落实所有者约束，不能只信 Router。
- **追问：为什么 Repository 不自己 commit？** 答：一个用例可能调用多个仓储；统一提交才能形成原子单元，内部 commit 会破坏外层回滚能力。
- **追问：怎么避免 Service 变成巨型类？** 答：按用例拆编排，抽取明确职责组件；不因文件长就随意拆分事务所有权和资源生命周期。

#### 5. 测试与证据

`test_refund_is_idempotent_and_transactional` 见 [tests/integration/test_orders.py:L34](../../tests/integration/test_orders.py#L34)；`test_order_is_scoped_to_owner` 见 [tests/integration/test_orders.py:L50](../../tests/integration/test_orders.py#L50)。这些是已有测试的检查点；必须结合 fixture 判断后端，不能把 SQLite 测试当成 PostgreSQL 并发锁验证。本轮未运行测试。

<a id="q233"></a>
### Q233：Pydantic Field、model_validate、model_dump、response_model有什么用？

★ 核心题

#### 1. 标准答案

Pydantic v2 的 `Field` 定义默认值、长度/数值约束和文档元数据；`model_validate` 将 Python 对象按模型进行验证转换，失败抛 ValidationError；`model_dump` 导出字典，`mode="json"` 将枚举、日期等转换为 JSON 兼容形式。`model_dump_json` 才直接得到 JSON 字符串。默认验证可能做类型转换，需要强类型语义时显式采用 strict 配置。

FastAPI `response_model` 声明输出验证、序列化、字段过滤与 OpenAPI 契约。它不是鉴权机制，也不会自动检查订单所有权；请求合法不代表业务操作获准。`Field(default_factory=list)` 避免用可变默认值表达意外共享状态。参考 [Pydantic v2 模型文档](https://docs.pydantic.dev/2.9/concepts/models/)。

#### 2. 面试口述版

这几个接口守住数据进出的边界。Field 声明消息长度约束，model_validate 把字典变成经过验证的模型，model_dump 把模型变回数据；给 JSON 使用时选 mode=json。response_model 让 FastAPI 按对外契约验证和过滤响应，避免暴露内部字段。项目 ChatRequest 限制消息和幂等键长度，ChatResponse 只列公开结果，Redis 取回 chunk 后也重新验证。但这些不等于安全授权：客户端 user_id 即使类型正确，也必须由服务端认证身份绑定，订单可见性还要再检查。验证失败和业务拒绝要分别处理。

#### 3. Adaptive-RAG实际实现

`ChatRequest.message` 限制 1–4000 字符，见 [app/schemas/chat.py:L18](../../app/schemas/chat.py#L18)；`chat` 声明 `response_model=ChatResponse`，见 [app/api/routes/chat.py:L31](../../app/api/routes/chat.py#L31)。`RedisRetrievalCache.get` 用 `RetrievedChunk.model_validate` 恢复对象，set 用 `model_dump(mode="json")`，见 [app/retrieval/cache.py:L64](../../app/retrieval/cache.py#L64)。验证异常转换成 422 统一错误体，见 [app/main.py:L102](../../app/main.py#L102)。

#### 4. 面试官可能追问

- **追问：`model_dump()` 等于 JSON 字符串吗？** 答：不是，它返回字典；`mode="json"` 仍是字典，只是值可 JSON 序列化；字符串使用 `model_dump_json()`。
- **追问：Schema 验证通过就能退款吗？** 答：不能。还要校验可信身份、订单归属、可退款状态、人工确认和幂等约束。
- **追问：缓存 JSON 损坏一定会作为 miss 吗？** 答：当前公共缓存仅捕获 Redis get 异常；JSON 解析与模型验证在捕获块外，可能继续抛错。不能声称已覆盖所有损坏载荷降级。

#### 5. 测试与证据

`test_empty_message_is_invalid_request` 断言空消息返回 422、稳定错误码与 trace，见 [tests/e2e/test_chat_api.py:L41](../../tests/e2e/test_chat_api.py#L41)。`test_redis_cache_mock_serialization_ttl_and_order_bypass` 见 [tests/unit/test_p4b_dependency_contracts.py:L47](../../tests/unit/test_p4b_dependency_contracts.py#L47)。后者使用 AsyncMock，不是实际 Redis；本轮未重跑。

<a id="q234"></a>
### Q234：HTTP流式响应SSE的协议格式是什么？与WebSocket差异？

★ 核心题

#### 1. 标准答案

SSE 使用 HTTP 响应，Content-Type 为 `text/event-stream`，UTF-8 文本按空行分隔消息。`data:` 是数据，可有多行并以换行拼接；`event:` 指定事件类型，默认 message；`id:` 与 `retry:` 支持原生 EventSource 的重连语义，冒号开头为注释。TCP/HTTP 数据块不等于事件边界，解析器要缓冲半行和半条消息。协议见 [WHATWG SSE](https://html.spec.whatwg.org/multipage/server-sent-events.html#parsing-an-event-stream)。

SSE 适合服务端单向持续推送；WebSocket 建立持久双向消息通道，支持二进制，适合客户端频繁交互。浏览器原生 EventSource 主要使用 GET；需要 POST 请求体和 Bearer header 时可用 fetch 读取 SSE，但必须自己处理解析、取消与重连。重连不等于业务幂等或断点续传。

#### 2. 面试口述版

SSE 是一条持续的 HTTP 响应，用 data 行和空行分帧，不是每个网络块就是一个 token。它适合聊天的服务端进度和文本推送；WebSocket 更适合高频双向交互和二进制。项目用 POST 加 fetch，因为要发送消息体和认证头，前端自己解析 SSE。服务端实际把业务事件写在 data 内的 JSON event 字段，不能混同协议 event 行。另一个关键是错误与取消：响应头发出后不能再改 HTTP 状态，要发送流内错误；用户断连时要关闭迭代器和图任务。项目的 token 也是最终答案验证后再分段发送，不能介绍成模型原始 token 实时直通。

#### 3. Adaptive-RAG实际实现

`chat_stream` 用 `JSONServerSentEvent(item)` 包装 JSON 数据，见 [app/api/routes/chat.py:L49](../../app/api/routes/chat.py#L49)；异常发送 JSON `error` 和 `done`，见 [app/api/routes/chat.py:L56](../../app/api/routes/chat.py#L56)。`ClosingEventSourceResponse` 保证断连后关闭 body iterator，见 [app/api/routes/chat.py:L20](../../app/api/routes/chat.py#L20)。`ChatService.stream` 在最终答案产生并提交后每 48 字符发送一段，见 [app/services/chat_service.py:L175](../../app/services/chat_service.py#L175)。前端 `consumeChatStream` 使用 fetch+reader+SseDecoder，见 [frontend/src/lib/api.ts:L111](../../frontend/src/lib/api.ts#L111)。项目未实现 SSE 事件持久化与 Last-Event-ID 恢复。

#### 4. 面试官可能追问

- **追问：连接中途报错为什么不能返回 500？** 答：响应头可能已提交；此时应发送应用错误事件并结束流，客户端不能把 done 当成成功，必须检查 error/answer。
- **追问：用了 SSE 就自动实时逐 token 了吗？** 答：没有。传输协议与生成策略独立；本项目优先保证输出校验，发送的是验证后的答案片段。
- **追问：重连会重复执行退款吗？** 答：可能重新发起请求；必须依靠服务端身份、确认和业务幂等，不能用网络连接 ID 代替业务幂等键。

#### 5. 测试与证据

`test_chat_stream_emits_token_and_node_events` 从 data 行解析 JSON，并断言拼接 token 等于最终 answer，见 [tests/e2e/test_chat_api.py:L50](../../tests/e2e/test_chat_api.py#L50)。ASGI 断连释放见 `test_asgi_disconnect_closes_body_iterator_and_graph` [tests/integration/test_stream_cleanup.py:L25](../../tests/integration/test_stream_cleanup.py#L25)。这是已有离线/模拟路径测试，未在本轮运行，不证明公网代理刷新或十万并发。
