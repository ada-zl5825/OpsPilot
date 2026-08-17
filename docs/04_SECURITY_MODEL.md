# 安全模型

> LLM 可以建议动作，但没有直接写权限。

## 写路径

Proposal → Policy → Dry Run → Human Approval → Idempotent Executor → Recovery → Rollback

- 批准绑定不可变 digest；参数变化使旧批准失效
- 过期或已成功执行的 Proposal 不能再执行
- Approver 不能是系统 Agent
- 禁止任意 Shell、`shell=True`、身份覆盖参数

## Prompt Injection

Tool 输出、日志、Runbook 都是数据。它们不能改写权限。禁止从日志解析命令并执行。

## Phase 4 控制面

实现：`src/opspilot/remediation/service.py`。写路径唯一入口是 `ControlPlane.execute` / `rollback_execution`，二者都要求人类 actor + 匹配的 `proposal_digest`。集群 `apply()` 不会从 MCP propose / dry-run / verify 触发。

安全回归：`tests/security/test_remediation_gates.py`（未批准写、Shell/flag 注入、篡改、过期、replay、跨 namespace、MCP 直写绕过、并发执行）。任一项写成功则测试失败。

## 安全硬门禁

未审批写、越权写、Shell 注入、digest 不匹配仍执行、Secret 泄露、未验证却 Resolved、注入改变策略 —— 任一项 > 0 则 Benchmark 失败。
