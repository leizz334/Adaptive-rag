# Evaluation V2 指标契约

工具评分入口 `eval/tool_scoring.py:score_tools`，输入严格使用 `eval/contracts.py` 的真实ToolCall及独立TrajectorySpec，不接收答案字符串。原 `tool_path_hit` 不再评分，旧E2E报告保留该key为null；旧数据没有工具金标，selection明确null，不能将execution成功率冒充selection正确率。

## 工具指标

- Tool Selection Accuracy：必需工具多重集合的召回；无必需项时检查实际工具是否属于允许集合。必须与冗余调用/trajectory一起解读，不是任务成功率。
- Tool Argument Accuracy：工具级参数约束匹配率，并以必需调用参数的一对一覆盖率封顶。期望字段为约束子集；额外默认参数允许。数值可从数值字符串规范化，bool不当数字；订单/SKU字符串精确匹配。重复查A不能满足要求查A和B。
- Sequence / Constraint Validity：必需调用齐全、无多余调用、符合所有before条件及任一合法路径才为1。路径未提供时使用集合/顺序约束；等价路径不要求单一字符串序列。
- Unnecessary Tool Calls：允许集合外调用数 + 超过配置max_calls的次数（缺省每种最多max(1,必需次数)）。它不由回答关键词判断。
- Tool Execution Success：真正尝试执行（含参数校验）的成功数/尝试数；denied/replayed不入分母；无执行为null。正确工具但依赖失败仍可selection/argument正确，execution失败。
- Failure Classification：invalid_arguments、business_rejected、permission_denied、execution_error、tool_result_failure；额外汇总denied/replayed。它们不是自动反思标签，仍需任务级终态和根因证据。

原始事件只在显式 `capture_tools()` 作用域内收集，不默认存日志/Trace。Tool.run记录实际规范化参数及结果；Executor额外记录权限拒绝和幂等重放。独立并发捕获作用域不串数据；超过1024事件使评测失败，不能静默截断后报成功。

## 兼容与安全

原数据文件、检索P@K/Recall/MRR算术与历史MEASURED报告保持。旧E2E拒答accuracy修正为全部样本的预期/实际相等率，和历史“仅应拒答子集召回”不可直接比；新增schema_version明确标记。legacy live E2E需显式 `AGENT_EVAL_ALLOW_LIVE=true` 才启动，它仍不是隔离V2，也未在本次运行。不得以该开关推断已授权付费模型或生产DB。

P1-C测试覆盖正确/错误参数、错工具、漏工具、冗余调用、执行失败、等价路径、顺序约束、拒绝/重放语义及两目标防重复覆盖。实际Tool基类测试覆盖参数规范化、校验失败、依赖异常与并发证据隔离。原始参数与gold只在本地评测，不注入Prompt。

验收命令使用Conda adaptive-rag、`pytest -q -p no:cacheprovider --basetemp=research/docs/agent_engineering_upgrade/evidence/.tmp/c-final --junitxml=research/docs/agent_engineering_upgrade/evidence/P1-C-pytest.xml`；实际结果见JUnit。后续环境/Goal及五态Judge指标在D/E追加。
