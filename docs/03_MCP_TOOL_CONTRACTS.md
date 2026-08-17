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
