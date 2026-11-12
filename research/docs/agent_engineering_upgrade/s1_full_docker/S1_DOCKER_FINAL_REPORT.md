# S1-Docker 全栈部署验收

状态：工程验收通过，交付Push核验待完成。基线`3ba2271d0ce8a70bd2de07278ae274bb782d6659`，分支`codex/s1-full-docker`。仅Ubuntu；Windows Docker Desktop NOT_RUN。新增付费请求0；Experience Active关闭。真实容器、浏览器、SQL/向量存储与故障恢复均有证据；工程通过保留以下部署限制。

## 实现与范围

独立`compose.showcase.yml`和多阶段Dockerfile：Node24构建React，Python3.12运行FastAPI/LangGraph并提供静态页面。宿主运行只需Docker Engine/Compose，无需Python/Conda/Node。既有`python -m scripts.showcase`接口保留，共享合成seed函数；没有Agent、RAG或M2架构重构。

六服务：无网络bootstrap生成凭证；PG16/Redis7/Qdrant1.12.5健康；initialize在PostgreSQL事务和advisory lock内迁移及校验seed；API在初始化成功后启动。API非root、只读根文件系统、cap_drop ALL，仅loopback发布Web。依赖和初始化只用内部网络，API额外加入Web网络；运行进程的socket允许列表仅放行本机和已解析依赖地址。默认OfflineLLMProvider，付费与云Trace/MCP配置显式清空，镜像不包含.env或实验目录。

五个项目私有命名卷保存PG、Redis、Qdrant、DB密码、开发凭证。Token随机生成、目录0700/文件0600、API只读挂载，PG只读另一密码卷。30天过期后拒绝使用；不静默替换旧凭证。初始8条合成订单和商品；已取消状态保留，内容冲突拒绝覆盖。无数据卷删除或历史实验重跑。

## 已验证证据

| 检查 | 当前结果 | 证据 |
|---|---|---|
| D1多阶段镜像/非root只读离线冒烟 | PASS | `evidence/d1_build_VERIFIED.json` |
| Compose/初始化安全单元测试 | 14 PASS | `evidence/d2_network_GREEN.xml` |
| 首次真实启动、认证、迁移、8订单 | PASS | `evidence/d2_startup_v2/verification.json` |
| 两并发初始化/数据凭证不变 | PASS | 同上 |
| 真实浏览器及持久化 | 7PASS；三轮恢复PASS | `evidence/d3_real_01/acceptance.json` |
| 首轮全量后端 | 964 PASS/1历史SKIP | `evidence/d4_full_VERIFIED.xml` |
| 最终配置全量后端 | 965 PASS/1历史SKIP/0FAIL | `evidence/d4_final_full_VERIFIED.xml`；190.86秒 |
| 前端 | 类型/构建/22测试PASS | `evidence/d4_frontend.json` |
| Ruff/格式/Mypy/pip | PASS；Mypy160源码 | `evidence/d4_static.json`；最终Ruff396文件 |
| 历史214案例 | 202PASS/12旧非PASS/0新增严格回归 | `evidence/d4_summary.json`及原始新run |
| 原宿主启动器 | 实际健康/认证/停止保留卷PASS | `evidence/d4_host_startup_VERIFIED.json`、`d4_host_stop_VERIFIED.json` |

新历史回归目录：`../p4_dependency_integration/runs/20261112_DOCKER4_legacy_01/`，不覆盖旧run。唯一SKIP来自旧P4-A公共user_id协议的冻结认证案例；当前Bearer主体、Owner隔离由后续真实集成和浏览器攻击反例独立覆盖，不把旧SKIP强行改PASS。

## RED与最小修复

1. 官方基础镜像下载和PyPI一次超时：记录中断/失败，官方校验缓存后同源码重试成功；未改宿主daemon或降低依赖要求。见`d1_initial_pull_INTERRUPTED.json`、`d1_dependency_download_RED.json`、`d1_base_image_prefetch.json`。
2. 当前Docker29.8 Snap/Ubuntu Core24的NNP选项导致解释器执行EPERM，未修改官方Python镜像同样复现。只移除可选`no-new-privileges`，保留默认AppArmor/seccomp和应用安全；此项加固没有获得，不能声称替代等效。见`d2_bootstrap_exec_RED.json`与独立review。
3. API仅加入internal网络时容器内部健康但实际发布端点为空、宿主连接拒绝。只给API增加Web桥接网络；依赖仍internal、Web仍loopback，应用egress guard保持。新增安全契约RED/GREEN。见`d2_host_port_RED.json`、`d2_network_RED.xml`、`d2_network_GREEN.xml`。

## 限制

- 本机可信演示，不是完整生产安全部署；NNP在实测Docker Snap环境不可用。默认AppArmor/seccomp不等于NNP。
- API加入Web桥接网络，出站限制依靠应用允许列表；依赖网络为internal。独立重建依赖而IP变化后，需要重启API重新解析；普通restart及整栈恢复另行实测。
- 开发凭证明文存于私有本地卷，Docker管理员可读；不提供生产登录、公开发证、凭证轮换或公网部署。到期用新的独立项目，保留旧卷。
- 默认Hash Embedding和lexical reranker仅展示业务链路，不冒充真实语义模型质量。真实DeepSeek引用历史阶段，S1-Docker新增请求0；Experience收益仍NOT_ESTABLISHED。
- Windows未实测；首次拉取/依赖下载受网络影响；当前依赖范围与基础镜像tag并非永久锁文件，证据记录实际版本/镜像。

部署操作见[DOCKER_DEPLOYMENT_GUIDE.md](DOCKER_DEPLOYMENT_GUIDE.md)，恢复与下一步见[RECOVERY.md](RECOVERY.md)。最终Push/精确HEAD另见交付元数据；当前尚未预先标记远程成功。

## 干净源码部署与恢复事实

实测源码`fb6a1c3480a45e114badf5624c32ab59e0713d63`，新项目`adg_s1docker_20261112_02`、loopback35691；原目录首次部署项目为`adg_s1docker_20261112_01`、60509。两者均使用同一Compose定义和`up -d --build`；项目名/端口仅为验收隔离变量。没有新Git Worktree。

Git archive不含.env/.git/.venv/node_modules。独立冷缓存下载在jieba阶段超过8分钟无输出，已中断并保留原始日志/哈希，**不判冷缓存安装PASS**。随后只将归档文件权限统一到本机checkout，源码字节未变，复用D1已实际构建的Docker层；干净源码热缓存构建和全栈启动PASS。镜像内219个应用/评估/知识/迁移与打包文件逐一哈希匹配归档，实际71包版本与镜像ID见`evidence/d5_image_versions.json`。README后续仅文档变化不冒充重建新的应用版本。

真实Chromium7项包括Memory/Tools/HTTP-SSE、私有知识CRUD/引用/跨用户拒绝、取消订单与幂等重放、撤销提案与隔离、Experience只读/响应式、网络中断取消、刷新后Owner历史恢复。ORD95102终态cancelled且cancel_order审计1条；ORD95104撤销后仍paid。模型受控Offline，无API路由Mock。

API重启、三依赖重启、stop/start后再up，均验证相同凭证哈希、13张SQL表计数/订单/审计不变，私有文档和会话历史可读，另一主体读取/删除404。补充直接Qdrant scroll绕过Redis缓存，确认同Owner文档点仍在；Redis AOF启用且写状态ok，见`evidence/d5_direct_storage_VERIFIED.json`。

## 保全与收尾

独立审计6,453公开文件（含477新增）和6,749可达Git blob，对照24项实际私有凭据候选，0匹配；历史5,932原文件和4,443保全库存无意外变更；EX SQLite及旧候选经验导出哈希一致，详见`evidence/d5_final_preservation_secret_review.json`。`.env`未被本任务编辑、未跟踪且Git状态不变；因为没有任务前字节哈希，其历史字节同一性为NOT_ASSESSED，不能强行判PASS。

两套本阶段Compose共12容器已按项目/源码/端口标签核验后停止，10卷保留；宿主回归3容器也已停止、3卷保留，共13卷。未执行prune、down-v或删除旧资源；无关MySQL仍运行，见`evidence/d5_owned_stop_VERIFIED.json`。

```text
PHASE = S1-Docker
DOCKER_BUILD = PASS_CLEAN_SOURCE_WARM_CACHE
COMPOSE_ONE_COMMAND_START = PASS
DATABASE_MIGRATION = PASS
DEMO_DATA_INITIALIZATION = PASS_IDEMPOTENT
FRONTEND_BACKEND_ACCESS = PASS
DEMO_SCENARIOS = 3/3_PASS
CONTAINER_RESTART_PERSISTENCE = PASS
BROWSER_E2E = 7_PASS_0_FAIL
PYTEST = 965_PASS_1_HISTORICAL_SKIP_0_FAIL
RUFF = PASS_396_FILES
MYPY = PASS_160_SOURCE_FILES
HISTORICAL_REGRESSION = 214_CASES_0_NEW_STRICT_REGRESSIONS
UBUNTU_VERIFICATION = PASS_WITH_DOCUMENTED_LIMITATIONS
WINDOWS_VERIFICATION = NOT_RUN
PHASE_STATUS = ENGINEERING_VERIFIED_AWAITING_PUSH
UNRESOLVED_ISSUES = NNP_UNAVAILABLE;COLD_DOWNLOAD_INTERRUPTED;DEPENDENCY_NEW_IP_REQUIRES_API_RESTART;DEV_ONLY_CREDENTIALS
LAST_COMMIT = SEE_DELIVERY_METADATA_AND_GIT
GITHUB_PUSH_STATUS = PENDING
RECOVERY_READY = YES
EXPERIENCE_ACTIVE_ENABLED = NO
```
