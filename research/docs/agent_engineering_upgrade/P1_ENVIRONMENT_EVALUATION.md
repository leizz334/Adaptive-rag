# P1-D Environment / Goal Evaluation

`eval/environment.py:BusinessEnvironment` 不接收DSN或业务Settings参数；创建固定SQLite `:memory:`，APP_ENV=testing、空模型密钥、禁远程Redis/Qdrant/MCP/本地模型加载。每个实例重新seed合成订单，退出dispose。服务路径仍为真实ChatService → LangGraph → Planner/Executor → Tool → Repository → commit；不是另写一套“会成功”的业务模拟器。

独立Session快照覆盖全部orders字段、items、products、refunds、returns、audit；只比较已提交状态，不取回答中的“成功”。`score_goal(initial, actual, expectation, calls)` 不接受答案输入。

每个场景需定义Initial State（重置fixture快照）、User Goal、Expected State、Allowed Actions（TrajectorySpec）、Forbidden Mutations（默认所有未明确允许的订单以及商品/行项目）、Actual State和失败原因。EnvironmentExpectation允许指定订单状态、仅状态可变的订单集合、最终申请数/新增审计动作及读操作观察。read observation必须来自成功工具的真实output，含精确订单/状态等约束；只有DB未变而没有实际读证据不能满足查询目标。

硬约束：未允许订单不得变化；不得新增/删除订单；即使允许变更status，其owner、金额等字段仍不得变化；products/items不得变；申请数与audit动作/目标需一致。最终任务成功还必须与工具参数/轨迹、安全/审批结果共同成立，不能只看environment_state_correct。

实际集成覆盖：订单状态查询与缺工具证据、取消提案不写库、确认后取消、重复确认仅重放且audit一次、他人订单不能写、跨用户Session拒绝、伪造确认拒绝、确认文字改对象仍使用原审批参数、commit失败回滚、禁止其他订单或owner变更、回答宣称成功但DB未变的负例。

为满足隔离场景，修复 `SessionRepository.get_or_create` 在已有Session时未核验user_id的缺口。该检查在加载历史前执行，阻止另一个给定身份读取/追加该Session；没有改历史窗口、摘要或实现任何P2 Memory。**HTTP user_id仍由客户端填写，生产认证缺口保留，不能将fixture身份隔离等同可信登录。**

运行命令：

```powershell
conda run --no-capture-output -n adaptive-rag python -B -m pytest -q -p no:cacheprovider --basetemp=research/docs/agent_engineering_upgrade/evidence/.tmp/d-full --junitxml=research/docs/agent_engineering_upgrade/evidence/P1-D-pytest.xml
```

验收以JUnit为准。本次全部写入仅合成内存DB，没有读取/操作生产库。未验证PostgreSQL并发、跨进程审批、远程幂等、退款完整资格状态机；这些P0风险未被本阶段测试覆盖自动消除。
