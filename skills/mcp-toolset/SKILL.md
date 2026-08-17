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

Do not advertise `anyOf` / `null` on optional strings. Azure rejects that schema, but gpt-4o still sends JSON `null` for unused optionals. Coerce at runtime with `drop_null_arguments` / `create_mcp()`; add a contract test that calls the tool with `path=null` (or equivalent) and still passes the Azure schema suite. See `docs/09_LIVE_AZURE_INVESTIGATION_FIX.md`.

If an optional path filter matches no series, retry without path and set `path_ignored`. Empty successful results must include `empty` and `suggested_fix`. Do not treat `(last-first)/duration` as aggregation for metrics that are already `rate()` / ratios. See `docs/10_LIVE_EMPTY_EVIDENCE_FIX.md`.

When `LAB_CONTROLLER_URL` is set, raise query `start` to `injected_at − 5s`. See `docs/12_LIVE_CROSS_SCENARIO_RESIDUE.md` and `docs/13_LIVE_QUIET_BEFORE_INJECT.md`.

`get_trace_summary` must expose peer services and real span error counts. Do not hardcode `error_count: 0` on Tempo search hits. See `docs/14_LIVE_TRACE_SUMMARY_PEERS.md`.

## Tests

- Unit: bounds, truncation, redaction, error shape
- Contract: Holmes can load schema, Azure accepts it, timeout/size enforced, permission class correct

## Out of scope

Write execution, UI, arbitrary shell.
