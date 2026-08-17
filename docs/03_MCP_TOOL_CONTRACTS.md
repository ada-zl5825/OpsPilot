# MCP 工具契约

目录源：`mcp_servers/contracts.py`。

## 权限

| 分类 | 谁可以调用 | 例子 |
|---|---|---|
| Read | Agent | `query_service_metrics`, `search_runbooks` |
| Propose | Agent | `propose_rollback_deployment` |
| Mutate | 仅 Control Plane | `execute_approved_proposal`, `rollback_execution` |

## 硬性字段

每个工具：`timeout_seconds`、`max_result_bytes`、结构化错误、合同测试、Azure schema 兼容性。

默认不提供任意 PromQL / Shell。高级只读查询若存在，必须有长度与时间范围限制。

## Phase 2 已实现（只读）

| Server | Tools | 端口 |
|---|---|---|
| observability | `query_service_metrics`, `query_service_logs`, `get_trace_summary` | 8001 |
| deployments | `get_recent_deployments`, `compare_deployments`, `get_ci_failure_summary` | 8002 |
| runbooks | `search_runbooks` | 8003 |

共同约束：

- 严格 typed input（枚举 / 范围 / 长度），`additionalProperties: false`
- 强制 ISO-8601 时间范围（最短 60s，最长 6h）和 `limit`
- 服务器端过滤；禁止 Agent 传入 PromQL / LogQL / Shell
- 超时、`max_result_bytes`、超量结果截断并 spill 到 `artifact://`
- 结构化错误：`tool`、`safe_params`、`time_range`、`error_type`、`retryable`、`suggested_fix`
- Azure OpenAI schema gate：单个坏工具隔离，不丢整个 catalog
- Runbook 结果标记为 untrusted，不能覆盖审批或写权限

实现：`mcp_servers/observability|deployments|runbooks`。测试：`tests/unit/test_*_tools.py`、`tests/contract/test_phase2_*.py`、`tests/contract/test_azure_schema_suite.py`。
