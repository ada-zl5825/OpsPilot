---
name: mcp-toolset
description: Author MCP servers with strict schemas, output budgets, structured errors, and Azure-compatible contract tests. Use when adding or changing tools under mcp_servers/ or tool catalog contracts.
---

# MCP toolset

## Catalog

Source of truth: `mcp_servers/contracts.py`.

Agent-visible: Read and Propose only. Never register `execute_approved_proposal` or `rollback_execution` on Holmes.

## Tool requirements

Every tool must have:

- Single responsibility
- Strict Pydantic / JSON Schema (enums, ranges, max length)
- Server-side filtering
- Timeout and `max_result_bytes`
- Structured error: tool, safe params, time range, error type, retryable, suggested fix
- Permission: `read` | `propose` | `mutate`
- Deterministic fake for tests

## Defaults (Phase 2)

| Server | Tools |
|---|---|
| observability | `query_service_metrics`, `query_service_logs`, `get_trace_summary` |
| deployments | `get_recent_deployments`, `compare_deployments`, `get_ci_failure_summary` |
| runbooks | `search_runbooks` |

Do not ship free-form PromQL/LogQL/Shell as the default interface.

## Azure gate

Run `validate_tool_schema_for_azure` on every tool schema. Isolate a single bad tool; do not drop the whole catalog.

## Tests

- Unit: bounds, truncation, redaction, error shape
- Contract: Holmes can load schema, Azure accepts it, timeout/size enforced, permission class correct

## Out of scope

Write execution, UI, arbitrary shell.
