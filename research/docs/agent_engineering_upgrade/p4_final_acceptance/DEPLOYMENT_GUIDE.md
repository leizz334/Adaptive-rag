# Ubuntu 部署与复现

本流程验证的是单机 Ubuntu、主机 `.venv` 运行 FastAPI、Docker Compose 运行 PostgreSQL/Redis/Qdrant 的隔离演示。真实业务仅合成数据；共享知识库只能放公共、非敏感文档。**私有多租户知识库应用层 ACL 未实现，禁止按该用途部署。** 本阶段没有认证生产就绪；TLS、备份恢复、密钥轮换、外部限流和新主机从零安装仍需另行验证。

## 1. 新克隆与 Python

```bash
git clone https://github.com/leizz334/Adaptive-rag.git
cd Adaptive-rag
git switch codex/p4-final-acceptance
python3 --version
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
docker version
docker compose version
```

Python要求>=3.11；本次实测Python3.12。依赖定义以 `pyproject.toml` 为准；`constraints-ubuntu-observed.txt` 和 `evidence/environment_packages.json` 记录实际验收环境，不是跨平台锁文件。新机器操作系统包安装需遵循当地管理员流程；无需Windows Conda。当前机器直接复用 `.venv`，不要重新创建或覆盖它。不要复制别人的 `.env`。

如需复现D阶段真实本地神经检索，先安装官方CPU torch，再使用rerank extra与观察约束：

```bash
.venv/bin/python -m pip install 'torch==2.6.0+cpu' --index-url https://download.pytorch.org/whl/cpu
.venv/bin/python -m pip install -e '.[dev,rerank]' -c research/docs/agent_engineering_upgrade/p4_final_acceptance/constraints-ubuntu-observed.txt
```

权重必须按D的 `evidence/model_download.json` 中revision/SHA获取并验证；本次不重新下载或计费运行D。演示profile显式禁用神经模型，`/capabilities` 会报告实际降级；Hash/lexical仅用于受控测试，不能作为真实Dense/Reranker性能。

## 2. 新隔离依赖项目

项目名须唯一且符合 `p4b_[a-z0-9_]{3,40}`；以下示例名若已存在，选择新名字，不删除旧目录/卷。`prepare` 使用exist_ok=False，拒绝覆盖。

```bash
.venv/bin/python -m research.docs.agent_engineering_upgrade.p4_dependency_integration.sandbox prepare --project p4b_new_demo_01
export P4B_RUN_LIVE=1
export P4B_MANIFEST="$PWD/research/docs/agent_engineering_upgrade/p4_dependency_integration/.private/p4b_new_demo_01/manifest.json"
.venv/bin/python -m research.docs.agent_engineering_upgrade.p4_dependency_integration.sandbox up
.venv/bin/python -m research.docs.agent_engineering_upgrade.p4_dependency_integration.sandbox ps
.venv/bin/python -m research.docs.agent_engineering_upgrade.p4_final_acceptance.offline research.docs.agent_engineering_upgrade.p4_dependency_integration.migrate
```

私有manifest和Compose env为0600权限、生成随机凭据、动态回环端口，只接触带正确owner标签的本地Docker资源。源码Compose保持原有PostgreSQL16/Redis7/Qdrant1.12.5；当前实测镜像digest在 `evidence/e2_runtime_images.json`。标签可能漂移；另一台主机需要核验digest。`--roundtrip`只可对新合成数据库用于测试，**不要对已有业务库执行降级迁移**。Root `docker-compose.yml` 是旧的SQLite示例，不是本次真实三依赖验收入口。

## 3. 真实应用启动与认证

```bash
.venv/bin/python -m research.docs.agent_engineering_upgrade.p4_final_acceptance.deploy info
.venv/bin/python -m research.docs.agent_engineering_upgrade.p4_final_acceptance.deploy serve
```

`serve` 前台启动原始 `app.asgi:app`，不是测试替代路由。production错误封装、required Bearer认证、真实三依赖；绑定127.0.0.1。demo自动创建manifest旁0600 `p4e_api.private.json`，只含1天有效的合成用户凭据，不输出token。重复启动复用该文件；到期后认证会拒绝，勿修改历史验收凭据，应新建演示项目。不要将此文件提交Git。

本profile清空DeepSeek/Embedding/LangSmith Key、关闭Experience/MCP/神经模型/外部trace，显式INFO日志和仓库公共knowledge目录；使用项目OfflineLLMProvider，**无真实模型付费能力，不能代表真实业务语言质量**。它仍加载真实数据库、Redis及Qdrant。订单业务合成种子仅由测试fixture写入，普通serve不自动插入订单。

另一终端保留相同 `P4B_MANIFEST`，可执行以下脚本；token只在内存中用于请求，不写终端：

```bash
.venv/bin/python - <<'PY'
import json, os
from pathlib import Path
import httpx
m=Path(os.environ['P4B_MANIFEST'])
a=json.loads((m.parent/'p4e_api.private.json').read_text())
u=f"http://127.0.0.1:{a['port']}"
with httpx.Client(base_url=u, trust_env=False) as c:
    for route in ['health','ready','capabilities']:
        print(route, c.get('/api/v1/'+route).json())
    print('unauthorized', c.post('/api/v1/chat',json={'message':'你好'}).status_code)
    with c.stream('POST','/api/v1/chat/stream',json={'message':'你好'},headers={'authorization':'Bearer '+a['token']}) as r:
        print('SSE status',r.status_code)
        for line in r.iter_lines():
            if line.startswith('data:'): print(line)
PY
```

`/health`只是liveness；`/ready`仅数据库为硬依赖，须逐项检查Redis/Qdrant状态及 `/capabilities`，不能只看HTTP200。真实服务实测包含无认证401和授权SSE完成。停机用前台Ctrl-C；SIGTERM也会优雅关闭，Uvicorn可能返回-15，应结合shutdown complete日志判断。六项部署探针中的故障和恢复证据在E1/B3新runs。

## 4. 测试与可重复验收

完整测试覆盖单元、SQLite、真实三依赖、HTTP/SSE、工具和历史研究helper。必须设置私有 `P4B_MANIFEST`，每次选新run ID，禁止覆盖已完成实验：

```bash
export P4_E2E_RUN_ID=ubuntu_new_E_http_01
export P4B_AUTH_RUN_ID=ubuntu_new_E_auth_01
export P4B_API_RUN_ID=ubuntu_new_E_api_01
.venv/bin/python -m research.docs.agent_engineering_upgrade.p4_final_acceptance.offline pytest tests research/docs/agent_engineering_upgrade -q
.venv/bin/ruff check app tests eval alembic research/docs/agent_engineering_upgrade
.venv/bin/ruff format --check app tests eval alembic research/docs/agent_engineering_upgrade
.venv/bin/mypy
.venv/bin/pip check
.venv/bin/python -m research.docs.agent_engineering_upgrade.p4_final_acceptance.offline research.docs.agent_engineering_upgrade.p4_dependency_integration.regress ubuntu_new_E_legacy_01
```

offline wrapper在Python进程内清Key/代理并拒绝外部socket；现有HTTP子worker也单独禁止外网，不依靠prompt防止计费。完整pytest使用新合成数据库，请勿提供生产DSN。性能runner固定当前run ID且拒绝覆盖；新实验需同时新run ID与新输出路径，不能盲目再次执行已通过的48请求。历史付费C/D ledger不可重置或重跑。

## 5. 安全/恢复与生产边界

- Bearer存摘要与subject/roles/expiry/revocation；客户端user_id不得授权。生产凭据发放/轮换/撤销运营流程不是本demo提供的身份系统。
- 业务Owner/Session、HITL durable pending、幂等和审计在请求事务内；实测跨worker/restart并发确认和中断回滚通过。机器断电、跨机灾难恢复未验证。
- Qdrant/BM25/cache是共享公共知识库；SDK原生filter不等于应用层租户ACL。私有语料需完整ingest/query/cache授权设计后另行验收。
- Redis失效时限流fail-open；付费工作负载需要外围强制配额/断路保护。当前不能承诺故障时严格限流。
- 日志格式化参数/嵌套secret/异常DSN脱敏已RED→GREEN；任意无标签密文、第三方自有handler或任意外部trace仍不可保证。勿写生产secret/PII到知识库、prompt或错误字符串。
- 部署到公网前需要TLS入口、网络策略、依赖认证、备份恢复验证、密钥生命周期、负载/soak与供应链审计；本次未执行，状态NOT_ASSESSED。

停止依赖且保留所有卷：

```bash
.venv/bin/python -m research.docs.agent_engineering_upgrade.p4_dependency_integration.sandbox stop
```

禁止 `down -v`、prune、按端口或名称批量kill。恢复相同owned项目使用sandbox start/up后ps检查；失败时先读RECOVERY.md和证据，不自动重放写操作或付费实验。
