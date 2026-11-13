# Docker 正式环境升级与 Agent 验收

日期：2026-11-14（台北时间）。正式入口已统一为 **http://127.0.0.1:8000**。Offline Agent 的实际端到端验收通过；Real Agent Dev 的配置和预算门禁通过。**真实 DeepSeek 验收为 `REAL_LLM_NOT_RUN`，不能据此宣称真实模型质量已通过。**

| 环境 | 更新前 | 更新后 |
| --- | --- | --- |
| 正式 API / React | 8000，镜像 `e2a216e7fd9d` | 8000，镜像 `65a5e165eda8`；四项容器健康 |
| 修复版测试项目 | 18083，镜像 `ae5c8f466b27`，四项运行、两项初始化容器已退出 | 核对无客户端、无活动数据库操作、无其他 Agent 使用后，六个测试容器已停止并移除；五个卷全部保留 |
| P4B 验证项目 | 三个容器已停止 | 隔离回归期间复用，测试结束后全部停止，三个卷保留 |

代码包含修复交付 `287a886` 和本地最终记录 `be2931f`，复用原工作树与独立分支 `codex/docker-production-acceptance`，未创建 Worktree。只通过 Compose `--no-deps --no-build api` 替换正式 API；PostgreSQL、Redis、Qdrant 的容器 ID、镜像和数据挂载保持不变。迁移版本已是 `0004`，未重跑 bootstrap、initialize 或 Seed。

实际验收结果：

| 检查 | 结果 |
| --- | --- |
| 8000 HTTP/SSE、订单 ORD95101 | PASS；SQL 和工具返回状态、6800 分金额一致，回答为 68 元 |
| 多轮 Memory / 会话恢复 | PASS；M2、同一 session、商品工具结果和 Trace 对应 |
| 私有政策 RAG / 引用 | PASS；本轮独立政策实际上传、检索、引用，测试后仅清理本轮政策 |
| HITL / 幂等 | PASS；确认前订单不变，确认后真实取消，同 Action 重放不重复写审计或业务数据 |
| Bearer / Owner / 身份隔离 | PASS；无凭证 401，伪造主体 403，跨主体历史/Trace/操作 404，订单与私有政策不泄露 |
| 无订单、无政策、依赖故障 | PASS；正式环境缺资料明确兜底；三项实际依赖故障在隔离 P4B HTTP 服务验证，不中断正式依赖 |
| 真实 Chromium | 7/7 PASS，无接口 Mock；含 HTTP/SSE、KB、确认/撤销/幂等、历史、身份切换、手机布局 |
| 前端测试 / 类型 / 构建 | 22 PASS / PASS / PASS |
| 完整后端 pytest | 1023 PASS，0 FAIL，1 历史 SKIP；另有 5 项新增回滚故障注入测试 PASS |
| 历史 214 场景 | 202 PASS，12 项既有非 PASS 保留，0 新增回归；原 Gold 和结果未改 |
| Real Dev / MockTransport 预算 | 72 PASS；密钥加载、同一 DeepSeekProvider/Graph 注入、请求/Token/费用门禁、失败恢复与持久账本 |
| Ruff / Mypy / 依赖 | 最终全项目 Ruff PASS，Mypy 162 源文件 PASS，pip check PASS；本轮脚本格式检查 PASS |

Experience Shadow 前端导航及页面已消失。后台 Experience 全部保留，运行配置为 OFF，Active 未开启。原 Bearer、Owner、HITL、幂等和 Redis fail-closed 安全机制保持。本轮未修改应用、前端或数据库迁移源码，只增加部署、验收脚本和证据。独立审查发现的部署脚本回滚异常缺口已 RED→GREEN 修复并复审关闭；未因此再次替换正式容器。

数据保护：升级瞬间 PostgreSQL 所有表数据指纹完全一致；测试结束后再用私有备份逐行核对，所有旧记录保留。明确允许的测试变动是合成订单 `ORD95102`、`ORD95107` 从 paid 变为 cancelled，以及测试政策操作导致 `web_demo_a` 的知识库 generation 递增。没有恢复或覆盖这些真实测试结果。6239 个受保护文件、`.env`、后台 Experience、历史实验和 Stash 均未改变；凭证/密钥扫描无匹配。全部 **13 个卷** 保留（正式 5、18083 测试 5、P4B 3）。最终长期运行 **4 个容器**，Real Dev 没有额外运行容器。

真实 DeepSeek：没有操作者批准的有限付费预算，因此未读取密钥去发起请求，实际请求 **0**、Token **0**、估算消费 **0**。自然语言理解、真实工具选择、模型 RAG 质量、真实延迟与成功率均 **未测**。MockTransport 结果不能替代这一项。以后启用须按 [现有 Real Dev 文档](../../../../docs/real-agent-dev.md) 配置私有密钥、明确请求/Token/费用及单价上界，在独立 8001 环境运行；本轮不自动启动。

在 WSL 中日常恢复已有正式容器（不重建、不重新初始化）：

```bash
cd /mnt/d/Code/Adaptive-rag/.worktrees/p3-experience-validation
sudo systemctl start docker
sudo docker compose --env-file /dev/null -p adaptive-rag-showcase \
  -f compose.showcase.yml \
  -f research/docs/agent_engineering_upgrade/docker_production_acceptance/compose.production.yml \
  start postgres redis qdrant api
```

8000 使用原正式环境凭证，与此前 18083 隔离。在本地 WSL 读取后粘贴到“本地开发凭证”，不加 `Bearer ` 前缀，点击“验证并进入”；不要发送到聊天或提交 Git：

```bash
sudo docker exec adaptive-rag-showcase-api-1 python -c "from app.demo.docker import read_credentials; print(read_credentials()['tokens']['a'])"
```

回滚仅替换 API，不操作数据库：旧镜像 `sha256:e2a216e7fd9d87612ec6039518e56ae7eca8997cc4b3d1c7ed83d58f5f353ca0` 已保留标签 `adaptive-rag-production:rollback-20261113`。原 API inspect、0600 PostgreSQL 备份及回滚覆盖文件位于 WSL `/root/.local/state/adaptive-rag-production-20261113/`，目录权限 0700。必要时从仓库根执行：

```bash
sudo docker compose --env-file /dev/null -p adaptive-rag-showcase \
  -f compose.showcase.yml \
  -f /root/.local/state/adaptive-rag-production-20261113/rollback.json \
  up -d --no-deps --no-build api
```

回滚后核对旧镜像 ID 与健康状态；未执行备份恢复演练，也未对现有数据库做恢复。原 Git 文件系统错误 1392 未修复，提交使用校验过的进程级对象缓存并只追加校验 pack；未 reset、清理损坏目录或 force-push。普通 Push 与远端 HEAD 核验结果见本目录 `delivery.json` 和 `progress.txt`。本轮新增的隔离回归原始运行目录本地保留；未混入旧实验提交。

证据：[容器基线](evidence/before-containers.json)、[升级保护](evidence/after-upgrade.json)、[实际 HTTP](evidence/offline-http-acceptance.json)、[Chromium](evidence/browser.json)、[回归](evidence/regression.json)、[最终静态检查](evidence/final-static.json)、[旧记录逐行保留](evidence/final-data-verification.json)、[文件与秘密保护](evidence/final-privacy.json)、[容器清理与卷清单](evidence/cleanup.json)。
