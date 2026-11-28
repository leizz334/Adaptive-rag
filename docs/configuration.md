# 配置与部署

从仓库根目录启动，应用以 `app/config/settings.py` 为配置入口。系统环境变量优先于 `.env`。默认的 `.env.example` 可无密钥、无模型权重启动。

| 功能 | 配置 | 本地默认 |
| --- | --- | --- |
| 对话模型 | `DEEPSEEK_API_KEY`、`DEEPSEEK_MODEL` | 离线演示；有密钥时默认 `deepseek-flash` |
| 规划 | `PLANNER_MODE=json` 或 `function_calling` | JSON |
| 持久化 | `DATABASE_URL` | 本地 SQLite 文件 |
| 缓存和限流 | `REDIS_URL` | 进程内 |
| 稠密检索 | `EMBEDDING_API_KEY` 和 `EMBEDDING_BASE_URL`，或 `LOCAL_EMBEDDING_ENABLED=true` | 示例配置使用 BM25 |
| 向量存储 | `QDRANT_URL`、`QDRANT_COLLECTION` | 进程内向量存储 |
| 精排 | `CROSS_ENCODER_ENABLED=true` | 词法精排 |
| 文档 | `KNOWLEDGE_DIR`、`UNSTRUCTURED_ENABLED` | 启动时载入 `knowledge/` 中的 Markdown |
| 管理接口 | `ADMIN_API_TOKEN` | 开发模式本地使用，生产模式需提供令牌 |

使用本地嵌入或 Cross-Encoder 前安装 `python -m pip install -e ".[rerank]"`。初次启用会下载模型。使用远程向量模型时，`EMBEDDING_DIM` 应与模型输出一致。启用 PDF 或 Office 解析需要 `.[docs]` 和相应的系统解析工具。使用 `/api/v1/capabilities` 检查实际运行的后端。

## Docker 单进程演示

```bash
docker compose up --build -d
docker compose exec api python -m scripts.seed_demo
docker compose ps
```

在 [工作台](http://127.0.0.1:8000/) 打开前端。Compose 在本机回环地址监听，SQLite 使用保留数据的命名卷。独立部署的前端需要同源反向代理或自行配置跨域策略。发布验收使用本机进程完成，Docker 镜像、外接 Qdrant 和多副本拓扑未实测。

## PostgreSQL 验证

本地 SQLite 的 Schema 由启动或种子脚本创建。在外部 PostgreSQL 上应先应用 [Alembic 迁移](../alembic/versions)，再启动或导入演示数据。

Ubuntu 24.04 或 WSL 上，可用脚本启动隔离的回环 PostgreSQL。脚本获取发行版的 PostgreSQL 16.15 软件包并检查其摘要。测试器先核对临时库的标识，再应用迁移并运行实际行锁、重叠会话、权限和事务测试。

```bash
sandbox=$(bash scripts/postgres-sandbox.sh start 16543)
python scripts/verify_postgres.py --ref HEAD --port 16543
bash scripts/postgres-sandbox.sh stop "$sandbox"
```

Windows 配合 WSL 使用时，在 WSL 执行启动和停止，在 Conda 所在系统执行 Python 验证器。普通 `pytest` 跳过需要该临时库的用例。

如需手工将迁移应用到现有 PostgreSQL，先对已正确配置 PostgreSQL 的 Alembic 连接执行 `alembic upgrade head`。仓库的 `alembic.ini` 默认指向 SQLite，连接独立 PostgreSQL 时使用自己的 Alembic 配置文件。启动应用时设置 `DATABASE_URL=postgresql+asyncpg://...`。

## 对外使用的边界

生产模式下管理接口需要配置令牌。普通聊天接口仍需在可信认证层绑定身份，确认票据也只在接收请求的应用进程中有效。仅示例数据可用于公开演示。Redis 和 Qdrant 是可选服务，缺失时可按配置运行本地降级。有限重规划通过 `REACT_ENABLED` 控制，默认关闭。
