# Observability MCP

Phase 2 read-only tools. Default interfaces are typed. Free-form PromQL is not exposed.

| Tool | Permission | Notes |
|---|---|---|
| `query_service_metrics` | read | Enum metric + aggregation, required time range and limit |
| `query_service_logs` | read | Server-side severity/contains filter; secrets redacted |
| `get_trace_summary` | read | Summaries only; require `service` or `trace_id` |

Every call enforces timeout, `max_result_bytes`, structured errors, and artifact spilling.

Backends: Prometheus / Loki / Tempo when `OPSPILOT_MCP_BACKEND=live`. Tests use deterministic fakes.
