# RAG 切片与检索答案

> 本章按原题编号组织。源码能力、实际启用模式和历史验收分别说明；“测试与证据”列出可复核的测试定义，不表示本轮执行了业务测试。

<a id="q038"></a>
### Q038：RAG 文档入库的完整链路是什么？从文件上传开始讲。
★核心60

#### 1. 标准答案

典型链路是鉴权及文件类型/大小校验→保存原件和文档版本→解析正文、标题、页码与表格→清洗去重→切片并绑定来源和 ACL→批量 Embedding→写向量索引、词法索引及权威元数据→发布可检索版本。任务状态应区分接收、解析、索引中、可检索和失败；幂等键避免重复上传产生重复块。更新要让检索读取一致的版本，删除需同时撤销权威权限、失效缓存并清理索引。只有向量写入成功，不能证明 BM25、权限和版本都已同步。

#### 2. 面试口述版

我会先分清文件导入和在线知识接口。通用文件入库先验证身份、格式和大小，保留原件，再解析结构、清洗去重、切片、生成向量，最后发布带版本和权限的检索数据。我的项目有两条实际链路：公共知识目录由 Ingestor 解析后建立 BM25 和向量记录；私有知识接口接收标题和正文，由认证身份确定归属，SQL 保存版本，再更新私有向量与缓存版本。它目前不是一个 PDF 文件上传平台。我会用入库后能检索、更新后只见新版本、删除后不可见以及其他用户不能访问来验证闭环，不能只展示接口返回成功。

#### 3. Adaptive-RAG实际实现

**已实现**公共目录导入：`KnowledgeIngestor.load()` 枚举受支持文件，在线程中调用 `parse_path`，去重后批量 `embed` 并 `build_records`；`ingest_knowledge()` 建立 BM25，配置 Qdrant 时写入，公共链路失败可回退内存。[app/retrieval/ingest.py:L79](../../app/retrieval/ingest.py#L79)、[app/retrieval/ingest.py:L116](../../app/retrieval/ingest.py#L116)。

**已实现**私有正文 CRUD，`DocumentInput` 接收 `title/content`，不是 `UploadFile`；`put()` 用验证后的 `principal.subject`，提交 SQL 事务。[app/api/routes/knowledge.py:L18](../../app/api/routes/knowledge.py#L18)、[app/api/routes/knowledge.py:L55](../../app/api/routes/knowledge.py#L55)。私有检索要求 PostgreSQL scope，不能套用公共共享库回退。[app/retrieval/private.py:L126](../../app/retrieval/private.py#L126)。**项目未实现**通用文件上传任务队列及完整的多格式上传状态机。

#### 4. 面试官可能追问

- **追问：Embedding 成功而 SQL 提交失败怎么办？** 答：以 SQL 文档版本为可见性权威，未授权或不属于当前 revision 的向量不能成为证据；残留向量通过对账清理。
- **追问：公共 Qdrant 回退能用于私有库吗？** 答：不能直接复用。私有路径应保留身份与 SQL 权威约束，依赖失败时关闭检索，避免回退共享语料泄露。
- **追问：如何证明这不是文件上传系统？** 答：检查接口 schema：现有私有入口是 JSON 标题和正文，目录解析器则读取已有本地文件，两者没有通用二进制上传接口。

#### 5. 测试与证据

`test_hybrid_retrieves_return_policy` 从 `knowledge` 导入、建立内存混合检索并检查返回政策，使用 **HashEmbeddingProvider**，不能证明真实语义模型质量。[tests/integration/test_hybrid_retrieval.py:L11](../../tests/integration/test_hybrid_retrieval.py#L11)。`test_parse_path_uses_injected_partition` 验证注入解析器路径。[tests/unit/test_unstructured_parser.py:L127](../../tests/unit/test_unstructured_parser.py#L127)。完整多格式上传端到端：**未实现/未验证**。本轮只核对源码和测试定义。

<a id="q039"></a>
### Q039：你如何切分 Markdown、TXT、PDF、Word、HTML？为什么不同格式不能简单一刀切？
★核心60

#### 1. 标准答案

先按格式还原结构，再切片。Markdown 利用标题和代码块；TXT 利用段落、标点与可选业务边界；PDF 先区分文字层、扫描 OCR 和多栏版面，避免页眉页脚混入正文；Word 保留标题层级、列表和表格；HTML 清理导航、脚本等噪声并沿 DOM 标题与正文组织。表格要保存表头与行列关系，代码要避免截断语法单元。统一按字符截取会把跨页句子、表格列和标题关系破坏，导致“检索到词却缺少条件”的证据。

#### 2. 面试口述版

不同格式的问题主要出在解析，不只是切片长度。Markdown 已有标题，可以先分节；PDF 可能是扫描件或多栏，需要先得到正确阅读顺序；Word 要保留标题、列表和表格；HTML 要先去导航、脚本和重复页脚。之后我才对过长正文开窗口，并保留页码和章节。项目实际支持 Markdown 回退和 Unstructured 元素解析，标题用于章节，表格单独保留，非 Markdown 在解析器不可用时会跳过。我也会主动说明默认后缀没有 TXT，不能因为纯文本容易处理，就把它说成已经支持。当前格式覆盖和真实版面精度是两件事。

#### 3. Adaptive-RAG实际实现

**部分实现**格式感知。`SUPPORTED_SUFFIXES` 包含 `.md/.pdf/.docx/.pptx/.html/.htm` 和图片，**不含 `.txt`**；Markdown fallback 按一至三级标题切段，再窗口切片。[app/retrieval/unstructured_parser.py:L25](../../app/retrieval/unstructured_parser.py#L25)、[app/retrieval/chunking.py:L69](../../app/retrieval/chunking.py#L69)。`elements_to_chunks()` 忽略 Header/Footer/PageBreak，Title 更新 section，Table 单独成块，保留可选页码与 HTML；PDF/图片 partition 传入 strategy 和 OCR languages。[app/retrieval/unstructured_parser.py:L129](../../app/retrieval/unstructured_parser.py#L129)、[app/retrieval/unstructured_parser.py:L288](../../app/retrieval/unstructured_parser.py#L288)。

缺少 Unstructured 时仅 Markdown 有回退；其他格式返回空列表。**项目未实现**独立 TXT 导入适配器、完整标题树和专门代码语法切分，不能宣称所有格式都能无损解析。[app/retrieval/unstructured_parser.py:L275](../../app/retrieval/unstructured_parser.py#L275)。

#### 4. 面试官可能追问

- **追问：表格很长为什么不直接窗口切？** 答：窗口可能拆掉表头与关联列；应按行组切分并重复表头。项目目前保留整张表，仍有超长表上下文风险。
- **追问：页码能定位到每一句吗？** 答：不能。当前缓冲正文用其中第一个可用页码，属于块级近似来源，不能当精确句子 offset。
- **追问：缺 OCR 依赖时是否把二进制当文本读？** 答：不会；非 Markdown 缺解析器会跳过，应让导入结果显示缺失并补依赖后重建。

#### 5. 测试与证据

`test_title_becomes_section_and_table_stays_whole`、`test_table_is_not_windowed` 分别覆盖标题/表格和长表策略。[tests/unit/test_unstructured_parser.py:L41](../../tests/unit/test_unstructured_parser.py#L41)、[tests/unit/test_unstructured_parser.py:L71](../../tests/unit/test_unstructured_parser.py#L71)。`test_parse_path_skips_non_markdown_without_unstructured` 验证缺解析器行为；`test_html_fixture_with_injected_partition` 是注入 fixture，**不是实际 HTML/PDF OCR 全链验收**。[tests/unit/test_unstructured_parser.py:L150](../../tests/unit/test_unstructured_parser.py#L150)、[tests/unit/test_unstructured_parser.py:L197](../../tests/unit/test_unstructured_parser.py#L197)。真实复杂 PDF/Word 版面效果：**未验证**。

<a id="q040"></a>
### Q040：固定长度、递归、按语义/标题、父子块切片分别怎么做？
★核心60

#### 1. 标准答案

固定长度按字符或 token 窗口滑动，简单可控但会切断语义；递归切片按标题、段落、句子、字符等分隔层级逐步细分超长部分；标题切片利用文档结构，将标题路径带入内容或元数据；语义切片依据句向量变化或主题边界分组，增加模型成本和阈值敏感性。父子块用小块召回定位，再根据 parent_id 获取更大父块供生成，兼顾精准匹配与完整语境。四种策略可以组合，但必须明确检索单位、生成单位和 token 预算，不能把“有标题”直接称为语义切片。

#### 2. 面试口述版

我会从边界和使用场景解释。固定窗口适合先做稳定基线，递归是超长时逐级尝试段落、句子等边界，标题切片利用作者给出的结构，语义切片则要额外判断主题是否改变。父子块不是单纯把块变大，而是小块负责命中，父块负责补全条件。项目里公共 Markdown 是标题分节后再按字符窗口，Unstructured 则按标题和元素类型组织；私有正文是固定字符切片。项目没有真正实现递归 splitter、句向量语义边界或父子块回填。我会把这些列为可比较的方案，用相同问题集检查召回和回答条件是否完整，再决定是否引入。

#### 3. Adaptive-RAG实际实现

**已实现**标题加固定窗口：`chunk_markdown()` 使用 `_split_sections()` 和 `_window()`，后者通过 `start = max(end - overlap, start + 1)` 推进。[app/retrieval/chunking.py:L33](../../app/retrieval/chunking.py#L33)、[app/retrieval/chunking.py:L88](../../app/retrieval/chunking.py#L88)。非 Markdown 正文元素也复用窗口，表格独立块。[app/retrieval/unstructured_parser.py:L142](../../app/retrieval/unstructured_parser.py#L142)。私有 `document_chunks()` 每 1000 **字符**切块，以 subject/document/revision/index 哈希作 ID。[app/retrieval/private.py:L23](../../app/retrieval/private.py#L23)。**项目未实现**递归分隔器、基于模型的语义边界检测以及 parent-child 索引/回填。

#### 4. 面试官可能追问

- **追问：标题切片为什么还需要窗口？** 答：章节大小不固定，超长章节会超过 embedding 或生成上下文限制，窗口提供上限控制。
- **追问：父子块有什么新风险？** 答：父块可能包含无关或超权限内容；回填必须再次按版本与权限过滤，并计算额外上下文成本。
- **追问：递归切片一定更好吗？** 答：不一定。格式噪声会使分隔符失真；应比较条件跨块丢失、检索粒度与成本，而非按算法名字排名。

#### 5. 测试与证据

`test_chunk_ids_are_stable` 覆盖 Markdown 相同输入生成稳定 ID；`test_unstructured_chunk_ids_are_stable` 覆盖元素切片稳定性。[tests/unit/test_bm25.py:L6](../../tests/unit/test_bm25.py#L6)、[tests/unit/test_unstructured_parser.py:L102](../../tests/unit/test_unstructured_parser.py#L102)。这些测试不证明语义边界最优。递归/语义/父子块策略对照：**项目未实现，未验证**。

<a id="q041"></a>
### Q041：Chunk Size 与 Overlap 怎么选，有什么指标验证？
★核心60

#### 1. 标准答案

先声明单位，再选候选范围。字符长度不等于 token 数；上限应考虑 embedding 最大长度、语言、表格和生成预算。小块更精准但容易丢失限定条件，大块保留上下文却稀释匹配并增加成本。Overlap 只缓解边界断裂，过大会产生重复召回和索引膨胀。固定语料、解析器、模型和问题集，比较证据 Recall@K、MRR/nDCG、回答忠实度与完整性、无答案拒答、P95 延迟和索引体积。按事实型、跨段、长表等切片分析，防止平均分掩盖退化。

#### 2. 面试口述版

我不会直接回答一个通用最优数，而会先说单位和文档结构。短政策希望一次保留适用范围、例外和办理条件，太小会只召回一句结论；太大又会把无关内容塞进模型。Overlap 是处理边界的手段，也会增加重复和成本。项目公共切片现在是五百字符、六十字符重叠，私有正文则是一千字符且没有重叠，它们不是 token 参数。我会在固定语料与金标准上比较多个组合，既看证据召回，也看最终答案是否漏掉例外和是否超出预算。现有代码能证明参数是什么，不能证明这些默认值已经经过系统调参而最优。

#### 3. Adaptive-RAG实际实现

**已实现**公共固定常量 `MAX_CHUNK_CHARS=500`、`OVERLAP_CHARS=60`，不是 Settings 中的 token splitter 参数；Markdown 与元素正文复用它们。[app/retrieval/chunking.py:L14](../../app/retrieval/chunking.py#L14)、[app/retrieval/unstructured_parser.py:L151](../../app/retrieval/unstructured_parser.py#L151)。私有库使用独立的 1000 字符窗口且无 overlap。[app/retrieval/private.py:L25](../../app/retrieval/private.py#L25)。请求级 `enforce_request_budget()` 对序列化 UTF-8 字节加余量及最大输出做保守界限检查，也不能当实际 tokenizer 计费值。[app/memory/budget.py:L14](../../app/memory/budget.py#L14)。**项目未实现**系统化 Chunk Size/Overlap 参数扫描及最优值结论。

#### 4. 面试官可能追问

- **追问：增加 overlap 后 Recall 上升就算成功吗？** 答：还要去重并检查新增命中是否只是同一证据的重复块，同时衡量索引、重排和上下文成本。
- **追问：为什么不能把 500 字符写成 500 token？** 答：不同语言、符号和模型编码有不同 token 比例，源码这里直接用 Python 字符串长度截取。
- **追问：跨块条件丢失怎么测？** 答：构造结论和例外恰跨边界的问题，金标准标注两段必要证据，再检查检索是否齐全和答案是否表达例外。

#### 5. 测试与证据

窗口实现可直接核对 `_window`，稳定性见 `test_chunk_ids_are_stable`。[app/retrieval/chunking.py:L88](../../app/retrieval/chunking.py#L88)、[tests/unit/test_bm25.py:L6](../../tests/unit/test_bm25.py#L6)。`test_complete_serialized_input_and_output_reservation_checked_before_http` 验证请求超预算先阻断 HTTP，**不是切片质量调参实验**。[tests/unit/test_context_budget.py:L10](../../tests/unit/test_context_budget.py#L10)。当前参数的最优性、真实模型召回收益：**未验证**。

<a id="q044"></a>
### Q044：如何保留标题路径、章节、来源页码、Offset、版本和权限元数据？
★核心60

#### 1. 标准答案

文档层保存 document_id、来源、内容哈希、解析版本和业务 revision；块层保存 chunk_id、父文档、标题路径、章节、页码、起止 offset、内容和索引版本。Offset 必须声明坐标系：原始文件字节、抽取文本字符或清洗后文本，不能混用。权限来自可信身份和权威 ACL，向量 payload 过滤只是防线之一；检索后还要核验当前文档权限和 revision。清洗后若无法恢复原位置，应明确定位精度，不能伪造页码或 offset。引用需能重建“哪一版、哪一段、谁可见”。

#### 2. 面试口述版

元数据不是为了展示漂亮引用，而是为了定位、版本一致性和权限验证。我会把来源与业务版本放文档层，把章节、页码、位置和 chunk ID 放块层；位置还要明确是在原文还是清洗后的文本中。项目已经有文档 ID、section、policy_version 和 metadata，解析器可保留页码和表格 HTML；私有块带 subject 和 revision，ID 也包含版本。它还没有完整标题路径和精确 offset，所以我不会说能逐句回跳 PDF。权限方面不能相信用户上传的 tenant 字段，必须从认证身份取，并在 SQL 可见文档范围和向量过滤两边保持一致。

#### 3. Adaptive-RAG实际实现

**部分实现**：`RetrievedChunk` 有 `document_id/title/section/chunk_index/policy_version/metadata`。[app/schemas/retrieval.py:L8](../../app/schemas/retrieval.py#L8)。公共 Markdown 存 `source/parser`，章节为当前标题，非完整层级路径；Unstructured `_build_chunk()` 额外存 `element_type/page_number/table_html`，HTML 最多 4000 字符。[app/retrieval/chunking.py:L51](../../app/retrieval/chunking.py#L51)、[app/retrieval/unstructured_parser.py:L321](../../app/retrieval/unstructured_parser.py#L321)。

私有 `document_chunks()` 用 `tenant_subject/revision`，`scoped_search()` 同时过滤 subject 与当前合法 chunk IDs。[app/retrieval/private.py:L23](../../app/retrieval/private.py#L23)、[app/retrieval/private.py:L67](../../app/retrieval/private.py#L67)。**项目未实现**标准化 heading_path 和精确起止 offset 字段；公共 `policy_version` 默认 v1 不等于自动版本管理。

#### 4. 面试官可能追问

- **追问：页码一定精确吗？** 答：单表元素页码可直接保留，正文缓冲块取第一个可用页码；这是块级来源，不能承诺逐句精确。
- **追问：稳定 ID 是否永久绑定相同内容？** 答：公共 ID 基于文档和块序号，前面插入内容可能改变块含义；私有 ID 包含 revision，更适合按版本追踪。
- **追问：向量命中旧版本怎么办？** 答：以 SQL 当前版本构建合法块集合，旧 ID 不在集合内就不能作为返回证据，另行异步清理残留索引。

#### 5. 测试与证据

`test_title_becomes_section_and_table_stays_whole` 检查 section、page_number 和表格 HTML；`test_unstructured_chunk_ids_are_stable` 检查同一输入稳定性。[tests/unit/test_unstructured_parser.py:L41](../../tests/unit/test_unstructured_parser.py#L41)、[tests/unit/test_unstructured_parser.py:L102](../../tests/unit/test_unstructured_parser.py#L102)。权限实现的源头可核对 `private_access()` 的 Principal 依赖。[app/api/routes/knowledge.py:L31](../../app/api/routes/knowledge.py#L31)。精确 offset、完整标题路径回跳：**未实现/未验证**。

<a id="q060"></a>
### Q060：用户 Query 也需要 Embedding 吗？离线建索引和在线查询如何对应？
★核心60

#### 1. 标准答案

Dense 检索通常需要将 Query 编码成与文档相容的向量，才能在同一空间比较距离；BM25 路径只需分词，不依赖 embedding。离线用文档编码器批量建索引，在线用对应查询编码器，双塔模型两侧可以不同但必须配套训练。模型版本、维度、归一化、距离度量和查询指令都属于索引契约。换模型或维度通常要重建索引，不能只更换在线 Query 编码器；应建立新 collection，完成离线比较后切换，并保留回滚信息。

#### 2. 面试口述版

如果走向量召回，Query 也要编码，但 BM25 不需要。关键不是两边都得到一串浮点数，而是它们属于同一个相容语义空间。文档离线批量编码，查询在线编码，模型版本、维度和归一化都要对应；换模型通常应重建索引。项目中 Ingestor 对块正文调用 embed，VectorRetriever 对单条 Query 调用同一接口。Provider 可以是配置的远端、可用的本地 BGE，也可能降级到 hash。我会特别说明 hash 能保证离线链路可运行和确定性，不能拿它的测试通过证明真实语义召回质量，实际验收还要记录当时的 embedding backend。

#### 3. Adaptive-RAG实际实现

**已实现**文档侧 `embed([chunk.content ...])` 与查询侧 `embed([query])`，随后调用存储搜索。[app/retrieval/ingest.py:L98](../../app/retrieval/ingest.py#L98)、[app/retrieval/vector.py:L165](../../app/retrieval/vector.py#L165)。`build_embedding_provider()` 优先配置好的远端 API，再本地模型，最后 `HashEmbeddingProvider`；本地 `encode()` 开启 `normalize_embeddings=True`。[app/providers/embeddings.py:L213](../../app/providers/embeddings.py#L213)、[app/providers/embeddings.py:L152](../../app/providers/embeddings.py#L152)。类名 `BgeM3EmbeddingProvider` 不证明实际模型是 bge-m3，应看 `settings.local_embedding_model`。Docker 演示运行配置显式禁用本地 embedding，不能将演示链路称为已启用 BGE；是否走远端还取决于该模式是否配置远端，否则由工厂降级 hash。[app/demo/docker.py:L134](../../app/demo/docker.py#L134)。**部分实现**索引契约；未见完整模型版本迁移发布控制器，不能声称自动完成模型换代重建。

#### 4. 面试官可能追问

- **追问：维度相同就能混用两个模型吗？** 答：不能，坐标空间语义不同；即使维度一样，距离也没有可比意义。
- **追问：Query embedding 失败可以直接回退 BM25 吗？** 答：公共 Hybrid 能隔离一路失败；私有 Dense 依赖失败采用 fail-closed，不能为了可用性绕开其安全契约。
- **追问：怎样证明测试没有下载模型？** 答：检查测试注入模型或 testing 下 hash 路径，测试名称和 backend 要明确标注。

#### 5. 测试与证据

`test_vector_retriever_searches_with_embedded_query` 验证查询编码后搜索；`test_build_records_rejects_length_mismatch` 验证块与向量数量一致。[tests/unit/test_vector_store.py:L135](../../tests/unit/test_vector_store.py#L135)、[tests/unit/test_vector_store.py:L126](../../tests/unit/test_vector_store.py#L126)。`test_factory_falls_back_to_hash_in_testing` 与 `test_injected_bge_m3_encodes` 分别验证降级和注入模型接口。[tests/unit/test_embeddings.py:L61](../../tests/unit/test_embeddings.py#L61)、[tests/unit/test_embeddings.py:L36](../../tests/unit/test_embeddings.py#L36)。本轮未执行模型加载或付费 embedding。

<a id="q061"></a>
### Q061：BM25 的基本原理是什么？它比向量检索在哪些问题上更强？
★核心60

#### 1. 标准答案

BM25 对查询词逐项累加词频、逆文档频率和长度归一化后的贡献：`Σ IDF(t) · f(t,d)(k1+1)/(f(t,d)+k1(1-b+b·|d|/avgdl))`。词频增益会饱和，长度归一化防止长文仅因词多而占优。IDF 有不同实现：常见正值形式为 `ln(1+(N-df+0.5)/(df+0.5))`；不能认定所有库都用这一版。BM25 对 SKU、错误码、政策编号、罕见专名和精确关键词通常有优势；同义改写、隐含语义及无共同词问题则需要 Dense 等补充。中文分词和标识符保留直接影响效果。

#### 2. 面试口述版

BM25 可以理解为带稀有词权重和长度修正的关键词匹配。一个词在当前文档出现会加分，但出现十次不会比一次线性高十倍；到处都有的词区分度低，过长文档也会做修正。它适合订单相关专名、SKU、规则编号和错误码，因为这些场景精确词面很重要；向量模型有时会把编号相近但业务不同的内容拉近。项目用 jieba 相关分词和 rank_bm25 的 BM25Okapi，我不会把教科书的某个 IDF 公式说成库的精确实现。BM25 的短板是同义表达和无共同词，所以项目把它与 Dense 融合，并保留纯词法基线来观察各自贡献。

#### 3. Adaptive-RAG实际实现

**已实现** `BM25Retriever.build()` 对块正文 `tokenize` 后构建 `rank_bm25.BM25Okapi`，`search()` 对 Query 分词并用 `get_scores` 排序，复制块、标记 rank 和 source。[app/retrieval/bm25.py:L23](../../app/retrieval/bm25.py#L23)、[app/retrieval/bm25.py:L30](../../app/retrieval/bm25.py#L30)。项目没有自己重写 IDF；该依赖的 Okapi 常见实现使用 `ln(N-df+0.5)-ln(df+0.5)` 并处理负 IDF，不能与上面的正值变体混称。代码明确保留小语料可能出现的负分，不以 `score>0` 硬过滤。[app/retrieval/bm25.py:L37](../../app/retrieval/bm25.py#L37)。**未验证**“所有精确匹配场景均优于 Dense”的广泛结论。

#### 4. 面试官可能追问

- **追问：为什么词频要饱和？** 答：重复堆积同一个词不代表相关性等比例上升，饱和可以降低重复文本的优势。
- **追问：中文检索最先排查什么？** 答：看分词是否保留商品名、数字与编号，再看语料和 Query 的规范化是否一致。
- **追问：为什么不删掉负分结果？** 答：小语料下负分仍可表达相对排序，机械删掉可能损失候选；是否无答案应结合证据与后续判断。

#### 5. 测试与证据

`test_bm25_ranks_lexical_match` 检查词面命中的相对排序。[tests/unit/test_bm25.py:L26](../../tests/unit/test_bm25.py#L26)。混合链路测试使用 hash dense，因此只能作为词法加降级向量链路验证。[tests/integration/test_hybrid_retrieval.py:L11](../../tests/integration/test_hybrid_retrieval.py#L11)。真实 Dense 对照下 SKU/错误码分类收益：**未验证**，没有捏造指标。

<a id="q063"></a>
### Q063：为什么采用 BM25 + Dense 混合检索，而不是只用向量搜索？
★核心60

#### 1. 标准答案

两路的错误分布不同：BM25 擅长精确词面、编号与稀有词，Dense 擅长同义改写和语义近似。混合检索扩大候选覆盖，再通过融合和重排控制最终上下文。代价是双索引维护、延迟、版本一致性与监控复杂度。BM25 与向量分数尺度不同，不能随意相加；可使用 RRF，或经验证的归一化/学习融合。是否值得混合要按问题类别对照 BM25-only、Dense-only、Hybrid 和 Hybrid+Rerank，并保留权限过滤一致性。

#### 2. 面试口述版

电商客服既有口语化政策咨询，也有精确编号和专名，单靠一种匹配方式容易漏掉另一类。BM25 负责词面稳定性，Dense 负责语义改写，两路召回后用 RRF 融合，再有限量重排。这个选择不是免费提升，它增加索引维护和查询成本，所以需要纯 BM25、纯 Dense 和混合的同集对照。项目实际实现了这条链，但离线集成测试常用 hash embedding，只能验证编排，不能据此宣布 Dense 带来多少语义收益。另外公共链路允许一路失败继续，私有知识则更保守，不能把公共降级策略直接搬过去绕开身份和版本校验。

#### 3. Adaptive-RAG实际实现

**已实现** `HybridRetriever.retrieve()` 分别执行 BM25 和 Dense，以 `reciprocal_rank_fusion` 合并，最终裁剪 `top_k`，支持缓存。[app/retrieval/hybrid.py:L39](../../app/retrieval/hybrid.py#L39)。两路当前为代码顺序调用，不能声称已有并行双路搜索；公共路径独立捕获一路异常，两路均无结果时抛 `RetrievalError`。[app/retrieval/hybrid.py:L49](../../app/retrieval/hybrid.py#L49)。私有 `retrieve` 在当前 SQL 授权块上建立 BM25、用 scope 向量搜索并融合；私有向量依赖异常明确抛错。[app/retrieval/private.py:L249](../../app/retrieval/private.py#L249)。**未验证**所有场景下混合必然更快或更准。

#### 4. 面试官可能追问

- **追问：只要混合就一定高召回吗？** 答：不一定，融合后的截断会挤掉单路正确结果，需要检查各阶段候选和证据 Recall。
- **追问：为什么不直接加原始分数？** 答：BM25 分数和向量相似度尺度不一致，未经校准的权重没有稳定含义。
- **追问：如何证明 Dense 真有贡献？** 答：固定真实 embedding backend，在无词面重合的同义问题上做消融，并比较候选与最终答案，不使用 hash 结果冒充。

#### 5. 测试与证据

`test_hybrid_retrieves_return_policy` 覆盖导入到融合召回，但 dense 为 hash。[tests/integration/test_hybrid_retrieval.py:L11](../../tests/integration/test_hybrid_retrieval.py#L11)。`test_rrf_prefers_docs_high_in_both_lists` 验证融合偏向双路靠前项及去重。[tests/unit/test_rrf.py:L18](../../tests/unit/test_rrf.py#L18)。本轮未重跑性能或真实 embedding 消融；相关收益**未验证**。

<a id="q064"></a>
### Q064：RRF 的公式、参数 k 和两路融合流程是什么？
★核心60

#### 1. 标准答案

`RRF(d)=Σᵢ 1/(k+rankᵢ(d))`，排名从 1 开始，某路未出现的文档贡献为 0。流程是各路先独立排序→按同一 chunk ID 合并→累加各路倒数排名贡献→按融合分排序→裁剪候选。`k` 是平滑常数，不是召回 Top-K：越小越强调榜首，越大越平滑各名次差异，更突出多路共同出现。RRF 避开分数标定，但不理解文本含义，也不能修复两路都没召回的证据；还要处理重复 ID、版本和权限。

#### 2. 面试口述版

RRF 只看排名，不直接比较 BM25 和余弦分数。每条结果在一路贡献一除以 k 加排名，两路都有就相加，没出现就是零。这里 k 是平滑参数，跟召回多少条的 Top-K 不是一个概念。项目默认六十，按列表中的实际位置计 rank，用 chunk ID 合并重复项，最后重新编号。它的好处是简单、可解释、无需给不同分数做校准；代价是丢失原始分数差距，也无法判断语义上真正支持哪个结论。我的验证会手算一个小例子，再查去重和截断后的金标准命中，不能只说融合后总条数变多就是效果提升。

#### 3. Adaptive-RAG实际实现

**已实现** `reciprocal_rank_fusion()` 检查 `k>0`，按 `enumerate(..., start=1)` 的位置计算贡献，不采用块原有的 `rank` 属性；同 ID 保留第一份元数据，累计融合分，再设置 `source='rrf'` 和新 rank。[app/retrieval/fusion.py:L16](../../app/retrieval/fusion.py#L16)。`Settings.rrf_k=60`，Hybrid 将两路列表传入后裁剪。[app/config/settings.py:L67](../../app/config/settings.py#L67)、[app/retrieval/hybrid.py:L63](../../app/retrieval/hybrid.py#L63)。例如 A 在两路均第 1，得 `2/61`；B 仅一路第 1，得 `1/61`。**项目未实现**按 Query 学习动态 RRF 权重。

#### 4. 面试官可能追问

- **追问：同一路重复同一个 ID 怎么办？** 答：合理输入应先去重；当前函数会按每次出现累加，跨路去重不等于自动防止同一路重复加分。
- **追问：k 越大越关注第一名吗？** 答：相反，k 大时不同名次的相对差异更小；要更强调榜首一般减小 k。
- **追问：相同 ID 的正文版本不同怎么办？** 答：不应靠“第一份胜出”解决，索引层需让 ID/版本一致，私有库还要先用 SQL 当前版本核验。

#### 5. 测试与证据

`test_rrf_prefers_docs_high_in_both_lists` 覆盖跨路合并，`test_rrf_uses_rank_not_raw_score` 构造分数差异并验证不按原始分数融合。[tests/unit/test_rrf.py:L18](../../tests/unit/test_rrf.py#L18)、[tests/unit/test_rrf.py:L28](../../tests/unit/test_rrf.py#L28)。后一用例的两个单元素列表位置都为 1，不能误读成采用对象 rank=5 的断言。k 调优效果：**未验证**。

<a id="q066"></a>
### Q066：为什么粗召回后还要 Cross-Encoder Rerank？优缺点是什么？
★核心60

#### 1. 标准答案

Bi-Encoder 可预编码文档，适合大规模近邻召回，但 Query 和文档独立编码会损失细粒度交互。Cross-Encoder 将 Query 与每个候选联合输入，直接估计相关性，适合有限候选上的精排，能区分相似词面下不同条件。代价是对每个候选计算，无法像文档向量一样预计算全部 Query-Document 配对，增加推理成本和延迟；长文截断、领域偏差仍会出错。它通常提升相关性排序，**不保证延迟更低，也不证明答案被证据蕴含**。

#### 2. 面试口述版

粗召回要先快而广，重排负责看得更细。双塔把问题和文档各压成一个向量，方便索引；Cross-Encoder 把问题和候选放在一起，能更细地比较条件、否定和例外。但候选越多计算越贵，所以我会先融合去重再限量重排，测收益是否覆盖新增延迟。项目有本地 Cross-Encoder Provider，也有词法重排降级；测试环境或禁用配置可能实际走 lexical，因此我不会说每次检索都调用了模型。重排分高只说明相关性判断，不等于结论一定被支持，生成后还要检查引用和 Faithfulness，失败时保守回答。

#### 3. Adaptive-RAG实际实现

**已实现** `CrossEncoderRerankProvider` 将 `(query, document)` 配对，在线程中 `model.predict()` 后排序；模型是否加载受 `cross_encoder_enabled`、testing/force、依赖及模型可用性控制，失败回退 `LexicalRerankProvider`，后者是字符集合重合度，**不是 Cross-Encoder**。[app/providers/reranker.py:L67](../../app/providers/reranker.py#L67)、[app/providers/reranker.py:L107](../../app/providers/reranker.py#L107)、[app/providers/reranker.py:L16](../../app/providers/reranker.py#L16)。`DocumentReranker.rerank()` 将候选内容传 Provider，再复制回元数据。[app/retrieval/reranker.py:L15](../../app/retrieval/reranker.py#L15)。**部分实现**模型重排能力：Docker 演示 `runtime_settings` 显式设置 `cross_encoder_enabled=False/cross_encoder_force=False`，实际采用词法降级，不能由类存在推断运行启用。[app/demo/docker.py:L136](../../app/demo/docker.py#L136)。

#### 4. 面试官可能追问

- **追问：Reranker 会找回未召回文档吗？** 答：不会，只能排序已给出的候选，因此先检查候选 Recall 再调重排。
- **追问：Cross-Encoder 会让系统更快吗？** 答：它增加一段推理；可能减少后续上下文或重试，但端到端净收益必须实测，不能一概说低延迟。
- **追问：如何知道实际用了哪种 Provider？** 答：记录 backend、启用配置和加载状态，testing 的注入模型测试与生产真实权重运行分开报告。

#### 5. 测试与证据

`test_cross_encoder_uses_injected_model` 验证联合配对与排序；`test_disabled_cross_encoder_falls_back` 验证禁用时回退。[tests/unit/test_reranker.py:L55](../../tests/unit/test_reranker.py#L55)、[tests/unit/test_reranker.py:L94](../../tests/unit/test_reranker.py#L94)。`test_document_reranker_rewrites_rank_and_source` 检查结果元数据。[tests/unit/test_reranker.py:L78](../../tests/unit/test_reranker.py#L78)。这些不是实际权重吞吐测试；真实收益与 P95 延迟本轮**未验证**。

<a id="q067"></a>
### Q067：Top-K（各路召回K、合并K、重排N）怎么选择？
★核心60

#### 1. 标准答案

先区分每路候选 K、融合保留 K、送入重排的候选数和最终上下文 N。通常上游候选数至少覆盖下游，扩大召回后再减少上下文，但不存在通用固定比例。应根据证据 Recall 饱和曲线确定粗召回范围，再在重排增益、P95 延迟、显存及 token 成本约束下选择最终 N。多证据问题需覆盖必要子目标；Top-K 过大可能增加相互冲突、过期或重复证据。权限、版本过滤要尽量前置，并报告过滤后的有效候选数。

#### 2. 面试口述版

我会把 K 和 N 在流水线里画清楚，不只报一个数字。两路各取多少、融合留下多少、重排看到多少以及最终给模型多少，是不同的控制点。先在固定问题集上看候选 Recall 随 K 的曲线，再看重排和生成质量的收益能否覆盖延迟和 token 成本。项目简单检索配置三条、复杂八条、重排目标五条，但 Hybrid 本身会把融合结果裁到传入的 K，普通路径最多合并两次查询。因此不能说它默认两路各三条后一定有六条可重排，也不能说最终一定五条。实际条数取决于去重、改写和候选数量。

#### 3. Adaptive-RAG实际实现

**已实现** `retrieval_top_k_simple=3`、`retrieval_top_k_complex=8`、`rerank_top_n=5`。[app/config/settings.py:L65](../../app/config/settings.py#L65)。`retrieval_node()` 按 MULTI 选择复杂 K；普通路径原 Query 加改写建议去重后最多 2 条，每条都调用 Hybrid，按 chunk_id 汇总后重排到 `rerank_top_n`。[app/agents/nodes/retrieval.py:L32](../../app/agents/nodes/retrieval.py#L32)。Hybrid 对两路各取同一 `top_k`，融合后立刻 `[:top_k]`；`DocumentReranker` 使用 `min(top_n,len(chunks))`。[app/retrieval/hybrid.py:L75](../../app/retrieval/hybrid.py#L75)、[app/retrieval/reranker.py:L25](../../app/retrieval/reranker.py#L25)。**项目未实现**每路/融合/重排候选完全独立调参界面及系统扫描结论。

#### 4. 面试官可能追问

- **追问：N=5 而简单 K=3 是否矛盾？** 答：不矛盾，重排最多返回已有数量，且普通路径可能合并两次查询；N 是上限而非保证条数。
- **追问：为什么不直接把 K 调到最大？** 答：会增加重排和生成成本，重复或噪声证据还可能干扰回答，必须看增益曲线。
- **追问：多跳问题只看第一个相关块够吗？** 答：不够，要标注所有必要证据和子目标，检查完整覆盖率而非仅 Hit@K。

#### 5. 测试与证据

`test_in_memory_search_respects_top_k` 验证向量存储截断；`test_document_reranker_rewrites_rank_and_source` 覆盖重排结果与限制。[tests/unit/test_vector_store.py:L95](../../tests/unit/test_vector_store.py#L95)、[tests/unit/test_reranker.py:L78](../../tests/unit/test_reranker.py#L78)。代码可以验证默认值与裁剪顺序；K/N 的真实业务最优性、全链 P95 曲线：**未验证**。

<a id="q068"></a>
### Q068：什么是 Recall@K、MRR、nDCG，如何比较不同检索链？
★核心60

#### 1. 标准答案

对每个问题，`Recall@K=|TopK∩Relevant|/|Relevant|`，衡量找齐多少标准证据；MRR 是各问题首个相关结果倒数排名的平均，无命中记 0；`DCG@K=Σᵢ(2^relᵢ−1)/log₂(i+1)`，`nDCG@K=DCG@K/IDCG@K`，支持分级相关性。Hit@K 只看是否至少命中一条，不能代替多证据 Recall。比较链路要固定语料版本、金标准、K、权限与评测单位，去重后逐问题配对比较；再同时报告延迟、费用、回答质量和失败切片，不能将不同数据集的数字直接横比。

#### 2. 面试口述版

Recall 关心证据找齐没，MRR 关心第一条有用结果出现得早不早，nDCG 则允许把强相关和弱相关分级，并奖励更合理的前排顺序。客服问题可能需要政策和例外两段证据，只看有没有命中一条会高估效果。比较 BM25、Dense、Hybrid 和 Rerank 时，我会固定问题、语料版本和 K，统一按文档还是按 chunk 计分，再看分类型差异和延迟成本。项目已经实现 Recall、Hit 和单问题 reciprocal rank；nDCG 还没有对应实现。我也会说明旧评测按文档 stem 聚合与逐 chunk 标注不是同一粒度，不能把数字混用。

#### 3. Adaptive-RAG实际实现

**已实现** `eval.metrics.recall_at_k()`、`hit_at_k()` 与 `mrr()`；这里函数 `mrr` 对单个问题返回首个相关结果倒数排名，跨问题平均要由调用方汇总。[eval/metrics.py:L21](../../eval/metrics.py#L21)、[eval/metrics.py:L31](../../eval/metrics.py#L31)。函数按列表逐项计数，调用方应先去重，避免同 ID 重复导致 Recall 膨胀。现有 RAG JSONL 用 `relevant_doc_ids` 和 `gold_answer_contains`，属于文档级/关键词标签。[eval/dataset/rag_eval.jsonl:L1](../../eval/dataset/rag_eval.jsonl#L1)。**项目未实现** nDCG 指标函数及完整分级 chunk 相关性标签，不把术语解释冒充已有评测能力。

#### 4. 面试官可能追问

- **追问：Relevant 有三条，只找回一条，Hit 与 Recall 各多少？** 答：Hit=1，Recall=1/3；所以 Hit 不能说明证据齐全。
- **追问：MRR 能评估第二、第三条证据顺序吗？** 答：不能，它只看首次命中，多证据或分级相关性需要 Recall、nDCG 等补充。
- **追问：没有相关文档的问题怎么计分？** 答：应单独评估空答案/拒答，预先声明空 Relevant 的处理；项目 recall_at_k 当前返回 0。

#### 5. 测试与证据

`test_recall_at_k_only_scans_top_k`、`test_mrr_second_position` 验证公式边界。[tests/unit/test_metrics.py:L76](../../tests/unit/test_metrics.py#L76)、[tests/unit/test_metrics.py:L100](../../tests/unit/test_metrics.py#L100)。`test_hit_at_k_true_on_any_overlap` 验证 Hit 语义。[tests/unit/test_metrics.py:L85](../../tests/unit/test_metrics.py#L85)。nDCG 单元测试及分级标签评测：**未实现/未验证**。本章不将历史合成集结果写成线上指标。

<a id="q084"></a>
### Q084：RAG回答如何保证引用的chunk真正支持所述结论？
★核心60

#### 1. 标准答案

至少分三层：引用 ID 必须来自本次授权检索集合；引用内容与版本可回溯；每个重要事实都能被所引内容支持。ID 存在性只能防止虚构文档，不能证明语义支持。可将答案拆成事实声明，检查引用是否包含主体、条件、数字与例外，结合规则校验、NLI/LLM judge 和人工抽检；需要同时检查引用准确率与声明覆盖率。无证据、裁判故障、矛盾和格式错误应分开处理，并限制修正次数；不能由“带引用”推断正确。

#### 2. 面试口述版

我把引用正确分为“引用真存在”和“引用真支持”两步。第一步由代码把模型给的 chunk ID 限制在本次检索结果里，第二步检查回答中的金额、条件和例外是否得到证据支持。比如引用了退货政策，却把定制商品也说成七天无理由，就算 ID 真实仍然错。项目有 ID 白名单过滤和生成后的 Faithfulness 裁判，不支持时最多一次改写再检查，证据不足或裁判故障会走保守回答。不过它还不是逐句绑定引用的完整证明系统，而且 Offline 路径跳过裁判。我会用真实 RAG 验收说明有限证据，不能声称从此没有幻觉。

#### 3. Adaptive-RAG实际实现

**已实现** `generate_node()` 仅为本次 chunks 中且出现在 `citation_chunk_ids` 的对象生成 Citation，防止返回任意模型虚构 ID。[app/agents/nodes/generate.py:L150](../../app/agents/nodes/generate.py#L150)。`FaithfulnessChecker.check()` 输入答案、检索证据与工具结果，区分 SUPPORTED、UNSUPPORTED、INSUFFICIENT_EVIDENCE 等；`self_correct_answer()` 最多改写一次并复核。[app/guardrails/hallucination.py:L54](../../app/guardrails/hallucination.py#L54)、[app/agents/nodes/faithfulness.py:L21](../../app/agents/nodes/faithfulness.py#L21)。**部分实现**语义保障：当前没有逐事实到引用的强制映射；Offline/DIRECT 路径跳过检查，不能泛称全部回答都被模型裁判验证。[app/agents/nodes/faithfulness.py:L92](../../app/agents/nodes/faithfulness.py#L92)。

#### 4. 面试官可能追问

- **追问：过滤掉不存在 ID 就够了吗？** 答：不够，还可能引用真实但不支持该结论的块，必须查语义蕴含与事实覆盖。
- **追问：裁判 API 出错能算支持吗？** 答：不能。项目把 JUDGE_ERROR/INVALID_OUTPUT 与支持分开，并退回已验证工具事实的安全回答。
- **追问：如何验证真实 RAG 引用？** 答：核对授权知识库 ID、真实返回 citation、文档摘录和回答条件；脱敏 Trace ID 不能直接拿来做原 ID 相等断言。

#### 5. 测试与证据

`test_judge_outage_no_arbitrary_policy_excerpt_or_false_configuration` 覆盖裁判故障时不能随意摘政策当事实。[tests/unit/test_p2s_answer_reliability.py:L97](../../tests/unit/test_p2s_answer_reliability.py#L97)。2026-11-15 历史真实 RAG 验收 PASS，采用隔离合成政策，原 Trace-ID 比较失败另存复核，未付费重跑；报告明确核对授权库 ID 与引用。[真实业务报告:L21](../../research/docs/agent_engineering_upgrade/deepseek_business_acceptance/REPORT.zh-CN.md#L21)。本轮未重跑；全量声明级引用覆盖率：**未验证**。

<a id="q087"></a>
### Q087：Faithfulness/Groundedness 的含义？怎样评测？
★核心60

#### 1. 标准答案

Faithfulness/Groundedness 关注答案事实是否被给定证据支持；它与世界事实正确性、问题相关性、任务完整性不同。证据本身过期时，答案可能忠实却错误；答案只复述一个已知事实时可能忠实却没完成任务。评测应按声明标注 supported/unsupported/无法判断，计算支持比例、关键错误率及覆盖率，并单独记录裁判故障、格式无效与截断。LLM judge 要固定版本、证据与 rubric，用人工标注集校准，不能让模型看到 Gold 后再声称无泄漏，也不能把 judge 可用率混为答案质量。

#### 2. 面试口述版

Faithfulness 是回答有没有越过手头证据，Groundedness 通常也强调这个依据关系。它不等于业务成功：回答“订单已支付”可能有证据，但用户还问了商品和退货条件，任务仍未完成；过期政策也可能让忠实回答不符合现行事实。项目把支持、无依据和证据不足分开，还把裁判调用失败、非法 JSON、截断列成不同错误。线上节点在必要时做一次修正，离线则要用固定证据和人工审阅检查裁判可靠性。我会分别报告事实支持、子目标完整性和裁判故障，不用一个漂亮的支持率掩盖漏答，也不会把 Offline 的固定裁判当真实模型评测。

#### 3. Adaptive-RAG实际实现

**已实现** `FaithfulnessStatus` 五种状态和 `FaithfulnessResult` 一致性校验；`FaithfulnessChecker.check()` 无证据时直接返回 INSUFFICIENT_EVIDENCE，模型截断、API 异常和 schema 错误分别标记。[app/guardrails/hallucination.py:L16](../../app/guardrails/hallucination.py#L16)、[app/guardrails/hallucination.py:L62](../../app/guardrails/hallucination.py#L62)。Prompt 明确“证据支持事实不代表覆盖所有用户目标”。[app/prompts/faithfulness.py:L3](../../app/prompts/faithfulness.py#L3)。节点对无依据回答修正一次，失败返回安全事实并清空引用。[app/agents/nodes/faithfulness.py:L127](../../app/agents/nodes/faithfulness.py#L127)。**部分实现**在线约束；未建立所有业务声明的人工校准指标及通用 NLI 验证系统。

#### 4. 面试官可能追问

- **追问：SUPPORTED 但没答完问题算成功吗？** 答：不算，应另测子目标覆盖和独立业务目标，不让支持率代替任务完成率。
- **追问：Judge 返回 true 字符串怎么办？** 答：不能按普通布尔转换接受；项目用 StrictBool 和状态一致性校验，矛盾输出归无效。
- **追问：怎样避免裁判自评偏好？** 答：冻结 rubric，做盲测与人工双标，按否定、数字和例外分类校准；多裁判一致也不能替代事实证据。

#### 5. 测试与证据

`test_judge_exact_error_category_no_retry` 覆盖错误分类，`test_no_evidence_is_insufficient_without_model_call` 检查无证据不调用裁判，`test_generated_length_is_not_accepted_even_with_complete_json` 检查截断不能当成功。[tests/unit/test_p2s_answer_reliability.py:L55](../../tests/unit/test_p2s_answer_reliability.py#L55)、[tests/unit/test_p2s_answer_reliability.py:L151](../../tests/unit/test_p2s_answer_reliability.py#L151)、[tests/unit/test_p2s_answer_reliability.py:L159](../../tests/unit/test_p2s_answer_reliability.py#L159)。测试定义已核对，本轮未运行；真实全量事实支持率和人工一致率：**未验证**。
