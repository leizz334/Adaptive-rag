# DeepSeek 真实 Agent 有限验收

日期：2026-11-14（台北时间）。**DeepSeek 真实 API 已成功连通，完整的真实业务 Agent 验收尚未完成。** 本轮达到 Token 预留门禁后停止，没有追加额度或用 Mock 冒充业务通过。

## 原因与最小修复

8000 的 Offline Showcase 故意将 Key 清空，并通过 `runtime_settings(..., _env_file=None)` 忽略宿主 `.env`；填写 Key 不会改变 Offline 模式。Compose 的变量插值也不会自动把 `.env` 中的 Key 注入真实 Provider。因此此前显示 Offline，不足以证明 Key 或 DeepSeek API 不可用。

已确认指定 `.env` 中 Key 非空、模型为 `deepseek-flash`、端点为官方 HTTPS；未修改或输出 Key。使用已有 Real Agent Dev，将 Key 复制到 WSL 原生私有文件 `/home/panda/.adaptive-rag-live-20261114/deepseek.key`（0600，目录0700），由原 Compose secret 挂载。现有 Key 未写入 YAML、前端、日志或 Git。

为适配现行模型默认思考模式和项目短 JSON 输出上限，新增可选 `deepseek_thinking_mode`，Real Dev 显式使用 `disabled`；普通 Provider 未配置此项时保留既有请求格式。Real Dev 每个 Provider 调用仅尝试一次，避免失败时自动消费额度。未改 Graph、工具、Memory、Owner、HITL 或预算预留算法；Experience Active 保持关闭。

## 实际真实测试

真实入口在测试期间为 **http://127.0.0.1:8001**。实际使用 DeepSeekProvider 和真实 HTTPTransport，复用既有 LangGraph、PostgreSQL、Redis、私有知识库、M2 Memory、Tools 与 HITL。认证、capabilities、依赖健康与应用150个Python文件均核对通过，Windows浏览器主机的8000/8001 HTTP访问均验证成功。

| 项目 | 真实结果 | 模型 HTTP / Tokens / 延迟 |
| --- | --- | --- |
| 简单问候 | **PASS**；完整 Agent 返回自然语言，Trace 为 Intent→Router→Generate 三次模型调用 | 3 次；1207实际Tokens；3859ms |
| ORD95101 订单 Tool Calling | **BUDGET_BLOCKED**；SSE 返回明确预算错误，在 Intent 发送模型请求之前拒绝；订单工具未执行 | 新增0次、0Tokens；13ms |
| 同一订单多轮 Memory | **NOT_RUN**；订单前置场景未完成，剩余预留额度不足 | 0次；延迟不适用 |
| 合成政策的模型 RAG 引用与解释 | **NOT_RUN**；预留额度不足 | 0次；延迟不适用 |
| 不存在订单/缺失资料的真实模型降级 | **NOT_RUN**；预留额度不足 | 0次；延迟不适用 |

模型 HTTP 成功率为 **3/3（100%）**，不能等同于五个业务场景全部通过。三次分别由 Intent、Router、Generate 发起，并非重试；Trace 中实际 Tokens 分别为718、219、270。

另外完成了**不调用模型**的私有政策上传/检索和Owner隔离，以及真实问候历史持久化：A能检索本轮合成政策，B不能；A历史HTTP200并含实际问候回答，B访问HTTP404。这些只验证检索、隔离和持久化，不替代真实模型RAG或订单多轮验收。合成政策仅保留在本轮独立 Real Dev 数据中。

## 预算与计费证据

门禁在首次真实请求前通过 MockTransport 和持久化测试验证，并在已解析 Compose 配置及实际运行配置中再次断言模型、官方端点、单价和上限，防止宿主环境变量覆盖。

| 指标 | 实际记录 | 本轮上限 |
| --- | --- | --- |
| 模型 HTTP 尝试，含重试 | **3** | 6 |
| 供应商 usage 输入/输出/总Tokens | **1086 / 121 / 1207** | 与保守预留分开记录 |
| 持久账本累计保守预留Tokens | **8986**，剩余1014 | 10000 |
| 持久账本保守费用预留 | **USD0.0037866** | USD0.05 |
| 按实际 usage 计算的费用估算上界 | **USD0.000471** | USD0.05 |
| 账本状态 | **completed=3，pending=0，uncertain=0** | 不确定状态立即停止 |

采用[DeepSeek官方价格表](https://api-docs.deepseek.com/quick_start/pricing/)在2026-11-14列出的 `deepseek-flash` 峰时上界：输入USD0.30、输出USD1.20/百万Tokens；未使用收费搜索或供应商内置收费工具。估算按全部输入为缓存未命中计算，未声称核验供应商实际扣款账单。

原门禁按完整UTF-8请求、协议余量与最大输出进行保守预留，消费后不退回，因此8986预留明显大于1207实际usage。即使还剩3次HTTP次数，也不足以再预留一次Intent请求。本轮没有按实际usage重置余额，也没有关闭分类、Router或Faithfulness来制造通过。

账本在 `adaptive-rag-real-agent-dev_real_budget` 卷内的 `/var/lib/real-agent/budget.sqlite3`，权限0600。服务停止后通过无网络、只读挂载再次读取，记录仍为3/8986/USD0.0037866，证明停止没有清零账本。

## 回归、运行状态与后续使用

配置/Provider最小修复采用 **RED：5失败 → GREEN：77通过**；随后相关后端、安全、HTTP/SSE回归 **779通过、0失败**。最终Ruff、Mypy、改动文件格式检查均PASS。预算专项包含本轮精确6/10000/USD0.05上限、重启持久性及不确定消费阻断。独立审查发现的模型/端点覆盖检查、证据状态误分类及收尾失败路径均已修复。没有重新运行或覆盖历史Gold及旧实验结果。

测试结束后，**本轮Real Dev的6个容器均已停止**，保留6个新数据卷和预算账本；连同旧环境共有19个卷，未删除任何旧卷。8000原四个容器的ID、镜像及挂载保持不变，收尾验证健康且仍为Offline。`.env`哈希与本轮开始一致，Key无泄露匹配。

如需打开既有8001界面，可在**普通WSL Ubuntu终端**中执行下列命令；这只启动既有容器，不增加或重置预算。**当前剩余额度不足新的模型推理**，不能把重新启动视为重新获准消费：

```bash
cd /mnt/d/Code/Adaptive-rag/.worktrees/p3-experience-validation
sudo docker compose --env-file /home/panda/.adaptive-rag-live-20261114/compose.env \
  -p adaptive-rag-real-agent-dev \
  -f compose.showcase.yml -f compose.agent-dev.yml \
  -f /home/panda/.adaptive-rag-live-20261114/image.override.json \
  start postgres redis qdrant api
```

8001使用自己的Bearer凭证，与8000隔离。启动后只在本地终端读取，再粘贴到“本地开发凭证”，不要加`Bearer `前缀或发送到聊天：

```bash
sudo docker exec adaptive-rag-real-agent-dev-api-1 python -c "from app.demo.docker import read_credentials; print(read_credentials()['tokens']['a'])"
```

本次观察到临时WSL命令结束后实例会退出，导致Docker随后重启；真实调用因此在一个有限前台WSL过程内完成。收尾已观察到两个普通用户交互式WSL shell，并验证不执行WSL命令12秒后，Windows仍可访问8000且为Offline。未修改WSL全局配置，也未安装保活任务。后续维持8000运行应保留普通Ubuntu终端；结束全部使用时先停止容器，再执行`wsl --shutdown`。Windows本机直连DeepSeek的TLS探测未通过，容器/WSL直连及本轮真实模型请求已成功；未擅改Windows证书、代理或防火墙。

后续若要完成Tool Calling、订单Memory、模型RAG与异常业务验收，需要另行授权覆盖多节点调用的Token预留额度及明确的账本处理方案；不能删除、覆盖或换账本绕过本轮限制。本轮不再新增付费请求、不自动开启下一阶段。

证据：[配置基线](evidence/D1-baseline.json)、[零付费回归](evidence/D2-preflight.json)、[真实启动与零账本](evidence/D2-startup.json)、[真实问候与完整Trace](evidence/D3-greeting.json)、[订单预算拒绝与SSE](evidence/D3-tool-order.json)、[汇总](evidence/D3-summary.json)、[停止后的账本与资源保护](evidence/D4-final-runtime.json)。提交及普通Push结果见`delivery.json`、`progress.txt`与Git历史。
