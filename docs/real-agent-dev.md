# Offline 与 Real Agent Dev

默认 `compose.showcase.yml` 继续使用 Offline：模型 Key 显式清空、出网门禁保留，调用现有 LangGraph、Memory、RAG、Tools 和 HITL。Offline 只提供有限规则/工具与有引用的原文节选，不是完整自然语言模型。私有知识库只检索当前认证用户上传的资料，不会自动导入仓库 `knowledge/`。

Real Agent Dev 复用相同应用工厂、路由、容器装配与 Agent 图，仅通过独立服务端入口显式启用。前端没有模式或付费开关，也不接收 DeepSeek Key。缺 Key、未显式启用、缺预算、账本异常或后端依赖不可用均安全拒绝，不回退为 Offline。

## Offline 启动

在已配置 Docker 的 WSL Ubuntu 内，进入当前仓库 worktree：

```bash
sudo docker compose -f compose.showcase.yml up -d --build
```

默认仅发布 `127.0.0.1:8000`，数据库均保留内部网络。既有身份凭证、Owner、HITL、幂等和 Redis 限流保持原路径；Experience Active 关闭。

## Real Agent Dev 配置

本入口支持 Linux Docker/WSL；预算卷需要真实 Linux 权限语义，不使用 Windows NTFS 目录作为预算绑定挂载。运行前保留 WSL 会话，检查 Docker 已启动。

1. 在仓库之外准备 Key 文件，例如 `$HOME/.config/adaptive-rag/real-agent-dev/deepseek.key`。目录权限 0700、文件权限 0600，使用本地编辑器填写，不将 Key 写入命令历史、YAML、Git 或前端。不要覆盖已有 `.env`。
2. 设置下列服务端环境变量。下面的有限额度仅为示例；输入/输出价格上界必须按计划使用的模型和官方现行价格明确填写，没有默认无限额或隐含单价。

| 变量 | 含义/示例 |
| --- | --- |
| `REAL_AGENT_KEY_FILE` | 上述私有 Key 文件的绝对路径；不是 Key 内容 |
| `REAL_AGENT_MAX_REQUESTS` | HTTP 尝试总上限，例如 `20`，重试也计数 |
| `REAL_AGENT_MAX_TOKENS` | 聚合保守 Token 预留上限，例如 `200000` |
| `REAL_AGENT_MAX_USD` | 按配置单价估计的费用预留上限，例如 `1` |
| `REAL_AGENT_INPUT_USD_PER_MILLION` | 正数、有限的输入价格上界，USD/百万 Token，必须填写 |
| `REAL_AGENT_OUTPUT_USD_PER_MILLION` | 正数、有限的输出价格上界，USD/百万 Token，必须填写 |
| `REAL_AGENT_MODEL` | 可选，默认 `deepseek-flash`；须和官方现行单价对应 |
| `REAL_AGENT_THINKING_MODE` | 默认 `disabled`，显式非思考模式适配现有短 JSON 分类、规划及回答；可明确设为 `enabled`，仍受同一输出和消费上限保护 |
| `REAL_AGENT_PORT` | 可选，默认 `8001`；须未被占用 |

Key 通过 Compose secret 挂载进容器，YAML 只保存文件引用。裸 Python 服务端入口也可读取 `DEEPSEEK_API_KEY` 或 `DEEPSEEK_API_KEY_FILE`，两者只能选一个。服务端显式要求 `REAL_AGENT_DEV_ENABLED=true`；独立 Compose overlay 会设置该标志，同时固定 `EXPERIENCE_MEMORY_MODE=off`、必需认证、私有 RAG 和 M2 Memory。

仓库 `.env` 中的 Key 不会切换 Offline。Compose 的变量插值和容器环境注入是两件事；Real Dev 仍须显式提供上述 secret 文件路径、模型和预算。不要把 `.env` 整体挂进容器，也不要把 Key 放入命令参数或前端。Real Dev 每次 Provider 调用最多尝试一次；出现错误先检查证据，不自动消耗剩余额度重试。

一次 Agent 用户请求可能包含分类、规划、生成、Faithfulness、改写等多次模型 HTTP 尝试，持久账本按每次尝试计数。保守 Token 预留包含完整 UTF-8 请求、协议边界余量和最大输出，可能明显高于供应商实际 usage；余额不足时会在发送下一次 HTTP 前拒绝，不应删账本或关闭安全节点来让小预算测试通过。

端点使用默认官方根地址或 `/v1`。其他路径目前会被运行时传输门禁拒绝；`validate` 的基础 URL 检查尚未和此路径限制完全统一，因此不能仅凭 `validate` 的结果判断自定义路径可用。实际付费连通性、代理必需的网络路径和供应商自然语言质量本轮均未测试。

## 配置检查与独立启动

下面的命令会继承明确列出的变量，不需要将 Key 内容传入命令行。应先在当前 shell 设置上述变量；不会修改宿主 `.env`。Compose 需支持 `!override`（当前验收版本 5.7.1）。

```bash
sudo --preserve-env=REAL_AGENT_KEY_FILE,REAL_AGENT_MAX_REQUESTS,REAL_AGENT_MAX_TOKENS,REAL_AGENT_MAX_USD,REAL_AGENT_INPUT_USD_PER_MILLION,REAL_AGENT_OUTPUT_USD_PER_MILLION,REAL_AGENT_MODEL,REAL_AGENT_PORT \
  docker compose -f compose.showcase.yml -f compose.agent-dev.yml config --quiet
```

只有决定允许后续模型消费时才执行启动：

```bash
sudo --preserve-env=REAL_AGENT_KEY_FILE,REAL_AGENT_MAX_REQUESTS,REAL_AGENT_MAX_TOKENS,REAL_AGENT_MAX_USD,REAL_AGENT_INPUT_USD_PER_MILLION,REAL_AGENT_OUTPUT_USD_PER_MILLION,REAL_AGENT_MODEL,REAL_AGENT_PORT \
  docker compose -f compose.showcase.yml -f compose.agent-dev.yml up -d --build
```

其项目名为 `adaptive-rag-real-agent-dev`，默认只发布 `127.0.0.1:8001`，与 Offline 的网络、数据库、开发凭证和数据卷全部分离。Overlay 用单一端口覆盖，不能同时继承 Offline 的 8000 发布。不要手动指定与 Offline 相同的 `-p` 项目名；那会使资源失去隔离。

首次 bootstrap 为预算卷准备私有目录，原有 initialize 在本项目中完成数据库初始化；API 通过同一 `build_container` 使用受预算传输保护的 `DeepSeekProvider`。健康检查仅读取 readiness、capabilities 和本项目身份，不发送 chat completion。

## 预算行为和边界

- 每次真正 HTTP 尝试之前，SQLite 事务原子预留一次请求、完整 UTF-8 请求和最大输出 Token 的保守上界，以及按配置单价的费用上界；正常 JSON、流式和重试都经过同一门禁。
- 账本位于本项目独立 `real_budget` 命名卷的 `/var/lib/real-agent/budget.sqlite3`，只保存计数、预留与状态，不保存问题、回答、Header 或 Key。重启保留计数；更改单价、模型或上限不能静默重置旧账本。
- 不确定、取消、中断或崩溃留下的 pending/uncertain 尝试保留预留，阻止后续自动消费。先人工核对供应商与账本；不要删除卷、改状态或重放来绕过门禁。需要新的消费额度或恢复方案时另行明确授权。
- 费用是按操作者提供的保守价格上界估算，不是供应商结算账单。单价和模型要由操作者按官方现行规则维护；本轮没有使用真实 Key 或验证真实供应商费用。
- 保留原上下文 Token 限制、每主体 Redis fail-closed 限流；Real Dev 默认每分钟 60 次入口配额，真实模型预算另行累计。没有将普通用户加入 docker 组，没有削弱认证或写操作确认。

本轮只执行假 Key、MockTransport、配置解析和启动门禁测试，真实付费请求数为 0。Real Agent 的实际自然语言质量与付费链路连通性尚未验收；前端改动应先在独立 Offline 验证项目完成浏览器回归。
