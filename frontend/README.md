# Adaptive-RAG Agent Web 工作台

React + TypeScript + Vite，复用原聊天/Markdown组件。支持HTTP/SSE、多轮内存会话、私有知识库CRUD/文本上传/检索、真实引用、HITL确认/撤销/幂等重放、真实执行Trace与离线Experience证据。

## 启动

需要Node20.19+或22.12+，Python后端按项目说明部署。安全可复现的零付费环境见[演示指南](../research/docs/agent_engineering_upgrade/s1_web_upgrade/DEMO_GUIDE.md)。

```bash
npm ci
npm run dev
npm test
npm run typecheck
npm run build
```

Vite默认127.0.0.1:5173，代理/api到127.0.0.1:8002。可用VITE_API_BASE显式配置HTTPS或本机API；不要把Token放VITE变量。构建dist可由FastAPI同源静态服务。跨源部署仍须由可信网关配置TLS/CORS；没有新增不安全的通配跨源配置。

## 身份与会话

打开页面后输入可信本地运维签发的开发Bearer凭证；/auth/me验证并返回主体。无生产登录/发证HTTP接口，不能客户端自报user_id。凭证只在内存、无日志/持久化；刷新重新认证。所有身份相关请求在切换时中止，旧401不能清除新身份。会话列表和可见内容保持页面内存；刷新重新认证后，通过Owner保护的SQL接口读取最近50个本人会话，选择后恢复最近100条user/assistant文本，可继续同session对话。旧引用/Trace/HITL状态不从文本重建，历史有明确提示。隐藏/删除按钮仅从当前页隐藏，SQL历史保留；旧localStorage不加载不覆盖，主题设置仍可保存。

SSE节点事件实时展示；答案通过服务端完整验证/提交后才分块传输，不是模型原始token流。停止/超时/断网不自动重试，不意味着回滚业务，需先核对结果。

## 功能边界

私有知识只用认证主体，最多100文档，每份10000字符；上传仅UTF-8 .txt/.md。更新需要完整新正文，不提供正文自动回填。引用来自实际API，片段见执行面板。HITL有效期来自服务端；撤销不能回滚已完成业务；同Action幂等重放不重复写。

Trace是128条/15分钟单进程快照，重启/worker切换可能404；不包含原始Prompt/完整State/摘要内容/凭据。Memory只展示真实模式/历史计数/摘要使用bool，不虚构M3命中。Experience面板为已提交合成离线历史，EXPERIENCE_BENEFIT=NOT_ESTABLISHED、人工语义NOT_ASSESSED，无Active开关。

## 浏览器验收

先按演示指南启动真实FastAPI/PG/Redis/Qdrant和受控LLM，再执行：

```bash
npx playwright install chromium --only-shell
S1WEB_CANCEL_ORDER=ORD95102 npm run test:e2e
```

单worker/重试0，真实Chromium，无API route mocks；认证文件仅从忽略私有目录读取，不开启含凭证的Trace/HAR。对已取消订单使用新的合成订单，不重置历史。详见[最终报告](../research/docs/agent_engineering_upgrade/s1_web_upgrade/S1-WEB_FINAL_REPORT.md)。
