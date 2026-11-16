# 2026 Agent 开发 / Python 后端面试题库（以公开面经为起点）

> 整理日期：2026-11-16。题目来源：牛客等公开面经、Reddit真实面试讨论、常见技术追问与官方文档。非企业官方题库，也不是抽样统计后的题目出现率排名。
>
> 优先级：★ 为建议**第一轮必会**（在公开面经反复出现或直接对应 Adaptive-RAG）；其余为深挖/拓展，并不等于完全不考。
>
> 口径：本题库“你的项目”默认指 Adaptive-RAG。实际实现以源码和运行报告为准。已通过真实DeepSeek的订单 Tool Calling、Memory、RAG、异常降级；真实HITL尚未完成端到端付费测试。

## 如何使用

1. 先准备每节★题：能用自己的项目讲清机制、为何这样设计、故障与证据。
2. 对RAG/Agent核心题准备“定义 → 方案 → 取舍 → 失败处理 → 评测”答案，避免只背框架名字。
3. 对后端与系统设计题准备可运行SQL、Python示例或简图。
4. ★题掌握后再刷进阶题；不要把未实现/未测试的能力描述为已上线。

## 全量题库

### 01｜项目架构与个人贡献（项目面试开场）（13题）

1. **★ 3分钟介绍你的 Adaptive-RAG，实际解决什么业务问题？**
2. **★ 从用户输入到最终回答，画出前端、FastAPI、LangGraph、工具和数据库的完整链路。**
3. **★ 为什么这个问题需要 Agent，不直接调用一次 LLM？**
4. **★ 为什么不全部采用固定 Workflow 或规则引擎？**
5. **★ 哪些模块由你独立设计，哪些复用已有组件或 AI 辅助生成？**
6. **★ 最难的真实 Bug 是什么？如何保存证据、定位根因并验证修复？**
7. 用了哪些组件？PostgreSQL、Redis、Qdrant 各自负责什么？
8. 如何区分 Offline 演示、MockTransport 和真实 DeepSeek 端到端验证？
9. 最重要的业务指标是什么，为什么不是只看模型回答是否流畅？
10. 如果把 LangGraph 删除、自己用 Python 编排，哪些能力要重新实现？
11. 项目有多少真实用户？如未正式上线，如何准确介绍验证范围？
12. 如何证明你写在简历上的成功率/性能数字是真的？
13. 如何用5分钟现场演示工具调用、RAG引用、权限隔离？

### 02｜Agent、Workflow、LangGraph 与编排（24题）

14. **★ Agent 与普通 LLM 应用、RAG、Workflow 的本质区别是什么？**
15. **★ Workflow 和 Agent 的优缺点是什么？什么时候用哪一个？**
16. **★ LangGraph 为什么适合你的系统？为什么不用纯 Python if/else？**
17. **★ LangChain 与 LangGraph 的定位和联系？**
18. **★ StateGraph 的 Node、Edge、Conditional Edge、State 分别是什么？**
19. **★ LangGraph 的 State 如何定义、更新与合并？Reducer 何时需要？**
20. **★ 你们的 Intent、Router、Retrieval、Generate、Faithfulness 和 Memory 节点为何这样分？**
21. **★ 工具调用是由 LLM 规划还是由图中的代码决定？如何划分控制权？**
22. **★ ReAct 的 Thought/Action/Observation 循环是什么？与固定流水线有何区别？**
23. **★ 如何限制 Agent 最大迭代轮数、避免死循环、重复工具调用？**
24. LangGraph 的条件路由如何实现？如何处理无效路由输出？
25. Command、Send 及并行分支在什么场景使用？
26. 什么是 Plan-and-Execute？与 ReAct 比较延迟、可控性、失败恢复。
27. 反思 Reflection 节点什么情况下能提升质量，什么情况下只是浪费 Token？
28. 如何做动态工具选择与工具集合裁剪？
29. 如何在图上实现失败重试、fallback、超时与终止条件？
30. Graph State 与数据库持久会话、LLM Context 有何区别？
31. 什么是 checkpoint 和 thread_id，如何断点恢复？
32. interrupt 与 resume 如何实现 HITL？恢复后如何防重复执行？
33. 多节点并发读写共享 State 会有什么冲突？
34. 图执行到一半进程崩溃，恢复时已发出的外部动作如何判定？
35. 静态 Workflow 能不能使用 LangGraph？为什么二者不是互斥选项？
36. 如何在单 Agent 与多 Agent 之间做技术取舍？
37. 何时值得用自研轻量 orchestrator 而不是框架？

### 03｜RAG 文档解析、清洗与切片（Chunking）（22题）

38. **★ RAG 文档入库的完整链路是什么？从文件上传开始讲。**
39. **★ 你如何切分 Markdown、TXT、PDF、Word、HTML？为什么不同格式不能简单一刀切？**
40. **★ 固定长度、递归、按语义/标题、父子块切片分别怎么做？**
41. **★ Chunk Size 与 Overlap 怎么选，有什么指标验证？**
42. **★ 切块太小与太大会分别造成什么问题？**
43. **★ 表格、代码块、图片、扫描PDF怎么处理？**
44. **★ 如何保留标题路径、章节、来源页码、Offset、版本和权限元数据？**
45. **★ RecursiveCharacterTextSplitter 的 chunk_size 是字符还是 Token？如何避免单位混淆？**
46. 为什么切片前要清理页眉页脚、目录、重复换行、无效字符？
47. 遇到跨页表格、嵌套列表、脚注和公式怎么办？
48. PDF是文本层还是扫描件，怎样识别并选择解析工具？
49. 怎么评估解析质量和段落顺序是否错乱？
50. 标题单独切成块会有什么风险？如何让每块带回父标题？
51. 什么是 Parent-Child Retrieval（小块检索，大块返回）？
52. 什么是相邻块扩展、窗口检索和标题层级检索？
53. 长文档中前后跨段才能回答的问题怎么处理？
54. 文档里既有描述又有大量唯一编号时，切片策略如何调整？
55. 知识库重复文档或旧版本文档如何去重与更新？
56. 文档删除后如何删除相关 chunk、向量与缓存？
57. Embedding 模型升级导致维度变化，如何进行重建或双索引迁移？
58. 切片策略变更后如何验证检索质量没有退化？
59. 如何为每个 chunk 生成稳定ID，避免引用失效？

### 04｜Embedding、向量检索、BM25、融合与重排（24题）

60. **★ 用户 Query 也需要 Embedding 吗？离线建索引和在线查询如何对应？**
61. **★ BM25 的基本原理是什么？它比向量检索在哪些问题上更强？**
62. **★ Dense Retrieval 为什么能找同义表达，在哪些情形会失败？**
63. **★ 为什么采用 BM25 + Dense 混合检索，而不是只用向量搜索？**
64. **★ RRF 的公式、参数 k 和两路融合流程是什么？**
65. **★ 为什么不能直接把 BM25 分数和余弦相似度加起来？**
66. **★ 为什么粗召回后还要 Cross-Encoder Rerank？优缺点是什么？**
67. **★ Top-K（各路召回K、合并K、重排N）怎么选择？**
68. **★ 什么是 Recall@K、MRR、nDCG，如何比较不同检索链？**
69. Embedding 模型选型看哪些指标（语言、维度、成本、领域、速度）？
70. 余弦相似度、点积、L2 距离的差异和归一化影响？
71. ANN 与精确 KNN 的区别，HNSW 为什么快？
72. Qdrant 与 Milvus、FAISS、Elasticsearch、pgvector 怎么选择？
73. Qdrant metadata filter 在搜索时起什么作用？
74. 用户 Query 改写有哪些策略（指代消解、多查询、HyDE、扩展）？
75. 什么时候 Query Rewrite 会改变用户原意？如何回退？
76. 多路召回如何去重？源文档不同版本如何处理？
77. 使用 Cross-Encoder 为什么通常更慢，如何控制推理开销？
78. Reranker 把正确证据排下去，如何诊断？
79. 怎样选择检索相关性阈值，为什么不能固定通用阈值？
80. 检索不到时应问用户澄清、拒答，还是网络搜索？
81. 检索命中但答案仍不对，怎么区分检索和生成故障？
82. 知识库千万级规模如何做分区、批量索引和增量更新？
83. 怎样做混合检索消融实验并保证公平（固定Query、数据集、模型）？

### 05｜RAG 生成、引用与幻觉治理（15题）

84. **★ RAG回答如何保证引用的chunk真正支持所述结论？**
85. **★ 检索到正确片段，为什么LLM仍可能幻觉？**
86. **★ 如何区分“知识库无资料”“召回失败”“生成未利用证据”？**
87. **★ Faithfulness/Groundedness 的含义？怎样评测？**
88. **★ 遇到相互冲突或过期政策时如何回答？**
89. 引文 ID、文档ID、页码及权限如何贯通到生成结果？
90. 如何避免用户下载或引用他人私有文档？
91. Context 组装中如何去重、截断及控制 token预算？
92. 怎么解决“lost in the middle”？
93. 什么情况下固定模板回答比生成式回答更合适？
94. 为什么仅靠Prompt写“不知道就说不知道”不够？
95. 怎样检测数字、日期、金额、订单状态等事实错误？
96. 有什么无答案拒答率、误拒答率的评测方法？
97. RAG vs 长上下文直接塞原文 vs 微调如何选择？
98. 如何处理结构化数据库事实和文本知识库同时参与回答？

### 06｜Tool Calling、Function Calling、MCP、Skill（22题）

99. **★ Function Calling 的完整链路：模型建议、参数校验、工具执行、结果回灌是什么？**
100. **★ Function Calling 与MCP有什么区别？Tool、Skill又分别是什么？**
101. **★ Tool Schema如何定义？参数类型、必填、枚举、描述为什么影响准确率？**
102. **★ 模型编造工具名、参数或非法订单号时如何处理？**
103. **★ 为什么不能相信LLM宣称“订单已取消”，必须检查真实业务结果？**
104. **★ 工具有副作用时如何做HITL、幂等和事务？**
105. **★ 工具调用超时、429、5xx、空结果、部分成功分别怎么办？**
106. **★ 查询工具与修改工具如何分级授权？**
107. 什么时候把业务能力封装成普通函数、HTTP API、MCP server、Skill？
108. 几十上百个工具时如何缩小候选集、做语义路由？
109. 工具说明要写“能做什么”还是“什么时候用”？
110. 模型调用工具之前是否需要用户身份与授权上下文？
111. 工具参数到底由模型生成还是后端确定？哪些字段不得由模型填写？
112. 如何设计工具结果的数据结构，减少模型误读？
113. 如何在多轮里引用上一次工具结果，又不误用旧状态？
114. 一轮中调用两个独立工具可否并行？有副作用时怎么办？
115. 模型是否可直接执行SQL？Text-to-SQL 如何限权及验证？
116. 如何设计只读查询与写操作的不同安全沙箱？
117. MCP的Resources、Prompts、Tools分别解决什么问题？
118. MCP客户端、服务端和认证边界如何划分？
119. 模型调用失败后什么时候允许重试，什么时候必须先查实际操作是否成功？
120. 如何衡量工具选择准确率与参数准确率？

### 07｜Memory、上下文与多轮会话（16题）

121. **★ Short-term Memory 与 Long-term Memory 如何划分？**
122. **★ 你项目里的M0/M1/M2分别是什么？效果如何验证？（以代码报告为准）**
123. **★ 用户问“那这个订单的商品呢”，如何消解“这个”指代？**
124. **★ 会话历史、LangGraph State、Memory、知识库有什么区别？**
125. **★ 上下文太长时滑窗、摘要、检索式记忆各有什么风险？**
126. **★ 哪些信息绝对不能在摘要压缩时丢失？**
127. 记忆写入时机如何选？每轮写还是按重要度筛选？
128. 记忆如何去重、版本更新、冲突消解和纠错？
129. Memory 写入“用户偏好”会污染跨用户会话吗？
130. 会话与租户ID的绑定由谁负责，如何防止注入别人的Memory？
131. 摘要出错或记错订单号怎么办？
132. 如何评估历史指代成功率和记忆召回有效性？
133. Memory 会增加Token和延迟，如何测量净收益？
134. 删除用户数据时如何清理Memory、历史、缓存及索引？
135. 如何防止过时记忆覆盖最新工具查询结果？
136. 长期记忆能否承载执行授权和安全规则？为什么不能？

### 08｜Prompt、Context Engineering 与模型基础（15题）

137. **★ System/Developer/User/Tool消息分别承担什么职责？**
138. **★ Prompt Engineering 与 Context Engineering有什么差异？**
139. **★ Zero-shot、Few-shot、CoT、ReAct和结构化输出分别适合何时用？**
140. **★ 为什么一条提示词不能保证工具调用安全或事实正确？**
141. **★ temperature、top_p、max_tokens、上下文窗口的实际影响？**
142. 上下文里工具Schema和检索文档的排序如何影响结果？
143. Prompt注入文档会不会覆盖系统指令，如何隔离？
144. JSON结构化输出总是有效吗？失败、截断如何处理？
145. DeepSeek thinking/non-thinking 模式对结构化输出和延迟有什么影响？
146. 如何做提示词版本化、A/B对照及回归测试？
147. 如何通过减少无用工具Schema降低Token和延迟？
148. 什么是KV Cache / prompt cache，为什么请求更短不一定更便宜？
149. 什么是Token，它与中文字数/字符数的关系？
150. 为什么同一输入模型输出可能不同？怎么设计稳定回归？
151. OpenAI兼容API与不同供应商的字段、流式协议可能有什么差异？

### 09｜评测体系、数据集、指标与消融（20题）

152. **★ 如何定义Agent任务成功率，能只用“模型回答看起来对”吗？**
153. **★ 如何搭建RAG评测集，问题、金标准证据和答案从哪来？**
154. **★ 如何分别评估检索、Rerank、生成及整个Agent任务？**
155. **★ 工具选择、参数正确性、执行成功率分别怎么算？**
156. **★ Recall@K、Precision@K、Hit@K、MRR、nDCG的差别？**
157. **★ 为什么要有无答案、歧义、越权、工具失败、冲突政策样本？**
158. **★ 如何做BM25/Dense/RRF/Rerank的消融？**
159. **★ 如何做Memory M0/M1/M2对照，排除随机性和测试污染？**
160. LLM-as-a-Judge有哪些偏差？如何结合人工和规则验证？
161. 评测集主要用LLM生成，怎么保证质量及防泄漏？
162. 每次改Prompt/Graph如何跑离线回归与E2E？
163. 如何设置重试和温度，保证版本间公平？
164. 质量、P95延迟、Tokens、费用如何做多目标权衡？
165. 线上badcase如何归因到检索、规划、工具、生成或数据？
166. 模型升级如何做shadow / canary / rollback？
167. Faithfulness、citation correctness、answer completeness如何人工标注？
168. 什么时候评估“没有成功调用工具”，什么时候算“正确拒答”？
169. 统计样本量太小时为什么不能宣称显著提升？
170. 如何追踪每一轮评测使用的模型、文档版本和代码commit？
171. 高风险操作的评测为什么不能只看LLM评分？

### 10｜权限、安全、HITL 与审计（18题）

172. **★ Prompt Injection是什么？检索文档里的恶意指令如何防护？**
173. **★ RAG多租户隔离为什么不能只在前端隐藏文档？**
174. **★ 授权过滤必须覆盖BM25、向量、缓存、引用、历史哪些环节？**
175. **★ HITL的业务流程、审批凭证、恢复机制如何实现？**
176. **★ 用户重复点击确认为什么不能重复取消订单？**
177. **★ Agent如何防止越权操作、工具参数注入、SQL注入和SSRF？**
178. 最小权限原则如何落实到工具注册、数据库账户与外部API？
179. 为什么不能将API Key放浏览器或Trace？
180. Bearer/JWT鉴权如何实现？Access与Refresh Token的边界？
181. 敏感操作如何做审计与防重放？
182. HITL审批后进程崩溃，再恢复怎样判定是否已经执行？
183. 工具回包含隐私信息，如何脱敏同时保留排障证据？
184. 如何防止私有KB“索引污染”和跨租户召回？
185. 什么时候使用人工确认、什么时候直接拒绝请求？
186. 为什么不能让模型自己生成授权令牌/幂等Key？
187. 恶意用户通过长Prompt耗尽预算，如何限流？
188. API Key泄露后如何轮换与定位？
189. 安全测试至少有哪些无认证、跨Owner、假主体、恶意文件用例？

### 11｜性能、费用、可观测性与线上故障（18题）

190. **★ 一个用户请求为什么会触发多次模型API请求？怎样定位每次Token消耗？**
191. **★ 你项目里首次1207实际Token却预留8986，如何解释？**
192. **★ 为什么需要费用预留、可信usage结算和不可确定消费阻断？**
193. **★ Trace中如何关联Graph节点、模型请求、工具、数据库与返回事件？**
194. **★ P50/P95/P99、QPS、吞吐量、错误率怎么测？**
195. 如何用超时预算和取消传播避免长尾请求拖垮服务？
196. 怎样做LLM批处理、并行检索和模型路由而不破坏依赖关系？
197. Redis或Qdrant不可用如何降级，哪些操作必须fail-closed？
198. 何时使用熔断、退避重试和限流？
199. 发生429是否总应该重试？如何控制重试风暴？
200. SSE已发送部分数据后失败，HTTP状态码还能更改吗？
201. 模型调用成功但usage日志未结算，如何保守处理？
202. DeepSeek响应压缩解码不一致会导致什么Bug？
203. 如何从Trace定位“订单工具没执行”，而不是猜模型效果不好？
204. 模型延迟增加2倍，如何拆分排查DNS、TLS、路由、生成和下游工具？
205. 费用限额的并发原子预留如何保证不超扣？
206. 如何设计安全的灰度发布与回滚？
207. 缓存命中改善但业务任务成功率下降，如何解释？

### 12｜Python语言、异步与并发（22题）

208. **★ 进程、线程、协程区别？Python GIL影响什么？**
209. **★ async/await、事件循环与Task是如何工作的？**
210. **★ CPU密集任务与IO密集任务如何选async、线程、进程？**
211. **★ async函数中使用同步requests或time.sleep为什么会卡住？**
212. **★ asyncio.gather、TaskGroup、Semaphore有什么差异？**
213. **★ Python装饰器、闭包和functools.wraps怎么用？**
214. Python list、tuple、dict、set的底层和复杂度？
215. 什么是可变默认参数陷阱？
216. 什么是浅拷贝、深拷贝、引用传递？
217. 生成器、迭代器、yield、async generator区别？
218. 上下文管理器with / async with如何清理资源？
219. 异常传播、finally、取消异常怎么处理？
220. classmethod、staticmethod和实例方法的区别？
221. __new__与__init__的执行顺序？
222. Pydantic的model_dump与普通dict有什么区别？
223. Python对象的垃圾回收、引用计数、循环引用？
224. 什么情况下ThreadPoolExecutor比asyncio更合适？
225. 如何实现带TTL的LRU缓存？
226. 如何限制并发请求数并保持结果顺序？
227. 多进程部署时内存状态为什么不能共享？
228. 线程安全、协程安全、进程安全分别是什么意思？
229. 如何为Python模块做类型标注、Mypy和Ruff校验？

### 13｜FastAPI、HTTP/SSE、测试（20题）

230. **★ FastAPI Depends为什么不用直接调用函数？何时创建/释放依赖？**
231. **★ async def与def路由的执行区别是什么？**
232. **★ FastAPI项目Router、Service、Repository、Schema如何分层？**
233. **★ Pydantic Field、model_validate、model_dump、response_model有什么用？**
234. **★ HTTP流式响应SSE的协议格式是什么？与WebSocket差异？**
235. **★ SSE断连、超时、取消、重连、心跳怎么处理？**
236. FastAPI中间件如何处理request_id、日志、异常？
237. ASGI、Uvicorn、Gunicorn worker分别起什么作用？
238. FastAPI BackgroundTasks与Celery分别适合什么场景？
239. 如何设计同步/异步SQLAlchemy Session生命周期？
240. 数据库Session为何不应全局跨请求共享？
241. 什么是依赖覆盖 dependency_overrides，如何用于测试？
242. HTTP 400/401/403/404/409/422/429/503何时使用？
243. JWT验证签名、audience、issuer、exp的注意事项？
244. OAuth2与JWT、Bearer有什么关系？
245. API版本化、OpenAPI和统一错误码怎么设计？
246. 如何写pytest fixture、AsyncClient、集成测试、E2E？
247. 如何用契约测试Mock LLM API，却保留真实数据库工具执行？
248. HTTP超时后客户端重试同一写操作，如何保持幂等？
249. 浏览器CORS是否等于认证机制？为何不是？

### 14｜数据库 PostgreSQL / MySQL 与事务（18题）

250. **★ 为什么Agent业务数据用PostgreSQL，而向量库用Qdrant？**
251. **★ SQL索引B+树原理、联合索引最左匹配和回表？**
252. **★ 什么是事务ACID与隔离级别？并发异常有哪些？**
253. **★ 如何设计订单查询的索引并通过EXPLAIN验证？**
254. **★ 数据库连接池如何设置？FastAPI多worker时总连接数怎么算？**
255. SQLAlchemy AsyncSession如何commit、rollback、flush与refresh？
256. 什么是MVCC，PostgreSQL与MySQL在RR隔离下差异？
257. 如何用条件UPDATE防超卖？
258. 读-改-写为何容易丢失更新？
259. 数据库唯一约束和应用层先查再插的区别？
260. 幂等Key如何设计、冲突如何处理？
261. 什么是行锁、死锁、锁顺序、SKIP LOCKED？
262. 读多写少场景的分页：offset vs keyset？
263. 为什么不能用Redis缓存作为订单最终事实源？
264. 慢SQL如何定位，怎么使用EXPLAIN ANALYZE？
265. Alembic迁移如何兼容已有数据与回滚？
266. Outbox模式解决什么窗口问题？
267. 多租户数据如何避免跨Owner查询泄露？

### 15｜Redis、消息队列、Celery与任务可靠性（18题）

268. **★ Redis常见数据类型和Agent中的典型用途？**
269. **★ 缓存穿透、击穿、雪崩分别如何解决？**
270. **★ 为什么用Redis限流或幂等辅助，而不让Redis决定订单库存？**
271. **★ Redis Lua脚本怎样实现原子限流？**
272. **★ Celery与FastAPI BackgroundTasks区别？**
273. **★ 消息至少一次投递和Exactly-once业务效果如何区分？**
274. **★ Celery acks_late、重试、重复消费和幂等性如何配合？**
275. Redis分布式锁适合什么、不适合什么？
276. Redis持久化RDB与AOF区别？
277. Redis作为broker与RabbitMQ/Kafka的取舍？
278. 数据库已提交但消息没发出去怎么办？Outbox如何解决？
279. 怎么用定时扫描补偿超时订单或未完成任务？
280. Redis宕机时限流和关键写操作应该fail-open还是fail-closed？
281. 消费者被kill -9、消息重复投递，怎么测试恢复？
282. 什么是缓存一致性、Cache-Aside、TTL、主动失效？
283. 怎样处理大Key、热Key、内存淘汰和连接数耗尽？
284. 多worker共享的幂等记录应该放在哪里？
285. 消息积压时如何区分生产过快与消费能力不足？

### 16｜Docker、Linux、网络、CI/CD与监控（16题）

286. **★ 从浏览器到FastAPI再到DeepSeek API经历哪些网络环节？**
287. **★ HTTP与HTTPS、TLS握手、证书链是什么？**
288. **★ Docker image、container、volume、network区别？**
289. **★ Compose的depends_on为何不等于服务真正可用？**
290. **★ Docker容器内的localhost和宿主机localhost为什么不同？**
291. **★ 一套服务为何会启动4个长期容器，怎么确认健康？**
292. 如何区分镜像build和运行时pip安装，对宿主Conda有什么影响？
293. Docker Compose更新API镜像怎么保护Postgres数据卷？
294. 如何排查DNS、代理、TLS、端口冲突、API 502/503？
295. Linux用哪些命令查CPU、内存、网络、进程与文件描述符？
296. Docker容器日志怎样关联Trace ID？
297. Git的merge、rebase、cherry-pick和worktree有什么区别？
298. CI中怎样运行pytest、Ruff、Mypy、前端构建与真实服务集成测试？
299. 配置与Key为何不应进入仓库和日志？
300. 服务故障时如何最小化回滚而不清空数据库？
301. 如何设置发布回归门槛与失败证据留存？

### 17｜LLM原理、模型选型与基础算法（15题）

302. **★ Transformer与self-attention基本机制是什么？Q、K、V如何理解？**
303. **★ Embedding模型与生成模型有什么不同？**
304. **★ 预训练、SFT、DPO、RLHF、LoRA/QLoRA的适用场景？**
305. **★ RAG与微调是替代还是互补？**
306. **★ 什么是KV Cache，推理时为什么有Prefill和Decode阶段？**
307. 什么是Tokenization、最大上下文、输出截断？
308. Temperature和Top-p如何影响概率采样？
309. MoE与稠密模型有什么区别？
310. 大模型量化（4bit/8bit）对内存和效果的影响？
311. 推理部署吞吐、首Token延迟TTFT、Tokens/s如何测？
312. 开源模型与API模型如何从成本、隐私、延迟选择？
313. 模型能力、工具调用协议与API兼容性为什么要分开验证？
314. 为什么模型输出不保证JSON正确？
315. 为什么LLM Judge可能和被评模型有共同偏差？
316. 什么任务应交给传统规则/SQL而不是LLM？

### 18｜Multi-Agent、A2A、Skill与长任务高级题（15题）

317. **★ 单Agent与多Agent怎么权衡，什么情况下不值得拆分？**
318. **★ Supervisor/Worker、Planner/Executor、辩论与并行专家模式区别？**
319. **★ 多Agent共享状态、Memory和工具权限如何隔离？**
320. **★ 两个Agent并发写同一文件或数据库怎样避免冲突？**
321. **★ 多Agent会增加哪类Token、延迟和错误传播成本？**
322. Agent-to-Agent协议与MCP是什么关系？
323. 什么是Skill的渐进披露，适合哪些工具集合？
324. 长任务如何做断点续跑、取消、checkpoint和进度可视化？
325. 什么是Sandbox？与RBAC、审批的区别？
326. 代码执行Agent如何防命令注入和越权文件访问？
327. 怎么检测Agent路径震荡或无限自我反思？
328. Agent自学习/经验记忆为什么需要离线评测、审核与灰度？
329. 工具目录有几百项，如何设计Tool Registry和动态搜索？
330. 模型换代后Graph/工具Schema/Memory如何兼容？
331. 什么时候需要Model Gateway和多模型路由？

### 19｜系统设计场景题（需要画图）（13题）

332. **★ 设计企业内部私有知识库RAG：支持PDF/Word、100万文档与多租户权限。**
333. **★ 设计客服Agent：能查询订单、退货政策、取消订单，危险操作需人工确认。**
334. **★ 设计Agent平台的请求级配额和费用账本，保证并发不超额。**
335. **★ 设计支持10万并发用户的SSE聊天服务，你如何限流、扩容和取消？**
336. **★ 设计实时索引更新：用户上传新文档后多久能检索，删除如何生效？**
337. **★ 设计Tool Calling执行网关，如何做授权、审计、重试、幂等和隔离？**
338. **★ 设计Agent多轮Memory，支持跨设备会话恢复和删除用户数据。**
339. 设计支持离线演示和真实付费模型的双模式系统，如何隔离配置和身份？
340. 设计Agent Eval Pipeline：历史Badcase、离线回归、灰度、回滚。
341. 设计异步文档解析任务：Celery + PostgreSQL + Redis + Qdrant，失败怎样恢复？
342. 设计多模型Fallback机制：供应商超时、限流、价格变化时怎么办？
343. 设计跨租户检索：如何证明无论BM25、向量还是缓存均不能泄露私有信息？
344. 设计Agent取消操作：模型做计划，人确认，数据库幂等提交，重复请求不重复取消。

### 20｜手写代码、SQL与算法现场题（16题）

345. **★ 手写一个最小FastAPI路由，接收Pydantic输入、Depends注入Session并返回response_model。**
346. **★ 手写一个可并发安全的工具参数校验与分发函数。**
347. **★ 手写asyncio.Semaphore控制并发调用3个API，支持超时和取消。**
348. **★ 手写SSE StreamingResponse迭代器，包含event/data/error与客户端断连处理。**
349. **★ 手写Redis限流思路（令牌桶或滑动窗口），解释原子性。**
350. **★ 写SQL：查询用户最近20条订单，按时间+ID稳定分页。**
351. **★ 写SQL：条件扣库存并在同一事务插入订单、处理幂等。**
352. 用Python实现LRU Cache、TTL缓存或带容量限制的队列。
353. 实现Top-K高频元素（堆/桶）、字符串无重复最长子串。
354. 实现二叉树层序遍历、右视图、最近公共祖先。
355. 实现课程表拓扑排序与环检测。
356. 实现单词拆分、零钱兑换等基础动态规划。
357. 手写BM25简化评分并说明TF/IDF与长度归一化。
358. 手写RRF多路融合，处理重复chunk ID。
359. 给定检索结果与标准相关标签，计算Recall@5和MRR。
360. 设计pytest并发用例验证同一幂等Key不产生重复业务副作用。

## 8 个代表性问题的答题骨架（起步版）

**1. 为什么LangGraph而不是固定Workflow？** 简单、可预测流程应优先固定Workflow；多步动态工具选择、状态分支、人工中断与恢复会提升图编排的价值。LangGraph本身既可写固定Workflow也可写Agent，二者不互斥。说明项目哪里使用确定性约束、哪里允许LLM选择，以及相应Trace证据。

**2. RAG文档怎么切片？** 先抽取并清洗结构，按标题/段落/表格保留语义单元，再基于Token预算拆分，必要时少量overlap、父子块、相邻段扩展。块携带doc_id、owner_id、version、page、标题路径。使用固定评测集比较召回、引用正确率、成本和延迟，不能说固定500字总是最优。

**3. BM25+Dense+RRF+Rerank为什么组合？** BM25强于精确编号与术语，Dense补语义别称；RRF用排名融合避免不同打分尺度直接相加；Cross-Encoder对召回候选做更细语义比较，但有延迟成本。需要比较消融效果，Rerank不能找回根本没召回的材料。

**4. 没有检索证据怎么办？** 先区分KB无数据、权限被过滤、Query改写失败、Embedding匹配差与索引延迟。不能由模型补写不存在的政策；应拒答/澄清/转人工。链路中保留已授权引用ID与Trace，不能通过绕过Owner过滤提升召回。

**5. 模型怎样调用工具？** 模型按Schema提出工具名与参数，服务端独立验证、鉴权、控制幂等并执行；将真实结果回灌模型，最终回答再次核对状态。写操作需要明确授权与HITL，不能信任模型“已完成”的自然语言。

**6. Memory如何实现？** 划分Session历史、短期上下文、摘要和长期结构化记忆；按任务和用户权限作用域隔离。关键订单ID应先恢复再调用工具核验，不能把历史模型叙述视为数据库事实。

**7. Agent怎么评测？** 拆检索的Recall@K/MRR/nDCG、工具名/参数准确率、业务真实效果、引用忠实性、无答案拒答、延迟和Token成本。通过固定Badcase与源版本、模型版本记录支持回归；统计结果必须注明样本量。

**8. FastAPI中的async有什么坑？** `async def`可在await等待IO时让出控制权，但在其中直接调用阻塞库会堵住事件循环；FastAPI的同步`def`路由和同步依赖一般通过线程池调度，普通函数直接调用不自动进入线程池。需要限制连接池/并发并正确传播取消。

## 公开面经与官方参考（部分）

- 牛客：字节Agent开发（RAG切片、BM25/Dense/RRF/Cross-Encoder、LangGraph与评测） https://www.nowcoder.com/discuss/940040254214389760
- 牛客：阿里AI应用（RAG切块、Qdrant/向量库选型、LangGraph State） https://www.nowcoder.com/discuss/923740158455730176
- 牛客：字节AI全栈（SSE、API幂等、Redis、Python并发） https://www.nowcoder.com/discuss/930603820395036672
- 牛客：分享AI应用开发面经（FastAPI、数据库、检索、MCP） https://www.nowcoder.com/feed/main/detail/9a63e7a92fe24513a99c5bb47457e031
- Reddit：LangGraph Agentic RAG面试的准确率、安全等追问 https://www.reddit.com/r/LangChain/comments/1k662xc/got_grilled_in_an_ml_interview_today_for_my/
- Reddit：RAG系统设计深挖评测与chunking https://www.reddit.com/r/OfferEngineering/comments/1x54sxn/rag_system_design_interviews_the_pipeline_is_the/
- LangGraph官方：Workflows and Agents https://github.com/langchain-ai/docs/blob/main/src/oss/langgraph/workflows-agents.mdx
- FastAPI官方：Concurrency and async/await https://fastapi.tiangolo.com/async/
