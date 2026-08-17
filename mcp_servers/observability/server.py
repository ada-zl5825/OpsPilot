from __future__ import annotations

import os
from typing import Literal

from mcp_servers.common.http_server import create_mcp, run_streamable_http
from mcp_servers.common.runtime import ToolRuntime
from mcp_servers.observability.backends import live_backends
from mcp_servers.observability.fakes import FakeLogsBackend, FakeMetricsBackend, FakeTracesBackend
from mcp_servers.observability.tools import (
    get_trace_summary as get_trace_summary_impl,
)
from mcp_servers.observability.tools import (
    query_service_logs as query_service_logs_impl,
)
from mcp_servers.observability.tools import (
    query_service_metrics as query_service_metrics_impl,
)

mcp = create_mcp("opspilot-observability")

_Service = Literal["gateway", "checkout", "payment", "inventory", "notification"]
_Metric = Literal[
    "request_rate",
    "error_rate",
    "latency_p95",
    "latency_avg",
    "db_pool_checked_out",
    "db_pool_available",
    "db_pool_max",
    "cache_lookup_p95",
    "downstream_p95",
]
_Aggregation = Literal["avg", "max", "p95", "rate"]
_Severity = Literal["debug", "info", "warn", "error", "all"]


def _backends() -> tuple[object, object, object]:
    timeout = float(os.environ.get("OPSPILOT_MCP_BACKEND_TIMEOUT", "12"))
    if os.environ.get("OPSPILOT_MCP_BACKEND", "live") == "fake":
        return FakeMetricsBackend(), FakeLogsBackend(), FakeTracesBackend()
    return live_backends(timeout)


@mcp.tool()
def query_service_metrics(
    service: _Service,
    metric: _Metric,
    start: str,
    end: str,
    aggregation: _Aggregation = "avg",
    path: str = "",
    limit: int = 60,
) -> dict[str, object]:
    """Read a typed service metric. Omit path unless a prior result showed that label."""
    metrics, _, _ = _backends()
    return query_service_metrics_impl(
        {
            "service": service,
            "metric": metric,
            "start": start,
            "end": end,
            "aggregation": aggregation,
            "path": path,
            "limit": limit,
        },
        backend=metrics,  # type: ignore[arg-type]
        runtime=ToolRuntime.from_catalog("query_service_metrics"),
    )


@mcp.tool()
def query_service_logs(
    service: _Service,
    start: str,
    end: str,
    severity: _Severity = "error",
    contains: str = "",
    limit: int = 50,
) -> dict[str, object]:
    """Read filtered service logs. Zero lines is not proof of no incident."""
    _, logs, _ = _backends()
    return query_service_logs_impl(
        {
            "service": service,
            "start": start,
            "end": end,
            "severity": severity,
            "contains": contains,
            "limit": limit,
        },
        backend=logs,  # type: ignore[arg-type]
        runtime=ToolRuntime.from_catalog("query_service_logs"),
    )


@mcp.tool()
def get_trace_summary(
    start: str,
    end: str,
    service: str = "",
    trace_id: str = "",
    min_duration_ms: int = 0,
    limit: int = 20,
) -> dict[str, object]:
    """Return trace summaries only. Provide service or trace_id. No raw span dumps."""
    _, _, traces = _backends()
    return get_trace_summary_impl(
        {
            "start": start,
            "end": end,
            "service": service,
            "trace_id": trace_id,
            "min_duration_ms": min_duration_ms,
            "limit": limit,
        },
        backend=traces,  # type: ignore[arg-type]
        runtime=ToolRuntime.from_catalog("get_trace_summary"),
    )


if __name__ == "__main__":
    run_streamable_http(mcp, 8001)
