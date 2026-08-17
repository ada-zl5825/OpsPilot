from __future__ import annotations

import asyncio

from mcp_servers.common.fastmcp_schemas import fastmcp_input_schemas
from mcp_servers.common.null_args import drop_null_arguments
from mcp_servers.common.validation import parse_model
from mcp_servers.deployments.server import mcp as deployments_mcp
from mcp_servers.observability.schemas import LogQueryInput, MetricQueryInput, TraceSummaryInput
from mcp_servers.observability.server import mcp as observability_mcp

from opspilot.holmes.compatibility import validate_tool_schema_for_azure


def test_drop_null_arguments_keeps_required_values() -> None:
    cleaned = drop_null_arguments(
        {"service": "checkout", "path": None, "contains": None, "limit": 60}
    )
    assert cleaned == {"service": "checkout", "limit": 60}


def test_parse_model_accepts_azure_null_optional_strings() -> None:
    metrics = parse_model(
        MetricQueryInput,
        {
            "service": "checkout",
            "metric": "error_rate",
            "start": "2026-08-17T09:00:00Z",
            "end": "2026-08-17T10:00:00Z",
            "aggregation": "rate",
            "path": None,
            "limit": 60,
        },
    )
    assert metrics.path == ""

    logs = parse_model(
        LogQueryInput,
        {
            "service": "checkout",
            "start": "2026-08-17T09:00:00Z",
            "end": "2026-08-17T10:00:00Z",
            "severity": "error",
            "contains": None,
            "limit": 50,
        },
    )
    assert logs.contains == ""

    traces = parse_model(
        TraceSummaryInput,
        {
            "start": "2026-08-17T09:00:00Z",
            "end": "2026-08-17T10:00:00Z",
            "service": "checkout",
            "trace_id": None,
            "min_duration_ms": 0,
            "limit": 20,
        },
    )
    assert traces.trace_id == ""


def test_fastmcp_call_accepts_azure_null_optional_strings(monkeypatch) -> None:
    monkeypatch.setenv("OPSPILOT_MCP_BACKEND", "fake")
    metrics = asyncio.run(
        observability_mcp._tool_manager.call_tool(
            "query_service_metrics",
            {
                "service": "checkout",
                "metric": "error_rate",
                "start": "2026-08-17T09:00:00Z",
                "end": "2026-08-17T10:00:00Z",
                "aggregation": "rate",
                "path": None,
                "limit": 60,
            },
        )
    )
    assert metrics["ok"] is True

    logs = asyncio.run(
        observability_mcp._tool_manager.call_tool(
            "query_service_logs",
            {
                "service": "checkout",
                "start": "2026-08-17T09:00:00Z",
                "end": "2026-08-17T10:00:00Z",
                "severity": "error",
                "contains": None,
                "limit": 50,
            },
        )
    )
    assert logs["ok"] is True

    traces = asyncio.run(
        observability_mcp._tool_manager.call_tool(
            "get_trace_summary",
            {
                "start": "2026-08-17T09:00:00Z",
                "end": "2026-08-17T10:00:00Z",
                "service": "checkout",
                "trace_id": None,
                "min_duration_ms": 0,
                "limit": 20,
            },
        )
    )
    assert traces["ok"] is True

    ci = asyncio.run(
        deployments_mcp._tool_manager.call_tool(
            "get_ci_failure_summary",
            {
                "service": "checkout",
                "start": "2026-08-17T09:00:00Z",
                "end": "2026-08-17T10:00:00Z",
                "workflow": None,
                "limit": 10,
            },
        )
    )
    assert ci["ok"] is True


def test_null_coercion_does_not_add_anyof_null_to_azure_schema() -> None:
    generated = fastmcp_input_schemas(observability_mcp)
    for name in ("query_service_metrics", "query_service_logs", "get_trace_summary"):
        report = validate_tool_schema_for_azure(name, generated[name])
        assert report.compatible is True, (name, report.issues)
        dumped = str(generated[name])
        assert "anyOf" not in dumped
        assert "'type': 'null'" not in dumped
        assert '"type": "null"' not in dumped
