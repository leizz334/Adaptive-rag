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

<a id="q042"></a>
### Q042：切块太小与太大会分别造成什么问题？

#### 1. 标准答案

小块容易拆散条件、例外和指代，大块容易稀释相关性、触发截断并增大成本。按必要证据覆盖、答案完整性、索引体积和延迟选择粒度，不能只看平均长度。

#### 2. 面试口述版

我会用政策例子说明两端风险：只保留“可退货”几个字，可能丢掉定制商品例外；把整份手册放进来，又会让模型面对大量无关条款。小块更容易精确命中，大块更容易带全条件，但实际效果取决于解析结构和查询类型。项目公共 Markdown 先按标题再开五百字符窗口，私有正文是一千字符窗口，两者不能混成一个默认值。我会标出每个问题必须看到的结论和限定条件，再比较不同大小的检索与回答，尤其检查跨边界条件，不能因为返回了文本就说参数合理。

#### 3. Adaptive-RAG实际实现

已实现公共500字符/60重叠和私有1000字符无重叠；自动选块长未实现。[app/retrieval/chunking.py:L14](../../app/retrieval/chunking.py#L14) [app/retrieval/private.py:L25](../../app/retrieval/private.py#L25)

#### 4. 面试官可能追问

- **追问：小块Recall高就够吗？** 答：还需看例外是否齐全，重复是否抬高指标。
- **追问：大块一定完整吗？** 答：实际生成输入可能被截断，要核对最终上下文。

#### 5. 测试与证据

test_chunk_ids_are_stable 只验证确定性。[tests/unit/test_bm25.py:L6](../../tests/unit/test_bm25.py#L6) 粒度最优性未验证，本轮未运行。

<a id="q043"></a>
### Q043：表格、代码块、图片、扫描PDF怎么处理？

#### 1. 标准答案

表格保留表头、行列和单位，长表可按行组重复表头；代码按语法单元；图片需OCR或视觉说明；扫描PDF先还原版面。不同元素不能统一字符切分。

#### 2. 面试口述版

我会先把正文、表格、代码和图像分流处理。表格最怕丢掉表头与单位，代码最怕截断函数和缩进，扫描 PDF 则首先要把文字识别正确。项目的 Unstructured 路径能接收表格和图片元素，表格不做普通窗口切分，并保存有限长的 HTML 与页码；图片没有识别文本就跳过。它并没有代码 AST 切片或完整视觉问答能力，我会明确说明。验收时应拿原页面与抽取结果逐项比较，尤其检查数字、负号和表格对应关系，不能只看文件扩展名在支持列表里。

#### 3. Adaptive-RAG实际实现

部分实现Table整块、Image有文本才成块，PDF传入布局和OCR参数；代码AST与视觉推理未实现。[app/retrieval/unstructured_parser.py:L180](../../app/retrieval/unstructured_parser.py#L180) [app/retrieval/unstructured_parser.py:L288](../../app/retrieval/unstructured_parser.py#L288)

#### 4. 面试官可能追问

- **追问：长表整块有何问题？** 答：可能超预算，按行组拆分尚未实现。
- **追问：OCR数字错怎么办？** 答：回原页核验并标记不确定，不能让生成器猜数。

#### 5. 测试与证据

test_table_is_not_windowed 覆盖现行行为。[tests/unit/test_unstructured_parser.py:L71](../../tests/unit/test_unstructured_parser.py#L71) 真实扫描精度未验证。

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

<a id="q045"></a>
### Q045：RecursiveCharacterTextSplitter 的 chunk_size 是字符还是 Token？如何避免单位混淆？

#### 1. 标准答案

单位由length_function和构造方式决定，字符splitter默认通常按字符，token-aware构造才按对应编码计量。配置、日志和文档都要标注单位。

#### 2. 面试口述版

我不会只看 chunk_size 名字就回答是 token。要看 splitter 如何创建，length_function 是 len 还是 tokenizer，以及有没有通过 token-aware 接口构造。项目实际没有用这个类，而是自己的字符窗口，所以五百明确是 Python 字符数；付费门禁另用完整请求 UTF-8 字节加余量做保守界限，也不是实际计费 token。我会在配置和文档中写清单位，用同段中文、英文和 emoji 比较长度，最终成本以可信供应商 usage 为准，避免把切片参数、上下文预算和累计费用限制混在一起。

#### 3. Adaptive-RAG实际实现

项目未使用RecursiveCharacterTextSplitter；_window直接字符串下标切分，完整请求预算独立处理。[app/retrieval/chunking.py:L88](../../app/retrieval/chunking.py#L88) [app/memory/budget.py:L14](../../app/memory/budget.py#L14)

#### 4. 面试官可能追问

- **追问：中文字数等于token吗？** 答：不等，取决于模型词表和内容。
- **追问：字节界限能当账单吗？** 答：不能，它是准入保守值，账单和usage另算。

#### 5. 测试与证据

test_complete_serialized_input_and_output_reservation_checked_before_http 检查完整请求。[tests/unit/test_context_budget.py:L10](../../tests/unit/test_context_budget.py#L10) 第三方splitter实例未实现。

<a id="q046"></a>
### Q046：为什么切片前要清理页眉页脚、目录、重复换行、无效字符？

#### 1. 标准答案

页眉页脚和重复空白污染词频、向量语义及上下文预算；清洗要保留编号、否定词、表格和代码结构，并记录位置映射，避免误删。

#### 2. 面试口述版

我会先处理抽取噪声，再讨论召回算法。每页重复的页眉页脚会让很多块带相同词，目录可能只有标题没有正文，导致表面相关却没有答案。项目会过滤元素级页眉页脚，并做 Unicode 规范化、控制字符清理和中文硬换行合并；表格不按普通正文合并换行。过度清洗也有风险，例如把编号、公式空格或代码缩进改坏，所以应对照清洗前后的原文片段，做专门回归。当前没有完整 offset 映射和通用目录识别，不能把已有空白清理说成无损文档还原。

#### 3. Adaptive-RAG实际实现

已实现normalize_text和元素Header/Footer/PageBreak过滤；目录识别和位置映射未实现。[app/retrieval/cleaning.py:L25](../../app/retrieval/cleaning.py#L25) [app/retrieval/unstructured_parser.py:L45](../../app/retrieval/unstructured_parser.py#L45)

#### 4. 面试官可能追问

- **追问：表格为何不合并换行？** 答：换行可能表示行关系。
- **追问：NFKC有风险吗？** 答：兼容字符表现会变，要保留原件核对领域编号。

#### 5. 测试与证据

test_title_becomes_section_and_table_stays_whole 检查结构。[tests/unit/test_unstructured_parser.py:L41](../../tests/unit/test_unstructured_parser.py#L41) 目录去除质量未验证。

<a id="q047"></a>
### Q047：遇到跨页表格、嵌套列表、脚注和公式怎么办？

#### 1. 标准答案

跨页表按列结构与续表关系合并；嵌套列表保留层级，脚注绑定引用，公式保留表达与单位。无法可靠解析应标不确定并回原页核验。

#### 2. 面试口述版

这类问题超出了普通字符切片能解决的范围。跨页表格下一页没有表头，直接拼正文会丢掉列含义；嵌套列表表达条件层级，脚注可能改变整条规则，公式还有上下标和单位。项目目前保留单个表格元素与页码，正文按章节缓冲，但没有跨页合并、脚注绑定或公式语义解析。我会把这些作为明确限制，遇到关键政策或金额先回原页面核验，必要时拒绝给精确结论。后续方案要用专门标注页测试结构关系，不能靠提高向量召回分数证明抽取正确，更不能编造缺失表头。

#### 3. Adaptive-RAG实际实现

部分实现单元素表格和页码；正文用首个可用页码。跨页关系、脚注回链和公式解析未实现。[app/retrieval/unstructured_parser.py:L142](../../app/retrieval/unstructured_parser.py#L142) [app/retrieval/unstructured_parser.py:L180](../../app/retrieval/unstructured_parser.py#L180)

#### 4. 面试官可能追问

- **追问：同列数就能拼表吗？** 答：还要核对文档、连续页、列名与续表标记。
- **追问：公式看不清怎么办？** 答：保留原页并说明无法可靠解析。

#### 5. 测试与证据

test_title_becomes_section_and_table_stays_whole 仅验证单元素。[tests/unit/test_unstructured_parser.py:L41](../../tests/unit/test_unstructured_parser.py#L41) 跨页能力未验证。

<a id="q048"></a>
### Q048：PDF是文本层还是扫描件，怎样识别并选择解析工具？

#### 1. 标准答案

逐页检查有效文字、位置和覆盖率，区分文字层、乱码与扫描图；混合PDF需逐页选文字抽取或OCR，多栏再做版面分析。

#### 2. 面试口述版

我会按页判断，而不是给整份 PDF 简单贴标签。先尝试抽取文字和位置，检查是否只有乱码或少量水印，再结合图像覆盖判断是否需要 OCR；一份文档可能前几页有文本层，后面是扫描附件。项目通过 Unstructured 策略和 OCR 语言配置处理 PDF，但没有自己写逐页分类器，也没有证据证明扫描页面都准确。我会展示抽取样本与原页对照，检查中文、金额、负号和多栏阅读顺序，再决定能否入库。解析器不可用时项目跳过非 Markdown，不能静默假装 PDF 已成功处理。

#### 3. Adaptive-RAG实际实现

已实现PDF的strategy/languages传参，未实现独立逐页检测器；缺依赖时非Markdown跳过。[app/retrieval/unstructured_parser.py:L288](../../app/retrieval/unstructured_parser.py#L288) [app/retrieval/unstructured_parser.py:L275](../../app/retrieval/unstructured_parser.py#L275)

#### 4. 面试官可能追问

- **追问：文本非空就不用OCR吗？** 答：不一定，可能只有水印，要检查覆盖率。
- **追问：混合文档怎么选？** 答：逐页记录策略与质量，避免整篇统一误判。

#### 5. 测试与证据

test_parse_path_skips_non_markdown_without_unstructured 检查依赖缺失。[tests/unit/test_unstructured_parser.py:L150](../../tests/unit/test_unstructured_parser.py#L150) 混合PDF精度未验证。

<a id="q049"></a>
### Q049：怎么评估解析质量和段落顺序是否错乱？

#### 1. 标准答案

按原页金标准评估识字错误、数字单位、元素召回、标题层级、表格关系和阅读顺序，再检查下游证据召回；字符数量不等于解析质量。

#### 2. 面试口述版

我会把解析评估和检索评估分开。解析先回答文字是否正确、段落顺序是否正确、表格关系是否保留；下游再看必要证据能否完整检索。例如双栏 PDF 抽成左右交错的句子，关键词可能都在，Recall 看起来不错，模型却无法理解。项目现有测试主要用注入元素 fixture 验证章节、表格和回退，能证明代码规则，不代表真实引擎对各种版面都准确。我会选代表性页面人工标注，检查数字和例外，再追踪错误影响了哪些问题，避免用一个下游平均分掩盖解析根因，也避免把模型凭常识答对当解析通过。

#### 3. Adaptive-RAG实际实现

已实现元素适配和确定性切块，未实现OCR错误率、阅读顺序金标准评估器。[app/retrieval/unstructured_parser.py:L106](../../app/retrieval/unstructured_parser.py#L106) [app/retrieval/unstructured_parser.py:L129](../../app/retrieval/unstructured_parser.py#L129)

#### 4. 面试官可能追问

- **追问：文字都对、顺序错有影响吗？** 答：条件归属会变，需单独评顺序。
- **追问：为什么不能只看答案？** 答：模型可能凭常识答对而掩盖来源错误。

#### 5. 测试与证据

test_parse_path_uses_injected_partition 验证适配层。[tests/unit/test_unstructured_parser.py:L127](../../tests/unit/test_unstructured_parser.py#L127) 真实版面量化未验证。

<a id="q050"></a>
### Q050：标题单独切成块会有什么风险？如何让每块带回父标题？

#### 1. 标准答案

标题独立成块可能只有关键词而没有事实；正文缺父标题会丢适用对象。可让子块继承标题路径，并按用途放元数据或文本前缀，控制重复词频与预算。

#### 2. 面试口述版

我通常不会让只有几个字的标题独自承担回答证据。“退货规则”可能很容易命中查询，却不能回答条件；正文失去父标题，也可能不知道适用于哪类商品。项目 Markdown 把当前标题存成 section，标题行不放正文，Unstructured 的 Title 也用于切换章节。生成证据带文档标题与正文，没有完整标题树自动回填。我会区分已有章节字段和未实现的父路径增强，后续可让子块继承路径，但要测试它是否只是重复关键词抬高 BM25，而没有增加可用事实。引用仍要定位原始内容，不能只引用标题冒充完整依据。

#### 3. Adaptive-RAG实际实现

已实现当前section，完整heading_path与统一正文前缀未实现。[app/retrieval/chunking.py:L69](../../app/retrieval/chunking.py#L69) [app/agents/nodes/generate.py:L61](../../app/agents/nodes/generate.py#L61)

#### 4. 面试官可能追问

- **追问：所有祖先标题都加好吗？** 答：长路径增加重复和token，应按用途限制。
- **追问：标题相关正文不相关怎么办？** 答：重排与支持检查应基于正文事实。

#### 5. 测试与证据

test_title_becomes_section_and_table_stays_whole 验证section。[tests/unit/test_unstructured_parser.py:L41](../../tests/unit/test_unstructured_parser.py#L41) 完整父标题回填未实现。

<a id="q051"></a>
### Q051：什么是 Parent-Child Retrieval（小块检索，大块返回）？

#### 1. 标准答案

小子块用于精确匹配，按parent_id获取较大父块补语境；需维护版本、ACL和范围，合并重复父块并限预算。它不同于普通overlap。

#### 2. 面试口述版

父子检索把检索单位和生成单位分开。小块容易精准匹配，命中后返回所在段落或章节，补上前提和例外。例如子块命中“七天无理由”，父块还应包含定制商品例外。项目目前是普通块召回，没有 parent_id 索引和父块回填，所以我只能把它作为改进方案。真正实现时，回填必须重新检查同一文档版本和权限，不能因为一个子块可见就把整份私有文档交给模型；还要合并重复父块，限制上下文大小，在相同问题集比较证据完整性和新增成本，避免大块噪声抵消精确匹配收益。

#### 3. Adaptive-RAG实际实现

项目未实现parent-child；现有RetrievedChunk无parent_id，Hybrid直接返回块。[app/schemas/retrieval.py:L8](../../app/schemas/retrieval.py#L8) [app/retrieval/hybrid.py:L39](../../app/retrieval/hybrid.py#L39)

#### 4. 面试官可能追问

- **追问：父块一定整篇吗？** 答：可选段落或章节，按必要语境和预算。
- **追问：多个子块同父怎么办？** 答：按父文档版本去重，保留子块命中定位。

#### 5. 测试与证据

test_hybrid_retrieves_return_policy 仅覆盖直接块返回。[tests/integration/test_hybrid_retrieval.py:L11](../../tests/integration/test_hybrid_retrieval.py#L11) 父子检索未实现/未验证。

<a id="q052"></a>
### Q052：什么是相邻块扩展、窗口检索和标题层级检索？

#### 1. 标准答案

相邻扩展在命中后取前后块，句窗先匹配句子再补邻文，标题层级检索先定位章节。都应限同文档版本与权限，去重并设预算，避免错误拼接。

#### 2. 面试口述版

我会区分入库重叠和检索后扩展。Overlap 在建索引时复制边界文本，相邻扩展是在命中后查前后块，句窗可先匹配一句再补语境，标题层级则利用文档树缩小范围。项目有 chunk_index 和 section，可作为基础，但没有完整邻块查找与层级路由。若增加这些能力，我会严格限定同一文档 revision 和授权范围，防止补出旧版或他人的内容，再去重并控制 token。验证时要看是否补齐必要例外，也要观察是否带来噪声，不能只按上下文变长判断成功，更不能把已有六十字符 overlap 说成检索后扩展。

#### 3. Adaptive-RAG实际实现

已有序号、section与固定overlap，检索后邻块扩展、句窗索引与标题树未实现。[app/schemas/retrieval.py:L17](../../app/schemas/retrieval.py#L17) [app/retrieval/chunking.py:L88](../../app/retrieval/chunking.py#L88)

#### 4. 面试官可能追问

- **追问：前后各一块总安全吗？** 答：不一定，要核验权限、文档与版本。
- **追问：窗口如何选择？** 答：看必要证据覆盖和成本，不宣称通用最优值。

#### 5. 测试与证据

test_chunk_ids_are_stable 只验证现有块ID。[tests/unit/test_bm25.py:L6](../../tests/unit/test_bm25.py#L6) 邻块扩展未验证。

<a id="q053"></a>
### Q053：长文档中前后跨段才能回答的问题怎么处理？

#### 1. 标准答案

跨段问题应标注必要证据，通过多查询、子问题分解、有限补检索或邻块回填聚合。证据必须同对象、相容版本；设轮数和预算，关键前提缺失时澄清或说明不足。

#### 2. 面试口述版

长文问题不能只寻找一句最相似的话。用户同时问定制商品能否退、质量问题如何办，需要覆盖一般规则、例外和办理条件。项目有 Query Rewrite、Self-RAG 评分与有限迭代，也会重排候选；但没有父子块回填和通用文档推理树。我会先检查必要证据是否进入候选，再看生成有没有正确连接条件。检索轮数受上限约束，不能无限补查。只有部分证据时，应说明哪部分有依据、哪部分无法确认，而不是把多段近似内容强行拼成确定答案；评分故障回退也不等于证据真的充分。

#### 3. Adaptive-RAG实际实现

已实现SelfRAGLoop有限循环、去重和评分；评分失败会按bool(chunks)回退，因此不是强充分性证明。[app/retrieval/self_rag.py:L45](../../app/retrieval/self_rag.py#L45) [app/retrieval/self_rag.py:L74](../../app/retrieval/self_rag.py#L74)

#### 4. 面试官可能追问

- **追问：跨段都命中就够吗？** 答：还要核对主体、条件和版本是否可组合。
- **追问：如何防无限检索？** 答：设置max_retrieval_hops与请求预算，保留未解问题。

#### 5. 测试与证据

test_hybrid_retrieves_return_policy 只验证有限关键词命中。[tests/integration/test_hybrid_retrieval.py:L11](../../tests/integration/test_hybrid_retrieval.py#L11) 跨段完整率未验证。

<a id="q054"></a>
### Q054：文档里既有描述又有大量唯一编号时，切片策略如何调整？

#### 1. 标准答案

编号应与所属实体及描述绑定，保留前导零、连字符和业务大小写，可用精确字段/BM25补充语义召回；切片避免截断编号或堆积无关编号。

#### 2. 面试口述版

我会先把编号当业务实体，而不是普通自然语言词。商品描述可能含很多 SKU、型号和规则编号，向量模型容易关注描述语义，却混淆只差一位的编号。切片应让编号和说明保持一起，查询保留精确词面再补语义匹配。项目的 BM25 加 Dense 提供两类信号，但现行字符窗口没有编号感知边界，不能说完全不会切断标识符。我会用相近编号、前导零、连字符和多编号同页样本回归，检查分词结果，必要时增加精确字段索引，而不是只调大向量维度。业务对象身份还应由后端校验。

#### 3. Adaptive-RAG实际实现

已实现词法/向量融合，编号原子切片和专门字段索引未实现。[app/retrieval/bm25.py:L23](../../app/retrieval/bm25.py#L23) [app/retrieval/chunking.py:L88](../../app/retrieval/chunking.py#L88)

#### 4. 面试官可能追问

- **追问：相近编号为何危险？** 答：语义近似不能替代业务实体的精确身份。
- **追问：能删所有标点吗？** 答：不能，连字符和小数点可能是编号含义的一部分。

#### 5. 测试与证据

test_bm25_ranks_lexical_match 验证词面排序。[tests/unit/test_bm25.py:L26](../../tests/unit/test_bm25.py#L26) 编号边界专项未验证。

<a id="q055"></a>
### Q055：知识库重复文档或旧版本文档如何去重与更新？

#### 1. 标准答案

精确重复可用规范化哈希，近重复指纹仅作为候选；版本由文档身份、revision和生效规则管理。更新应切换权威可见版本、失效缓存再清理旧索引，不能按相似度误删例外。

#### 2. 面试口述版

内容去重和版本更新必须分开。相同正文的重复导入可用哈希处理，近似文件先标记核查，因为一两句话的差别可能就是政策例外。项目公共导入会删除完全相同的块，SimHash 近重复只记日志不删；私有库有 revision 和租户 generation，检索按 SQL 当前文档构建合法块集合。公共默认 policy_version 为 v1，并不代表自动政策生效管理。我会检查重复来源是否丢失、旧向量是否仍可见和缓存是否跨版本，不能只看导入数量减少。对于当前实现的首块保留行为，也要明确多来源引用关系还不完整。

#### 3. Adaptive-RAG实际实现

已实现精确哈希去重、近重复仅日志、私有revision/generation；自动生效日期治理未实现。[app/retrieval/cleaning.py:L73](../../app/retrieval/cleaning.py#L73) [app/retrieval/private.py:L216](../../app/retrieval/private.py#L216)

#### 4. 面试官可能追问

- **追问：近重复为何不直接删？** 答：数字、否定词和例外可能决定业务差异。
- **追问：不同来源同文怎么办？** 答：应保留来源映射；当前公共保留首块，不是完整多来源治理。

#### 5. 测试与证据

test_exact_duplicate_keeps_first_chunk_id 与 test_near_duplicate_is_logged_not_dropped 覆盖现行规则。[tests/unit/test_cleaning.py:L111](../../tests/unit/test_cleaning.py#L111) [tests/unit/test_cleaning.py:L118](../../tests/unit/test_cleaning.py#L118) 本轮未运行。

<a id="q056"></a>
### Q056：文档删除后如何删除相关 chunk、向量与缓存？

#### 1. 标准答案

先撤销SQL权威可见性，再清理chunk、向量与缓存generation；索引残留不能返回。删除按身份、文档与revision限定，异步对账要幂等，避免误伤并发新版本。

#### 2. 面试口述版

删除更重要的是立即不可见，而不是所有存储同时物理消失。数据库是权限和版本权威，文档撤销后，检索必须从当前合法块集合重建或核验，旧向量和缓存即使残留也不能成为证据。项目私有接口已有删除，按认证 subject 与文档处理，并更新租户 generation；向量清理带 revision，避免误伤新版本。公共目录没有同样完整的在线删除管理。我会测删除后搜不到、他人数据不受影响、旧缓存不回流，以及清理失败时是否关闭返回，不能把旧限制文档里的“无删除”当成当前事实。

#### 3. Adaptive-RAG实际实现

已实现私有DELETE及subject/document/revision向量删除，缓存ID重查canonical。公共在线删除控制器未实现。[app/api/routes/knowledge.py:L67](../../app/api/routes/knowledge.py#L67) [app/retrieval/private.py:L88](../../app/retrieval/private.py#L88) [app/retrieval/private.py:L216](../../app/retrieval/private.py#L216)

#### 4. 面试官可能追问

- **追问：向量残留必泄露吗？** 答：合法集合过滤可阻止返回，但仍要验证失败边界并清理。
- **追问：为何删除带revision？** 答：防止旧清理任务删掉并发新版本。

#### 5. 测试与证据

当前代码可核查删除；通用向量upsert测试不等于删除验收。[tests/unit/test_vector_store.py:L84](../../tests/unit/test_vector_store.py#L84) 本轮真实删除端到端未运行。

<a id="q057"></a>
### Q057：Embedding 模型升级导致维度变化，如何进行重建或双索引迁移？

#### 1. 标准答案

升级需固定模型、维度、归一化、距离与切片契约。新建索引重编码，以双写或变更日志追平，质量/权限/性能验证后切读别名，保留旧索引与水位回滚。

#### 2. 面试口述版

模型升级不能只改在线配置。文档和 Query 必须处于相容向量空间，维度不同会报错，维度相同也未必可比。我会新建索引，记录模型和切片契约，重编码存量，再通过变更日志追上更新，验证召回、权限与延迟后切换。项目能配置 Provider 和 Qdrant 维度，也有私有 reindex，但没有双索引迁移、别名切换与回滚控制器，所以这是方案而非现成能力。迁移期间删除和权限必须同步到两边，不能为了比较效果复制到无过滤新索引；回滚前也要确认旧索引已追平变更。

#### 3. Adaptive-RAG实际实现

已有collection维度、Provider工厂和reindex，完整双索引迁移未实现。[app/retrieval/vector.py:L81](../../app/retrieval/vector.py#L81) [app/providers/embeddings.py:L213](../../app/providers/embeddings.py#L213) [app/retrieval/private.py:L204](../../app/retrieval/private.py#L204)

#### 4. 面试官可能追问

- **追问：同维度能直接换吗？** 答：不能，坐标空间可能不同。
- **追问：回滚只切配置够吗？** 答：还要确认旧索引的增量、权限和删除已追平。

#### 5. 测试与证据

test_build_records_rejects_length_mismatch 仅检查数量契约。[tests/unit/test_vector_store.py:L126](../../tests/unit/test_vector_store.py#L126) 双索引迁移未实现/未验证。

<a id="q058"></a>
### Q058：切片策略变更后如何验证检索质量没有退化？

#### 1. 标准答案

冻结语料、Query、模型和预算，只改变切片策略；将Gold绑定原文证据或重映射新块，比较召回、完整性、拒答、成本与各类退化，保留旧索引回滚。

#### 2. 面试口述版

切片变化后，最容易犯的错是继续用旧 chunk ID 评分，看起来大退化却只是编号变了。我会固定语料和问题，把金标准绑定稳定原文证据或映射到新块，再保持模型与检索预算一致做配对比较。现有文档级标签可避免部分 ID 漂移，但不够细，不能完整检测例外被拆开。还要看必要证据、最终答案和成本，特别检查原来能答的跨段问题。当前没有系统切片迁移评估流水线，因此不能说默认五百字符经过严格最优验证。新旧结果与代码版本都要保留，失败不能覆盖后重跑当首次结果。

#### 3. Adaptive-RAG实际实现

已有文档级RAG标签和Recall/MRR，切片版本比较及Gold自动重映射未实现。[eval/dataset/rag_eval.jsonl:L1](../../eval/dataset/rag_eval.jsonl#L1) [eval/metrics.py:L21](../../eval/metrics.py#L21)

#### 4. 面试官可能追问

- **追问：Recall不降就够吗？** 答：大块可能命中文档但遗漏条件，还要看答案完整性。
- **追问：如何公平限制预算？** 答：固定候选/上下文约束，报告实际块数和输入量差异。

#### 5. 测试与证据

test_recall_at_k_only_scans_top_k 覆盖指标边界。[tests/unit/test_metrics.py:L76](../../tests/unit/test_metrics.py#L76) 切片回归实验未验证。

<a id="q059"></a>
### Q059：如何为每个 chunk 生成稳定ID，避免引用失效？

#### 1. 标准答案

稳定ID应结合文档身份、块内容或位置与版本，避免绝对路径依赖。序号ID重复构建稳定却可能因插入错位；引用要绑定revision，旧ID不能静默指向新内容。

#### 2. 面试口述版

稳定 ID 有两个含义：同一输入重复入库得到一样的 ID，以及内容改变后旧引用不会错指新内容。项目公共文档 ID 用目录相对路径哈希，块 ID 再加序号，所以跨 Windows 和容器位置可重复，但前面插入段落后，序号可能代表另一段。私有块将 subject、文档、revision 和序号一起哈希，版本含义更清楚。我不会因此说历史引用永久有效。长期引用还要保留对应版本和来源，删除时明确不可用，并验证重名文件、编号变化和跨租户对象不会混淆；仅测试重复输入稳定是不够的。

#### 3. Adaptive-RAG实际实现

已实现公共相对路径文档ID/序号块ID及私有版本哈希；永久版本归档未实现。[app/retrieval/chunking.py:L18](../../app/retrieval/chunking.py#L18) [app/retrieval/chunking.py:L23](../../app/retrieval/chunking.py#L23) [app/retrieval/private.py:L23](../../app/retrieval/private.py#L23)

#### 4. 面试官可能追问

- **追问：内容哈希解决一切吗？** 答：同文可能不同来源和权限，仍需身份版本。
- **追问：为何不用绝对路径？** 答：部署目录改变不应改变业务身份。

#### 5. 测试与证据

test_chunk_ids_are_stable 和 test_unstructured_chunk_ids_are_stable 验证重建确定性。[tests/unit/test_bm25.py:L6](../../tests/unit/test_bm25.py#L6) [tests/unit/test_unstructured_parser.py:L102](../../tests/unit/test_unstructured_parser.py#L102) 历史引用持久性未验证。

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

<a id="q062"></a>
### Q062：Dense Retrieval 为什么能找同义表达，在哪些情形会失败？

#### 1. 标准答案

Dense用训练得到的语义空间表示Query和文档，可匹配无词面重合的同义表达。罕见编号、否定、数值条件、领域迁移及长文截断仍会失败；相似度不是事实支持概率。

#### 2. 面试口述版

Dense 能找同义表达，是因为训练让相关问题和文档在表示空间接近，不是因为向量数据库理解业务。比如“到货后发现坏了”可能接近质量售后政策，但精确型号、否定条件和金额可能被忽略。项目可用远端或本地模型，也会降级 hash，后者不能证明这种语义能力。我会先确认实际 backend，再用无共同词的同义问题和只差一个数字的反例测试，观察候选是否正确。失败时补 BM25、精确字段或重排，而不是把相似分高直接当政策支持，更不能宣称所有未见领域都可泛化。

#### 3. Adaptive-RAG实际实现

已实现Query/文档编码和向量检索，hash明确是无权重降级；模型语义收益依赖实际backend。[app/providers/embeddings.py:L33](../../app/providers/embeddings.py#L33) [app/providers/embeddings.py:L143](../../app/providers/embeddings.py#L143) [app/retrieval/vector.py:L165](../../app/retrieval/vector.py#L165)

#### 4. 面试官可能追问

- **追问：维度越高越好吗？** 答：不保证，训练质量和领域匹配更重要，也增大存储成本。
- **追问：相似度0.8等于80%正确吗？** 答：不是，分值需按模型和数据校准。

#### 5. 测试与证据

test_injected_bge_m3_encodes 验证接口，非语义泛化。[tests/unit/test_embeddings.py:L36](../../tests/unit/test_embeddings.py#L36) 真实同义召回收益未验证。

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

<a id="q065"></a>
### Q065：为什么不能直接把 BM25 分数和余弦相似度加起来？

#### 1. 标准答案

BM25与余弦相似度的范围、分布和含义不同，直接相加会被某一路尺度主导。可用RRF绕开标定，或在验证集校准归一化与权重；不能每次Query随意缩放后宣称通用。

#### 2. 面试口述版

我不会把 BM25 分数和余弦相似度直接相加。BM25 随词频、稀有度和语料变化，余弦通常在另一范围，某一路数值更大就可能主导，并不代表更可靠。项目用 RRF 根据排名融合，避免假定原始分数同尺度。它也有代价：丢失分差，不能识别第一名明显优于第二名的程度，所以仍需同集消融。若将来做加权分数，我会先用固定验证集校准，检查不同问题类型和模型版本的稳定性，再冻结参数；不能对每个问题看答案后挑权重，也不能把RRF得分当语义置信度。

#### 3. Adaptive-RAG实际实现

已实现排名RRF，未实现学习式或分数校准融合。[app/retrieval/fusion.py:L16](../../app/retrieval/fusion.py#L16) [app/retrieval/hybrid.py:L63](../../app/retrieval/hybrid.py#L63)

#### 4. 面试官可能追问

- **追问：Min-Max归一化够吗？** 答：小候选和异常值会改变分布，仍需验证。
- **追问：为什么RRF不万能？** 答：它只处理排名，召回缺失和语义错误仍存在。

#### 5. 测试与证据

test_rrf_uses_rank_not_raw_score 覆盖分数尺度隔离。[tests/unit/test_rrf.py:L28](../../tests/unit/test_rrf.py#L28) 校准权重收益未验证。

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

<a id="q069"></a>
### Q069：Embedding 模型选型看哪些指标（语言、维度、成本、领域、速度）？

#### 1. 标准答案

按语言、领域和Query类型测召回/排序，再比较维度、最大长度、延迟吞吐、资源、许可证与费用。用实际语料和难例选型，关注编码契约、部署可用性与模型升级重建成本。

#### 2. 面试口述版

我会先看问题分布，而不是按排行榜或维度直接选。中文客服涉及口语、商品专名和政策条件，应以实际问题比较 Recall、首命中和例外覆盖，再看 CPU/GPU 延迟、批量速度、向量存储和部署成本。项目的本地模型名称可配置，Provider 类名不保证实际就是某个检查点；远端未配置且本地不可用会降级 hash。我会把运行 backend 写进结果，避免用无权重测试冒充选型。模型变更还要重建相容索引，并检查隐私、许可和长文截断；目前没有足够证据声称某个模型是本项目最优。

#### 3. Adaptive-RAG实际实现

已实现可配置本地/远端/hash工厂，未实现多模型选型平台或最优模型结论。[app/providers/embeddings.py:L69](../../app/providers/embeddings.py#L69) [app/providers/embeddings.py:L213](../../app/providers/embeddings.py#L213)

#### 4. 面试官可能追问

- **追问：只看公开榜单够吗？** 答：不够，领域、语言和失败类别可能不同。
- **追问：降维能直接用吗？** 答：需验证模型是否支持及召回损失，不能任意截断。

#### 5. 测试与证据

test_backend_follows_local_model_id 验证backend来源。[tests/unit/test_embeddings.py:L70](../../tests/unit/test_embeddings.py#L70) 大规模选型对照未验证。

<a id="q070"></a>
### Q070：余弦相似度、点积、L2 距离的差异和归一化影响？

#### 1. 标准答案

余弦为点积除以两向量范数，点积同时受长度影响，L2衡量欧氏距离。单位向量上点积=余弦，平方L2=2−2点积，排序相应等价；未归一化时不可混用。

#### 2. 面试口述版

我会先问向量是否归一化。余弦只比较方向，点积还受模长影响，L2看距离；单位向量时点积和余弦一致，L2排序也可互相转换。项目内存函数名字叫 cosine，但实现实际上是 zip 后求点积，依赖输入已归一化，且长度不一致时会忽略尾部。这是需要准确说明的实现边界，不能只按函数名介绍。当前本地编码与 hash 会归一化，远端输出则要核对其契约；Qdrant collection 使用的距离设置也要一致。验证时应包含非单位向量和维度错误，避免近邻结果看似正常但含义不同。

#### 3. Adaptive-RAG实际实现

已实现内存dot-product函数，Qdrant collection用COSINE，本地/Hash归一化；统一维度严格验证仍有限。[app/retrieval/vector.py:L19](../../app/retrieval/vector.py#L19) [app/retrieval/vector.py:L81](../../app/retrieval/vector.py#L81) [app/providers/embeddings.py:L24](../../app/providers/embeddings.py#L24)

#### 4. 面试官可能追问

- **追问：模长可能有信息吗？** 答：有些训练目标编码置信或频次，不能无脑丢弃。
- **追问：为什么维度错也可能出结果？** 答：zip截短，需在边界主动校验避免静默错误。

#### 5. 测试与证据

test_cosine_is_a_dot_product 和 test_cosine_ignores_trailing_length_mismatch 明示实际行为。[tests/unit/test_vector_store.py:L47](../../tests/unit/test_vector_store.py#L47) [tests/unit/test_vector_store.py:L51](../../tests/unit/test_vector_store.py#L51) 本轮未运行。

<a id="q071"></a>
### Q071：ANN 与精确 KNN 的区别，HNSW 为什么快？

#### 1. 标准答案

精确KNN计算全部候选距离，ANN用索引换取近似召回。HNSW以分层近邻图先粗定位再局部探索，避免全扫；M、构建与查询探索参数影响内存、速度和召回，没有对所有数据的恒定复杂度保证。

#### 2. 面试口述版

我会从准确性与资源取舍解释。精确 KNN 扫描所有向量，容易作为小规模金标准；ANN 少看候选来降低查询开销，因此可能漏掉真实最近邻。HNSW 利用分层图先远距离定位，再在底层扩展邻居，查询探索越多通常召回越高但更慢，图连接也占内存。项目内存存储是全量打分排序，Qdrant 把索引能力交给服务端，代码没有显式调 HNSW 参数，更没有千万级压测。所以我能说明原理和选型方法，不能报告虚构吞吐。真实比较应以同一向量集的精确结果为基准测召回与P95，而非只看接口返回快。

#### 3. Adaptive-RAG实际实现

已实现内存全量排序与Qdrant search，未实现HNSW调参或ANN基准。[app/retrieval/vector.py:L49](../../app/retrieval/vector.py#L49) [app/retrieval/vector.py:L125](../../app/retrieval/vector.py#L125)

#### 4. 面试官可能追问

- **追问：ANN Recall与RAG Recall一样吗？** 答：前者对精确近邻，后者对业务相关证据，金标准不同。
- **追问：探索参数越大越好吗？** 答：召回可能改善，但耗时和资源增加，需测曲线。

#### 5. 测试与证据

test_in_memory_search_orders_by_score 覆盖小规模精确排序。[tests/unit/test_vector_store.py:L68](../../tests/unit/test_vector_store.py#L68) ANN召回/延迟未验证。

<a id="q072"></a>
### Q072：Qdrant 与 Milvus、FAISS、Elasticsearch、pgvector 怎么选择？

#### 1. 标准答案

先比较过滤、混合检索、持久性、规模、运维和事务边界：FAISS是库需自建服务；pgvector便于SQL结合；ES强词法生态；向量数据库提供专门索引服务。具体产品能力随版本变化，应基于当前需求实测，不能只靠品牌排序。

#### 2. 面试口述版

我会先列需求，再挑产品。小规模本地实验可能用内存或 FAISS，已有 PostgreSQL 且重视事务集成时可评估 pgvector，词法与日志生态较重可考虑 Elasticsearch，专门向量服务则比较 Qdrant、Milvus 的过滤和运维方式。这里是一般选型思路，产品细节要核对实际版本，不能宣称谁永远最快。项目实际只实现 Qdrant 和内存适配，选择证据是已有服务接口与私有过滤需求，不是做过全部产品压测。百万、千万文档还要估算向量数量、维度、更新率和租户分布，并用相同数据比较质量、成本和失败恢复。

#### 3. Adaptive-RAG实际实现

项目已实现QdrantVectorStore/InMemoryVectorStore；Milvus、FAISS、ES、pgvector适配未实现。[app/retrieval/vector.py:L34](../../app/retrieval/vector.py#L34) [app/retrieval/vector.py:L67](../../app/retrieval/vector.py#L67)

#### 4. 面试官可能追问

- **追问：为何不把SQL当所有索引？** 答：要看规模和查询性能，权威数据与搜索索引可分工。
- **追问：产品替换最难在哪？** 答：过滤语义、索引契约、失败处理与迁移，不只API名称。

#### 5. 测试与证据

test_vector_retriever_searches_with_embedded_query 验证现有接口。[tests/unit/test_vector_store.py:L135](../../tests/unit/test_vector_store.py#L135) 跨产品性能对照未验证。

<a id="q073"></a>
### Q073：Qdrant metadata filter 在搜索时起什么作用？

#### 1. 标准答案

metadata filter限制向量搜索候选到租户、文档、版本等合法范围，需与可信身份和权威ACL结合。检索后再核验当前可见性；只在生成后删引用太晚，缓存也必须带scope/version。

#### 2. 面试口述版

过滤的价值是让搜索从一开始就在合法候选里进行，避免先搜到别人文档再寄希望于模型不说。项目私有 Qdrant 查询同时带认证 subject 和 SQL 当前合法 chunk ID 集合，命中后仍用 canonical 映射还原内容；这比只信向量 payload 更稳。缓存键也含租户和 generation，缓存内容只存 ID 并重新检查。公共向量路径没有同样的私有权限语义，所以不能混用。对于大规模合法 ID 集合，过滤开销还需要测量，我不会把代码有过滤就说已经证明所有租户规模性能，也不会允许用户自报tenant决定权限。

#### 3. Adaptive-RAG实际实现

已实现PrivateVectorStore.scoped_search的must过滤及私有canonical复核；未经scope的search直接拒绝。[app/retrieval/private.py:L67](../../app/retrieval/private.py#L67) [app/retrieval/private.py:L111](../../app/retrieval/private.py#L111) [app/retrieval/private.py:L216](../../app/retrieval/private.py#L216)

#### 4. 面试官可能追问

- **追问：后过滤够安全吗？** 答：它是补防线，不能允许越权内容进入模型或日志。
- **追问：用户能指定subject吗？** 答：由认证Principal和请求scope决定，不信任正文。

#### 5. 测试与证据

私有接口身份入口可核对private_access。[app/api/routes/knowledge.py:L31](../../app/api/routes/knowledge.py#L31) 通用向量测试[tests/unit/test_vector_store.py:L135](../../tests/unit/test_vector_store.py#L135)不替代真实跨租户验收；本轮未运行。

<a id="q074"></a>
### Q074：用户 Query 改写有哪些策略（指代消解、多查询、HyDE、扩展）？

#### 1. 标准答案

改写包括指代消解、同义扩展、多查询、子问题分解和HyDE假设文档。保留原问题、实体与否定，假设只能辅助检索而不能当证据。

#### 2. 面试口述版

我会先判断缺什么：用户说“这单”需要会话指代，口语政策可能需要同义扩展，复合问题可拆多个查询。HyDE 生成的假设文档只能寻找相近资料，不能当真实政策。项目有受控历史消解和多查询改写，普通路径始终保留原问题，最多用两条查询，没有 HyDE 实现。改写增加调用与候选，未必总有收益，所以应保留原文和改写结果，检查编号、否定、金额与目标变化，再比较召回。歧义没有足够上下文时应澄清，不能靠模型猜订单号；改写格式合法也不能证明语义等价。

#### 3. Adaptive-RAG实际实现

已实现QueryRewriter和最多两查询合并，HyDE未实现。[app/retrieval/query_rewrite.py:L18](../../app/retrieval/query_rewrite.py#L18) [app/agents/nodes/retrieval.py:L41](../../app/agents/nodes/retrieval.py#L41)

#### 4. 面试官可能追问

- **追问：能新增实体吗？** 答：不应凭空新增，要绑定用户或可信上下文。
- **追问：HyDE能直接回答吗？** 答：不能，需要真实检索证据。

#### 5. 测试与证据

test_ambiguous_untrusted_or_absent_entity_requires_clarification 检查歧义。[tests/unit/test_context_builder.py:L42](../../tests/unit/test_context_builder.py#L42) 改写语义等价率未验证。

<a id="q075"></a>
### Q075：什么时候 Query Rewrite 会改变用户原意？如何回退？

#### 1. 标准答案

改写可能丢否定、改数字、扩大范围或替换实体。保留原Query，约束关键字段，异常回退原文，歧义澄清；格式有效不等于语义等价。

#### 2. 面试口述版

例如“定制商品质量问题能退吗”被改成“定制商品七天无理由退货”，就改变了条件。改写可能更像常见问题，却偏离用户真正目标。项目保留原 Query，异常时回退原文，限制数量，但没有严格语义等价验证器。我会对编号、否定、金额和适用条件做专门测试，比较原查询与改写各自带来的证据。候选冲突时不能用改写覆盖原话，指代不明应追问。回退也要可观察，不能静默换问题再把错误归到知识库；即使保留原文，错误扩展仍可能在融合截断时挤掉正确候选。

#### 3. Adaptive-RAG实际实现

已实现异常回退和原文保留，语义漂移检测未实现。[app/retrieval/query_rewrite.py:L18](../../app/retrieval/query_rewrite.py#L18) [app/agents/nodes/retrieval.py:L42](../../app/agents/nodes/retrieval.py#L42)

#### 4. 面试官可能追问

- **追问：JSON合法可直接接受吗？** 答：只能证明结构，不能证明保留原意。
- **追问：保留原文就免疫吗？** 答：不能，错误候选仍会竞争排名。

#### 5. 测试与证据

test_current_explicit_target_overrides_old_and_assistant 检查实体优先级。[tests/unit/test_context_builder.py:L28](../../tests/unit/test_context_builder.py#L28) 改写漂移率未验证。

<a id="q076"></a>
### Q076：多路召回如何去重？源文档不同版本如何处理？

#### 1. 标准答案

同chunk ID合并，先按权威可见版本筛选再融合；相似正文不等于同证据。每路输入先去重，保留来源贡献，防重复抬分。

#### 2. 面试口述版

我先区分重复命中和版本冲突。同一块被 BM25、Dense 或两个改写查询找到，可以按 ID 合并；不同版本内容相似，却不能随便保留一份。项目普通查询用 by_id，RRF 跨路累计同 ID 分数，私有库先从 SQL 当前文档建立合法集合。需要说明的是，RRF 没有对每一路内部做 seen 去重，同路重复会多次贡献；第一份元数据胜出也不能解决版本冲突。后续应规范每路输入并记录版本来源，不能按正文相似就删掉新版例外。评测前也应去重，但不能说现行所有指标已经自动处理。

#### 3. Adaptive-RAG实际实现

已实现by_id和跨路RRF合并，单路重复保护未实现。[app/agents/nodes/retrieval.py:L43](../../app/agents/nodes/retrieval.py#L43) [app/retrieval/fusion.py:L25](../../app/retrieval/fusion.py#L25) [app/retrieval/private.py:L224](../../app/retrieval/private.py#L224)

#### 4. 面试官可能追问

- **追问：同ID正文不同怎么办？** 答：先修索引版本契约，不靠第一份胜出。
- **追问：单路重复会怎样？** 答：当前重复加分，建议输入去重。

#### 5. 测试与证据

test_rrf_prefers_docs_high_in_both_lists 覆盖跨路合并。[tests/unit/test_rrf.py:L18](../../tests/unit/test_rrf.py#L18) 单路防护未实现。

<a id="q077"></a>
### Q077：使用 Cross-Encoder 为什么通常更慢，如何控制推理开销？

#### 1. 标准答案

Cross-Encoder对每个query-document联合推理，不能预计算所有配对。候选裁剪、去重、批处理、长度与设备控制开销，比较净收益和长尾。

#### 2. 面试口述版

重排慢是因为每个候选都和当前问题一起计算，不能提前保存所有文档评分。候选越多、文本越长，计算通常越大。项目先融合去重再调 Provider，Cross-Encoder 将候选配对批量预测，在线程中执行，并配置最大长度；但 Docker 演示关闭它，词法降级不能当模型性能。我会先确认正确证据已在候选，再调数量和长度，测排序收益与 P95。线程主要避免阻塞事件循环，不会自动降低计算量，也不能据此说比不重排更快。缩短文本还可能丢例外，因此必须把质量和成本一起看。

#### 3. Adaptive-RAG实际实现

已实现pairs预测和max_length，Docker禁用模型重排。[app/providers/reranker.py:L96](../../app/providers/reranker.py#L96) [app/providers/reranker.py:L107](../../app/providers/reranker.py#L107) [app/demo/docker.py:L136](../../app/demo/docker.py#L136)

#### 4. 面试官可能追问

- **追问：线程等于更快吗？** 答：主要改善事件循环响应性。
- **追问：文档越短越好吗？** 答：关键条件可能被截掉，要测退化。

#### 5. 测试与证据

test_cross_encoder_uses_injected_model 验证配对。[tests/unit/test_reranker.py:L55](../../tests/unit/test_reranker.py#L55) 真实权重时延未验证。

<a id="q078"></a>
### Q078：Reranker 把正确证据排下去，如何诊断？

#### 1. 标准答案

先确认正确证据进入候选，再查重排前后ID、分数、原下标、截断和领域偏差，做无重排对照。召回缺失不能归因重排。

#### 2. 面试口述版

我先问正确证据是否进入重排。上游没召回时换模型也找不回；进入后被排低，才检查实际送入文本、截断、否定和领域偏差。项目按 Provider 返回的原下标还原块，还应检查下标与元数据是否对应。实际 backend 可能是 lexical，不能把词法失败归给 Cross-Encoder。诊断用同一候选做前后配对，看必要证据是否留在最终 N，再决定扩候选、换模型或调上下文。简单提高 N 可能掩盖排序问题并增加成本，所以要保留首次失败和阶段证据，不靠一条高分或流畅答案判断。

#### 3. Adaptive-RAG实际实现

已实现original_index映射，完整候选诊断平台未实现。[app/retrieval/reranker.py:L25](../../app/retrieval/reranker.py#L25) [app/providers/reranker.py:L55](../../app/providers/reranker.py#L55)

#### 4. 面试官可能追问

- **追问：增N就解决吗？** 答：减少丢失但增加噪声，仍需定位原因。
- **追问：相关等于支持吗？** 答：排序与事实蕴含分开。

#### 5. 测试与证据

test_document_reranker_rewrites_rank_and_source 检查映射。[tests/unit/test_reranker.py:L78](../../tests/unit/test_reranker.py#L78) 错排归因集未验证。

<a id="q079"></a>
### Q079：怎样选择检索相关性阈值，为什么不能固定通用阈值？

#### 1. 标准答案

阈值依赖模型、语料与分数定义，不能让BM25/RRF/余弦共用。用可回答和无答案集校准误答/误拒答，版本变化重新评估。

#### 2. 面试口述版

我不会给一个通用零点八阈值。余弦、BM25、RRF 和重排分不同，同模型换语料后分布也变；RRF 主要由路数和排名决定，更不是概率。项目没有统一校准阈值系统，主要靠有限候选、证据评分和生成后检查。我会用有答案、无答案、歧义与相似反例集，比较错误确定回答和误拒答成本，再按业务场景选边界。阈值只能辅助判断，多证据是否齐全要另测，改模型后也要重校准。最高分高可能只是覆盖一个子目标，不能直接当任务完成，更不能把未测的阈值说成线上保证。

#### 3. Adaptive-RAG实际实现

已有分数与SelfRAG评分，校准阈值未实现。[app/retrieval/fusion.py:L16](../../app/retrieval/fusion.py#L16) [app/retrieval/self_rag.py:L74](../../app/retrieval/self_rag.py#L74)

#### 4. 面试官可能追问

- **追问：最高分高就够吗？** 答：可能只支持部分问题。
- **追问：如何考虑业务风险？** 答：高风险减少无依据回答，同时报告误拒答成本。

#### 5. 测试与证据

test_no_evidence_is_insufficient_without_model_call 检查空证据。[tests/unit/test_p2s_answer_reliability.py:L151](../../tests/unit/test_p2s_answer_reliability.py#L151) 阈值校准未验证。

<a id="q080"></a>
### Q080：检索不到时应问用户澄清、拒答，还是网络搜索？

#### 1. 标准答案

缺实体或目标歧义先澄清，缺可靠授权资料说明不足，依赖故障标不可用；网络搜索需单独范围与来源策略，不能绕权限补答案。

#### 2. 面试口述版

我按原因选择动作。没说哪笔订单应澄清，政策库没材料应说明不足，依赖出错应提示暂时不可用，不能说事实不存在。网络搜索不是默认补救，私有客服政策不能网上随便拼，也不能发用户数据到未授权服务。项目有指代澄清和无证据拒答，公共两路空可能抛检索错误，私有依赖失败关闭返回，没有自动网络搜索。回答可保留已验证部分并说明缺口，避免把“没检索到”当成“世界没有”，也不让模型凭常识补金额或规则。转人工应针对无法可靠处理的风险，而非代替可解决的简单澄清。

#### 3. Adaptive-RAG实际实现

已实现澄清/不足，自动联网搜索未实现。[app/agents/nodes/generate.py:L35](../../app/agents/nodes/generate.py#L35) [app/agents/nodes/faithfulness.py:L94](../../app/agents/nodes/faithfulness.py#L94) [app/retrieval/hybrid.py:L59](../../app/retrieval/hybrid.py#L59)

#### 4. 面试官可能追问

- **追问：空检索等于无资料吗？** 答：可能是解析、权限、索引或故障。
- **追问：为何不总转人工？** 答：简单歧义可先澄清，高风险仍应保守转接。

#### 5. 测试与证据

test_no_evidence_is_insufficient_without_model_call 覆盖空证据。[tests/unit/test_p2s_answer_reliability.py:L151](../../tests/unit/test_p2s_answer_reliability.py#L151) 联网补救未实现。

<a id="q081"></a>
### Q081：检索命中但答案仍不对，怎么区分检索和生成故障？

#### 1. 标准答案

逐阶段查Gold是否在语料、召回、融合/重排和实际Prompt中，最后查支持与完整性。以首次丢失处归因，不一次修改所有层。

#### 2. 面试口述版

我沿证据路径排查：文档正确解析且用户可见吗，候选有必要块吗，重排留下吗，最终 Prompt 有没有裁掉？模型看到了仍错，才查条件理解、数字绑定、指令与裁判。项目生成只取前六块，裁判前八块，Self-RAG 可能返回更多，因此“结果里有”不等于“生成看到”。必须核对实际组装顺序，不能只展示检索页面。不同故障分别回归，检索和生成可能同时有问题，流畅也不能免除证据核查。先固定失败问题和版本，再单变量修正，避免改了切片、模型和Prompt却无法解释收益来源。

#### 3. Adaptive-RAG实际实现

已有分离节点和有限证据组装，自动阶段归因器未实现。[app/agents/nodes/generate.py:L61](../../app/agents/nodes/generate.py#L61) [app/guardrails/hallucination.py:L68](../../app/guardrails/hallucination.py#L68)

#### 4. 面试官可能追问

- **追问：结果有证据为何仍错？** 答：可能组装裁剪或条件误读。
- **追问：如何证明修复？** 答：同样本单变量比较首次丢失阶段及最终答案。

#### 5. 测试与证据

test_judge_outage_keeps_all_verified_facts_not_last_result 检查安全事实。[tests/unit/test_p2s_answer_reliability.py:L76](../../tests/unit/test_p2s_answer_reliability.py#L76) 自动归因未验证。

<a id="q082"></a>
### Q082：知识库千万级规模如何做分区、批量索引和增量更新？

#### 1. 标准答案

估算块数、维度、更新和租户分布，设计分区/分片、批量编码写入、幂等日志、版本发布与删除对账。规模方案需真实过滤和长尾压测。

#### 2. 面试口述版

我先把千万文档换算成向量数量，因为每篇块数决定存储与更新成本。再按租户热点设计分区，批量解析编码，记录增量水位，重建追上更新后发布，并保证权限与删除一致。项目是小型链路，公共一次加载编码，私有每租户最多一百文档且正文有限，不具备千万级能力。分片、队列和双索引发布是设计方案，不能编吞吐数字。验证还包括过滤选择率、热点、恢复和删除传播，不只是平均向量搜索耗时；SQL、BM25与缓存也可能先成为瓶颈，不能只扩向量服务就宣称解决。

#### 3. Adaptive-RAG实际实现

项目未实现千万级平台；公共链路整批load。私有正常API新建每subject最多100篇，接口content最多10000字符；`_corpus()`仍全量装载SQL现有文档，并非面向大规模的分页/分片检索。列表接口的limit(100)是另一约束，不能和新建门槛混为一谈。[app/retrieval/ingest.py:L79](../../app/retrieval/ingest.py#L79) [app/retrieval/private.py:L150](../../app/retrieval/private.py#L150) [app/retrieval/private.py:L140](../../app/retrieval/private.py#L140) [app/api/routes/knowledge.py:L18](../../app/api/routes/knowledge.py#L18)

#### 4. 面试官可能追问

- **追问：只扩Qdrant够吗？** 答：解析、SQL、BM25和缓存也受限。
- **追问：租户分片有何风险？** 答：大租户热点与小租户碎片，需分布数据。

#### 5. 测试与证据

test_hybrid_retrieves_return_policy 为小语料/hash验证。[tests/integration/test_hybrid_retrieval.py:L11](../../tests/integration/test_hybrid_retrieval.py#L11) 千万级未验证。

<a id="q083"></a>
### Q083：怎样做混合检索消融实验并保证公平（固定Query、数据集、模型）？

#### 1. 标准答案

冻结Query、语料、模型、权限和预算，只改变召回/融合/重排开关；分别评候选与答案，记录实际backend、缓存状态、质量和成本。

#### 2. 面试口述版

我会比较 BM25-only、Dense-only、RRF 和加重排，但先冻结数据与模型，不能每组用不同问题或 K。文档级与 chunk 级标签一致，缓存冷暖、权限和改写策略也要可比。运行器有多种链路，实际 backend 必须记录，hash 与 lexical 只能算降级功能验证，不代表真实 Dense/Cross-Encoder。还要检查某组是否多了改写或更大上下文，否则收益无法归因。逐问题配对看必要证据和最终答案，同时报告延迟与费用；旧合成集分数不能说成用户效果，也不能反复看留出集调到满意再称盲测。

#### 3. Adaptive-RAG实际实现

已实现eval_retrieval多链入口，真实模型全面公平消融未验证。[eval/runner.py:L166](../../eval/runner.py#L166) [app/providers/embeddings.py:L213](../../app/providers/embeddings.py#L213)

#### 4. 面试官可能追问

- **追问：缓存如何处理？** 答：分别声明冷暖，避免某组独享热缓存。
- **追问：固定K就公平吗？** 答：块长、改写与重排预算也影响输入量。

#### 5. 测试与证据

test_hybrid_retrieves_return_policy 使用hash。[tests/integration/test_hybrid_retrieval.py:L11](../../tests/integration/test_hybrid_retrieval.py#L11) 本轮未运行实验。

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

<a id="q085"></a>
### Q085：检索到正确片段，为什么LLM仍可能幻觉？

#### 1. 标准答案

正确证据仍可能因注意力、否定误读、参数知识、截断或注入被误用。检查实际上下文、事实绑定和引用，验证失败时保守回退，召回命中不是答案保证。

#### 2. 面试口述版

检索成功只是把材料送到门口，不保证正确使用。模型可能忽略定制例外、拼错订单金额，或被长上下文和文档命令干扰。项目生成要求证据，引用 ID 有白名单，之后有 Faithfulness 和一次修正，但裁判也会失败，Offline 还跳过它，不能说没有幻觉。我会专查数字、主体、否定和例外，并确认必要块进入前六块生成输入。确定业务事实适合受控模板，不能因相似度高就开放确定回答。最后还要查答案是否覆盖全部目标：一句有依据的话，也可能完全没有完成用户任务。

#### 3. Adaptive-RAG实际实现

已实现规则、引用过滤和有限复核，零幻觉保证未实现。[app/prompts/answer.py:L5](../../app/prompts/answer.py#L5) [app/agents/nodes/generate.py:L150](../../app/agents/nodes/generate.py#L150) [app/agents/nodes/faithfulness.py:L127](../../app/agents/nodes/faithfulness.py#L127)

#### 4. 面试官可能追问

- **追问：ID真实即正确吗？** 答：仍可能不支持该句。
- **追问：支持就完成任务吗？** 答：完整性和业务目标另测。

#### 5. 测试与证据

test_generated_length_is_not_accepted_even_with_complete_json 检查截断。[tests/unit/test_p2s_answer_reliability.py:L159](../../tests/unit/test_p2s_answer_reliability.py#L159) 全量幻觉率未验证。

<a id="q086"></a>
### Q086：如何区分“知识库无资料”“召回失败”“生成未利用证据”？

#### 1. 标准答案

先核对授权语料是否含资料，再用Gold判断索引/召回，最后核对Prompt与答案利用。依赖故障、权限不可见和真正无资料分别记录。

#### 2. 面试口述版

我先确认当前授权范围是否有材料，而不只看搜索空返回。原文有但解析未入库是数据问题；已索引却没召回是检索问题；被重排或上下文裁掉是组装问题；模型看到仍错才查生成。项目分离导入、检索、重排与生成，但没有自动全链归因器。私有权限和版本也必须纳入，因为别人库里有不等于当前用户能回答。应保留阶段证据和失败样本，区分依赖不可用与知识缺失，不能用一次空返回断言不存在。若答案凭常识碰巧对，也不能掩盖证据链失败，仍需修复来源。

#### 3. Adaptive-RAG实际实现

已有分离模块与tracing，自动知识缺失分类未实现。[app/retrieval/ingest.py:L79](../../app/retrieval/ingest.py#L79) [app/agents/nodes/retrieval.py:L20](../../app/agents/nodes/retrieval.py#L20) [app/agents/nodes/generate.py:L61](../../app/agents/nodes/generate.py#L61)

#### 4. 面试官可能追问

- **追问：别人库有算可答吗？** 答：不算，Gold必须尊重权限。
- **追问：检索异常算无答案吗？** 答：应标依赖故障。

#### 5. 测试与证据

test_no_evidence_is_insufficient_without_model_call 覆盖缺证据。[tests/unit/test_p2s_answer_reliability.py:L151](../../tests/unit/test_p2s_answer_reliability.py#L151) 自动根因分类未验证。

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

<a id="q088"></a>
### Q088：遇到相互冲突或过期政策时如何回答？

#### 1. 标准答案

检查对象、条件、可信revision和生效时间，区分一般规则/例外与真冲突；无法消解则展示差异并核验，不能任取高分或创造综合政策。

#### 2. 面试口述版

遇到政策冲突，我先不让模型选一个。可能是适用商品不同、一般规则与例外，也可能真是旧版没撤销。先核来源、revision、对象和生效范围，再说明能确认的结论。项目私有库限定 SQL 当前 revision，公共默认 v1，没有完整日期治理和冲突裁决，不能保证自动发现过期政策。无法消解时列出差异，避免承诺金额或办理结果，转人工核验。排序高不代表权威，上传晚也未必已经生效；不能把两版拼成新规则。验收应专门加入相同关键词、相反条件的样本，检查是否诚实保留冲突。

#### 3. Adaptive-RAG实际实现

部分实现revision可见性，生效治理与冲突裁决未实现。[app/retrieval/private.py:L23](../../app/retrieval/private.py#L23) [app/retrieval/chunking.py:L40](../../app/retrieval/chunking.py#L40) [app/prompts/answer.py:L9](../../app/prompts/answer.py#L9)

#### 4. 面试官可能追问

- **追问：新版一定优先吗？** 答：核对生效和适用对象，不只上传时间。
- **追问：两版可合并吗？** 答：不能擅造政策，应核验冲突。

#### 5. 测试与证据

test_no_evidence_is_insufficient_without_model_call 为保守机制测试。[tests/unit/test_p2s_answer_reliability.py:L151](../../tests/unit/test_p2s_answer_reliability.py#L151) 冲突专项未验证。

<a id="q089"></a>
### Q089：引文 ID、文档ID、页码及权限如何贯通到生成结果？

#### 1. 标准答案

从授权文档revision到chunk ID，再到生成白名单与Citation；页码/offset需显式传递，回链重新鉴权。存在性、定位和语义支持分别验证。

#### 2. 面试口述版

引用是一条数据链，不是末尾加编号。先确定文档身份、版本和权限，块保存来源定位，模型只引用本次合法块，后端映射成 Citation。项目有 document_id、chunk_id、section，解析器可存页码，但 Citation 没页码字段，所以不能说页面定位已贯通。白名单也只证明 ID 存在，仍需检查语义支持。下载或查看原文要按当前身份再次验证，不能持有引用就永久有权，更不能暴露内部路径。长期引用还涉及版本保留和删除后失效，而当前没有通用原件下载系统，这些限制应明确说清。

#### 3. Adaptive-RAG实际实现

已实现文档/块/section映射；页码metadata未贯通Citation，offset未实现。[app/schemas/retrieval.py:L23](../../app/schemas/retrieval.py#L23) [app/agents/nodes/generate.py:L150](../../app/agents/nodes/generate.py#L150) [app/retrieval/unstructured_parser.py:L343](../../app/retrieval/unstructured_parser.py#L343)

#### 4. 面试官可能追问

- **追问：有ID即可下载吗？** 答：不能，必须重新鉴权。
- **追问：页码能逐句定位吗？** 答：不能承诺，正文可能取首个页码。

#### 5. 测试与证据

test_title_becomes_section_and_table_stays_whole 检查元数据。[tests/unit/test_unstructured_parser.py:L41](../../tests/unit/test_unstructured_parser.py#L41) 页码导航未实现。

<a id="q090"></a>
### Q090：如何避免用户下载或引用他人私有文档？

#### 1. 标准答案

可信认证决定scope，SQL先限定可见文档，向量、BM25和缓存同范围，生成仅见授权证据；下载回链再次鉴权，不能靠Prompt防越权。

#### 2. 面试口述版

防泄露不能在最后删敏感词。检索、缓存和生成前都要限制可见范围，下载回链也重新鉴权。项目 subject 来自 Principal，SQL 当前文档形成 canonical，向量同时过滤租户与合法 ID，缓存只存 ID 后重新核验，不信缓存文本。公共共享检索不能混作私有回退。项目没有通用原件下载接口，我不会编造下载能力。历史有 A 可见合成政策、B 不可见的有限真实证据，但不等于所有攻击已证明安全。还应测改ID、过期引用、删除缓存与依赖失败，确保失败时不绕权限填答案。

#### 3. Adaptive-RAG实际实现

已实现私有scope和缓存复核，通用下载未实现。[app/api/routes/knowledge.py:L31](../../app/api/routes/knowledge.py#L31) [app/retrieval/private.py:L67](../../app/retrieval/private.py#L67) [app/retrieval/private.py:L216](../../app/retrieval/private.py#L216)

#### 4. 面试官可能追问

- **追问：Prompt够吗？** 答：不够，越权内容不能进入模型。
- **追问：租户缓存键够吗？** 答：还需版本和合法集合复核。

#### 5. 测试与证据

20261115历史报告记录A/B隔离。[research/docs/agent_engineering_upgrade/deepseek_business_acceptance/REPORT.zh-CN.md:L21](../../research/docs/agent_engineering_upgrade/deepseek_business_acceptance/REPORT.zh-CN.md#L21) test_concurrent_roots_and_privacy仅补追踪隐私。[tests/unit/test_tracing.py:L17](../../tests/unit/test_tracing.py#L17) 本轮未运行。

<a id="q091"></a>
### Q091：Context 组装中如何去重、截断及控制 token预算？

#### 1. 标准答案

按ID/版本去重、权限过滤后保留必要证据，预算包含规则、历史、工具和最大输出；压缩保持主体与条件，估算和usage分开。

#### 2. 面试口述版

上下文预算不只算正文。系统规则、历史、工具参数、JSON与最大输出都占空间，去重后还要按子目标留必要条件。项目按 chunk ID 汇总，生成取前六块，完整请求再按 UTF-8 字节加余量检查，这不是精确 tokenizer。记忆选择可控制历史，但没有通用最优证据装箱算法。我会先去重和降噪，保留主体、金额与例外，超预算就减少非必要材料或澄清，不能截掉关键条件后继续确定回答。实际费用另看可信 usage，不能把字符估计当账单，也不能只测平均输入而漏极长工具结果。

#### 3. Adaptive-RAG实际实现

已实现by_id、前六块和完整请求界限，通用预算分配器未实现。[app/agents/nodes/retrieval.py:L43](../../app/agents/nodes/retrieval.py#L43) [app/agents/nodes/generate.py:L61](../../app/agents/nodes/generate.py#L61) [app/memory/budget.py:L14](../../app/memory/budget.py#L14)

#### 4. 面试官可能追问

- **追问：直接截N字符安全吗？** 答：可能切掉否定或实体。
- **追问：超预算还能发送吗？** 答：不行，在HTTP前阻断。

#### 5. 测试与证据

test_selected_memory_payload_bounded_without_truncating_entity 检查实体。[tests/unit/test_context_budget.py:L34](../../tests/unit/test_context_budget.py#L34) 最优装箱未验证。

<a id="q092"></a>
### Q092：怎么解决“lost in the middle”？

#### 1. 标准答案

长上下文中部证据可能被低效利用，可减噪、重排、分解与受控摘要；做位置扰动测试，不能保证固定头尾摆放适用于所有模型。

#### 2. 面试口述版

我不会把答案放最前就当问题解决。长上下文材料多且相似，中间条件容易漏，多个版本或订单尤其危险。项目用重排和有限块减少输入，但没有专门位置鲁棒性实验或自动控制器。我会固定证据内容，改变位置与噪声数量，检查数字、否定和例外是否仍正确，再考虑任务分解或先抽证据。摘要也会丢信息，应保留来源核验，不能删掉关键条件后用回答流畅当成功。评测同时看模型版本和实际输入长度，某个样本有效的摆放方式不应被包装成通用规律，检索命中也不能代替证据利用测试。

#### 3. Adaptive-RAG实际实现

已有有限证据与rerank，专门位置治理未实现。[app/agents/nodes/generate.py:L61](../../app/agents/nodes/generate.py#L61) [app/retrieval/reranker.py:L15](../../app/retrieval/reranker.py#L15)

#### 4. 面试官可能追问

- **追问：放头部一定好吗？** 答：不保证，证据关系也重要。
- **追问：摘要一定改善吗？** 答：可能丢例外，需对照来源。

#### 5. 测试与证据

test_document_reranker_rewrites_rank_and_source只测元数据。[tests/unit/test_reranker.py:L78](../../tests/unit/test_reranker.py#L78) 位置扰动未验证。

<a id="q093"></a>
### Q093：什么情况下固定模板回答比生成式回答更合适？

#### 1. 标准答案

金额、状态、审批和合规话术等确定字段适合模板；解释与多源整合适合生成。模板也需处理缺字段、对象绑定和时效，不能复述过期值。

#### 2. 面试口述版

我优先让工具和模板表达确定事实。订单金额、是否取消和是否等待确认有明确来源，不必让模型自由发挥；生成适合解释政策和下一步，不能替代事务结果。项目 safe_answer 在生成或裁判故障时输出已验证工具事实，pending 操作也直接返回摘要，降低虚构金额和未确认成功风险。模板仍可能用旧结果或漏目标，所以要检查当前工具、实体与缺字段，不能只测字符串像答案。可以在固定事实外围生成自然解释，但事实字段保持受控，工具失败就说未知而不是填默认值。申请退款也不能写成已经到账。

#### 3. Adaptive-RAG实际实现

已实现safe_answer和pending分支，非全场景模板化。[app/agents/answer_evidence.py:L132](../../app/agents/answer_evidence.py#L132) [app/agents/nodes/generate.py:L48](../../app/agents/nodes/generate.py#L48)

#### 4. 面试官可能追问

- **追问：模板太生硬怎么办？** 答：外围可生成，关键事实受控。
- **追问：工具失败如何填？** 答：明确未知，不编默认金额。

#### 5. 测试与证据

test_fallback_never_claims_unconfirmed_write_or_refund_settlement 覆盖安全措辞。[tests/unit/test_p2s_answer_reliability.py:L144](../../tests/unit/test_p2s_answer_reliability.py#L144) 本轮未运行。

<a id="q094"></a>
### Q094：为什么仅靠Prompt写“不知道就说不知道”不够？

#### 1. 标准答案

Prompt是概率性引导，不能证明证据、权限和事务；需要schema、后端授权、引用白名单、事实校验与故障回退，验证失败路径。

#### 2. 面试口述版

“不知道就说不知道”有用，但模型可能误以为自己知道，把相关材料当充分证据。文档注入、过期历史也会干扰，不能只写一句就宣布安全。项目还有结构化解析、引用过滤、Faithfulness 和安全回退，工具执行另有后端确认与权限。每层解决不同问题，也有边界，裁判会故障，正则不能覆盖所有攻击。我会用无答案、矛盾、工具失败和越权样本看是否停止，而不只展示正常回答。没有证据不能凭常识补业务事实；支持一句话也不能证明全部任务完成，风险控制必须落到代码和可观察结果。

#### 3. Adaptive-RAG实际实现

已实现多层约束，任意注入免疫未实现。[app/providers/json_parser.py:L46](../../app/providers/json_parser.py#L46) [app/agents/nodes/faithfulness.py:L79](../../app/agents/nodes/faithfulness.py#L79) [app/tools/base.py:L73](../../app/tools/base.py#L73)

#### 4. 面试官可能追问

- **追问：模型说有权可执行吗？** 答：不能，权限来自后端。
- **追问：Judge故障算支持吗？** 答：不算，应明确故障并回退。

#### 5. 测试与证据

test_judge_exact_error_category_no_retry 检查分类。[tests/unit/test_p2s_answer_reliability.py:L55](../../tests/unit/test_p2s_answer_reliability.py#L55) 全攻击免疫未验证。

<a id="q095"></a>
### Q095：怎样检测数字、日期、金额、订单状态等事实错误？

#### 1. 标准答案

把声明主体、字段、单位与时间绑定当前证据，规范化分/元、日期和状态；精确规则补语义裁判，不只检查相同数字出现。

#### 2. 面试口述版

金额错误常是主体或单位错。六千八百分是六十八元，不能当六千八百元，旧订单也不能填当前订单。项目安全回答来自工具，答案评分会规范化金额并要求证据绑定，实时状态由工具查。我会测相同数字属于不同订单、退款申请不等于到账、确认前不能声称取消。规则适合精确值，语义裁判辅助条件关系。已有机制并非覆盖所有日期数字，新字段还需扩展契约。状态发生后续变更时旧观察要失效，最终结论应对应最新已验证操作，而不是把整个会话数字集合当成可随意引用的事实池。

#### 3. Adaptive-RAG实际实现

已有金额规范化、答案评分与safe_answer，通用事实抽取未实现。[eval/answer_scoring.py:L193](../../eval/answer_scoring.py#L193) [eval/answer_scoring.py:L261](../../eval/answer_scoring.py#L261) [app/agents/answer_evidence.py:L132](../../app/agents/answer_evidence.py#L132)

#### 4. 面试官可能追问

- **追问：数字出现即正确吗？** 答：还要绑定对象、单位和字段。
- **追问：状态变更怎么处理？** 答：最新已验证结果覆盖旧状态。

#### 5. 测试与证据

test_later_confirmed_write_invalidates_earlier_status_in_answer 覆盖时序。[tests/unit/test_p2s_answer_reliability.py:L167](../../tests/unit/test_p2s_answer_reliability.py#L167) 全字段覆盖未验证。

<a id="q096"></a>
### Q096：有什么无答案拒答率、误拒答率的评测方法？

#### 1. 标准答案

在人工预标注可答/不可答集计算正确拒答、误拒答和错误确定回答；歧义澄清与依赖故障单列，明确分母和风险。

#### 2. 面试口述版

我先定义标签，不只数“不知道”。无资料应拒答，有充分授权证据却拒答是误拒答，目标不清需澄清，API故障也不该混在一起。项目有不足、裁判无效和调用错误，但没有完整拒答仪表盘。我会人工核对当前语料权限下可否回答，再固定模型和阈值配对评估，同时看错误确定回答。高风险政策应保守，但必须报告误拒答成本，不能认为拒得越多越好。基础设施失败也不能全部从分母删掉做漂亮指标；无答案样本必须有真实来源核对，不能用系统自己判断充当Gold，关键词命中也不足以判可答。

#### 3. Adaptive-RAG实际实现

已有不足与故障分类，成套拒答指标未实现。[app/guardrails/hallucination.py:L16](../../app/guardrails/hallucination.py#L16) [app/agents/nodes/faithfulness.py:L114](../../app/agents/nodes/faithfulness.py#L114)

#### 4. 面试官可能追问

- **追问：澄清算拒答吗？** 答：建议单列并预定义。
- **追问：没有Gold怎么评？** 答：先人工审授权资料。

#### 5. 测试与证据

test_no_evidence_is_insufficient_without_model_call 检查状态。[tests/unit/test_p2s_answer_reliability.py:L151](../../tests/unit/test_p2s_answer_reliability.py#L151) 拒答率/误拒答率未验证。

<a id="q097"></a>
### Q097：RAG vs 长上下文直接塞原文 vs 微调如何选择？

#### 1. 标准答案

RAG适合动态知识、引用与权限；长上下文适合有限完整材料；微调适合行为格式与领域能力。可组合，按更新、预算和可验证性选择。

#### 2. 面试口述版

我从知识更新和任务结构选择。政策常变、需要引用与隔离时优先 RAG；材料少且一次能完整放入时长上下文可能简单；格式或领域表达总失败才考虑微调。它们能组合，但微调不能替代实时订单查询，也难可靠删除已学政策。项目是 RAG 加工具与受控上下文，没有训练流水线。我会用同问题比较质量成本，不把更大窗口当免费知识库，也不因微调显得高级就增加训练依赖。长上下文仍有权限和证据利用问题，RAG也有召回失败；选择取决于可验证结果，缺资料仍应明确不足而不是用参数知识补齐。

#### 3. Adaptive-RAG实际实现

已实现RAG和工具，训练与三方案公平对照未实现。[app/agents/nodes/retrieval.py:L20](../../app/agents/nodes/retrieval.py#L20) [app/agents/nodes/generate.py:L61](../../app/agents/nodes/generate.py#L61)

#### 4. 面试官可能追问

- **追问：微调适合订单状态吗？** 答：不适合，实时查权威库。
- **追问：长窗口能省检索吗？** 答：有限材料可，但成本权限仍需测。

#### 5. 测试与证据

test_hybrid_retrieves_return_policy 验证RAG。[tests/integration/test_hybrid_retrieval.py:L11](../../tests/integration/test_hybrid_retrieval.py#L11) 三方案对照未验证。

<a id="q098"></a>
### Q098：如何处理结构化数据库事实和文本知识库同时参与回答？

#### 1. 标准答案

SQL提供当前事实/事务，文本提供政策，按实体时间条件绑定，分清已验证事实、规则与未解目标；文本不能覆盖实时权限状态。

#### 2. 面试口述版

订单支付、金额和取消提交来自数据库工具，退货范围和材料来自政策文本。模型能解释整合，但旧文档或历史不能覆盖实时状态，政策允许也不等于操作完成。项目生成接收检索证据和工具 JSON，Agent检查子目标是否有观察，故障时 safe_answer保留事实。它不是通用 SQL/文档联合查询引擎，跨源冲突还需明确规则。验收应检查对象、单位、例外和事务，不只是两种来源都在 Prompt。缺某类证据应具体说明哪项无法确认，不能拿政策话术替代订单查询，也不能把工具失败包装成正常无数据。

#### 3. Adaptive-RAG实际实现

已实现证据/工具组装及coverage，通用跨源优化器未实现。[app/agents/nodes/generate.py:L61](../../app/agents/nodes/generate.py#L61) [app/agents/nodes/generate.py:L107](../../app/agents/nodes/generate.py#L107) [app/agents/goals.py:L127](../../app/agents/goals.py#L127)

#### 4. 面试官可能追问

- **追问：可取消等于已取消吗？** 答：不等，需确认和提交结果。
- **追问：来源冲突怎么办？** 答：实时事实看工具，政策另核版本范围。

#### 5. 测试与证据

test_query_goal_uses_observed_tool_result_not_answer 验证观察。[tests/integration/test_goal_evaluation.py:L11](../../tests/integration/test_goal_evaluation.py#L11) 通用跨源冲突评测未验证。
