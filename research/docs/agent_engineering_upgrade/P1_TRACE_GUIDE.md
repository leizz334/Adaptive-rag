# P1 Trace 接入与隐私

采用LangSmith适配器，核心记录器平台中立；无需更换DeepSeekProvider或业务Graph。默认 `AGENT_TRACING_ENABLED=false`；为true时默认backend=local，输出metadata-only结构化agent_span日志。`AGENT_TRACING_BACKEND=langsmith` 必须另设 `AGENT_LANGSMITH_API_KEY`，不借用DeepSeek密钥或隐式开启云端。

主要文件：`app/observability/tracing.py`、`langsmith_exporter.py`、Settings、ChatService、已装饰节点/Provider/检索/工具/摘要边界。原trace_id、日志、Prometheus保持；新增可选root_run_id响应/SSE字段。每轮服务端UUID root；原trace_id/request/session/user只导出进程随机密钥HMAC引用。响应原trace_id仍可结合root_run_id关联本地日志；HMAC跨进程/重启不稳定，不能当持久用户身份。

范围：session load/confirmation、Graph invoke或stream、10个节点、DeepSeek逻辑调用与每次HTTP尝试、改写/grade、Hybrid/BM25/vector/rerank、Tool.run、摘要、persist/commit；默认不采集输入、输出、原始参数、完整State、异常文字或stack。LLM逻辑span记录可得usage，attempt不重复计tokens；失败usage unknown。上下文随async task、to_thread传播，SSE根直到迭代结束/关闭；关闭会等待被取消Graph任务清理。最终正文仍是原来校验后的48字符切段。

为防环境变量意外启用全State采集，ChatService的ainvoke/astream显式在 `langsmith.tracing_context(enabled=False)` 中运行；项目手工metadata spans独立于此开关。不要再配置自动Graph callback捕获原始State。Node/Provider spans以静态用途命名，不获取模型隐藏思维链。

每轮默认上限256个span（配置1–4096）；云端队列默认32批（1–1024），满时丢弃而不阻塞业务。后台线程单独调用SDK，异常只计数；关闭等待有上限，不因遥测重试业务工具。关键限制：极慢导出时可能丢数据/未flush；当前是按轮结束成批导出，不是崩溃恢复日志。export_errors/dropped和dropped_spans在记录器/导出器对象可读，不应解释成业务成功率。

LangSmith从原传递依赖变为显式依赖 `>=0.14.7,<0.15`；锁文件继续使用原0.14.7包，仅增加根依赖/metadata边，没有安装或升级。环境是0.14.12；当前签名已离线检查，测试覆盖注入假Client的payload而非云端连通。Conda内没有uv可执行文件，`conda run -n adaptive-rag uv lock --offline`失败，未安装uv；锁元数据做最小手工同步，最终验收另检查解析与版本约束，不能声称uv resolver已运行。

官方依据：[手动Tracing](https://docs.langchain.com/langsmith/annotate-code)、[隐藏输入输出与元数据](https://docs.langchain.com/langsmith/mask-inputs-outputs)。本实现不依赖最新文档中所有接口，使用本机SDK已核对的Client/create_run/tracing_context；SDK的API和隐藏元数据选项不可当成业务ACL。

实际离线验证：并发root不串联、父子关系、默认关闭与业务响应一致、异常仅类型、列表密钥/手机号/订单canary不在payload、span数量上限、generator关闭、真实ChatService+Graph+SQLite正常/SSE/早关、MockTransport DeepSeek调用和usage、假Client导出。完整命令：

```powershell
conda run --no-capture-output -n adaptive-rag python -B -m pytest -q -p no:cacheprovider --basetemp=research/docs/agent_engineering_upgrade/evidence/.tmp/b-full --junitxml=research/docs/agent_engineering_upgrade/evidence/P1-B-pytest.xml
```

P1-B当前全套173 passed，1条原有LangChain预弃用警告；真实云端、账号权限、远程区域和计费NOT_RUN。生产客户端user_id可信性、全面日志脱敏和业务幂等并发等P0风险没有因追踪自动修复；本地评测原始参数不能传入该导出器。无正式业务数据或API key上传。

P1-F追加验收：现已通过真实LangSmith SDK的纯离线HTTP Adapter序列化测试；原先仅假Client的B阶段证据不被覆盖。SSE根移入拥有流的生产任务，经有界队列/送达确认维持生命周期；路由与Response显式关闭嵌套迭代器，并通过实际ASGI断线测试。导出/本地日志边界再次应用白名单，防未来意外加入原始元数据。完整最终结果见P1_REPORT.md，云端连通仍NOT_RUN。
