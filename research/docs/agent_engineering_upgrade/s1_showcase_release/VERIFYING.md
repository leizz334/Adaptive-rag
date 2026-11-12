# 验证命令与隔离边界

已完成结果见r5_checks/r5_browser/JUnit，不必自动重跑。确需重现时用全新验证run，禁止指向演示、用户或生产数据库。固定Ubuntu工作目录、既有`.venv`，安装依赖见README。不要重复已有run-id或覆盖结果。

## 前端与真实浏览器

```bash
npm test --prefix frontend
npm run typecheck --prefix frontend
npm run build --prefix frontend
# 首次安装到用户缓存：
cd frontend
npx playwright install chromium --only-shell
cd ..
```

根据STARTUP新建并serve演示run，再执行：

```bash
.venv/bin/python -m scripts.showcase browser --run-id my_fresh_demo --cancel-order ORD95102
```

真实Chromium单worker、重试0，当前7场景；没有route mock，包含真实断网与CDP网络延迟下的历史读取取消。它会取消一个合成订单，并非无副作用检查；已取消订单不得重置，使用另一个尚未取消的种子或新run。

## 全量后端与历史回归

选择新run-id，不能和演示共用验证数据库：

```bash
export RELEASE_CHECK_RUN=release_check_fresh01
.venv/bin/python -m scripts.showcase init --run-id "$RELEASE_CHECK_RUN"
export P4B_RUN_LIVE=1
export P4B_MANIFEST="$PWD/research/docs/agent_engineering_upgrade/p4_dependency_integration/.private/p4b_showcase_${RELEASE_CHECK_RUN}/manifest.json"
export P4_E2E_RUN_ID="${RELEASE_CHECK_RUN}_http"
export P4B_AUTH_RUN_ID="${RELEASE_CHECK_RUN}_auth"
export P4B_API_RUN_ID="${RELEASE_CHECK_RUN}_api"
.venv/bin/python -m research.docs.agent_engineering_upgrade.p4_final_acceptance.offline pytest tests research/docs/agent_engineering_upgrade -q
.venv/bin/python -m research.docs.agent_engineering_upgrade.p4_final_acceptance.offline research.docs.agent_engineering_upgrade.p4_dependency_integration.regress "${RELEASE_CHECK_RUN}_legacy"
.venv/bin/ruff check app tests eval alembic research scripts/showcase.py
.venv/bin/ruff format --check app tests eval alembic research scripts/showcase.py
.venv/bin/mypy
.venv/bin/python -m pip check
.venv/bin/python -m scripts.showcase stop --run-id "$RELEASE_CHECK_RUN"
```

init已在新空库做迁移回环并保留marker。全量fixture发现marker会跳过已完成回环，不重置业务数据。测试会重启/故障注入**本验证项目**的服务，所有Docker动作继续经过原sandbox标签/清单检查；其他服务不属于作用域。offline wrapper清除付费key并禁止外部socket，控制模型只用合成数据。

历史214案例含12个既有非PASS，不把它们改成PASS。真实模型旧C/D/EX实验不在这些命令里重跑，Gold与原始分数不修改。原始试验日志/私有凭据不提交，公开证据只记录安全摘要和合成业务。

CLI/README关键命令的本阶段实测：新init、serve、status、stop、start/serve、browser、隔离pip/npm安装、types/build、全量与静态检查。Git clone的目标发布分支在最终Push后可用；清洁源码安装使用git archive验证，未额外创建开发Worktree。
