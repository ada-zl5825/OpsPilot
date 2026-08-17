from __future__ import annotations

from statistics import mean
from typing import Any

from mcp_servers.common.errors import structured_error
from mcp_servers.common.runtime import ToolRuntime, invoke_tool
from mcp_servers.common.schemas import SERVICE_NAMES
from mcp_servers.common.time_range import TimeWindow, apply_window_flags
from mcp_servers.common.validation import parse_model, validation_failure, window_or_error
from mcp_servers.observability.backends import (
    LogsBackend,
    MetricsBackend,
    TracesBackend,
    render_metric_query,
)
from mcp_servers.observability.fakes import FakeLogsBackend, FakeMetricsBackend, FakeTracesBackend
from mcp_servers.observability.traces import aggregate_trace_summary
from mcp_servers.observability.schemas import LogQueryInput, MetricQueryInput, TraceSummaryInput


def query_service_metrics(
    params: dict[str, Any],
    *,
    backend: MetricsBackend | None = None,
    runtime: ToolRuntime | None = None,
) -> dict[str, Any]:
    tool = "query_service_metrics"
    runtime = runtime or ToolRuntime.from_catalog(tool)
    try:
        parsed = parse_model(MetricQueryInput, params)
    except Exception as exc:
        return validation_failure(tool, exc, params)
    window = window_or_error(tool, parsed.start, parsed.end, params)
    if not isinstance(window, TimeWindow):
        return window
    backend = backend or FakeMetricsBackend()

    def _run() -> dict[str, Any]:
        query = render_metric_query(parsed, window)
        points = backend.query_range(query, window, parsed.limit)
        path_ignored = False
        if parsed.path and not points:
            fallback = parsed.model_copy(update={"path": ""})
            points = backend.query_range(
                render_metric_query(fallback, window), window, parsed.limit
            )
            path_ignored = bool(points)
        values = [float(point["v"]) for point in points]
        empty = not points
        payload: dict[str, Any] = {
            "ok": True,
            "tool": tool,
            "service": parsed.service,
            "metric": parsed.metric,
            "aggregation": parsed.aggregation,
            "time_range": window.as_dict(),
            "aggregated_value": _aggregate(values, parsed.aggregation, window),
            "peak_value": round(max(values), 6) if values else None,
            "point_count": len(points),
            "empty": empty,
            "path": "" if path_ignored else parsed.path,
            "path_requested": parsed.path,
            "path_ignored": path_ignored,
            "points": points,
        }
        if empty:
            payload["suggested_fix"] = (
                "omit path and retry; empty series is not evidence that the service is healthy"
            )
        elif path_ignored:
            payload["suggested_fix"] = (
                "no series matched the requested path; returned service-wide series"
            )
        return apply_window_flags(payload, window)

    return invoke_tool(tool, _run, runtime, params=parsed.model_dump(), time_range=window.as_dict())


def query_service_logs(
    params: dict[str, Any],
    *,
    backend: LogsBackend | None = None,
    runtime: ToolRuntime | None = None,
) -> dict[str, Any]:
    tool = "query_service_logs"
    runtime = runtime or ToolRuntime.from_catalog(tool)
    try:
        parsed = parse_model(LogQueryInput, params)
    except Exception as exc:
        return validation_failure(tool, exc, params)
    window = window_or_error(tool, parsed.start, parsed.end, params)
    if not isinstance(window, TimeWindow):
        return window
    backend = backend or FakeLogsBackend()

    def _run() -> dict[str, Any]:
        entries = backend.query_range(
            parsed.service,
            window,
            severity=parsed.severity,
            contains=parsed.contains,
            limit=parsed.limit,
        )
        payload: dict[str, Any] = {
            "ok": True,
            "tool": tool,
            "service": parsed.service,
            "severity": parsed.severity,
            "time_range": window.as_dict(),
            "returned": len(entries),
            "empty": not entries,
            "entries": entries,
        }
        if not entries:
            payload["suggested_fix"] = (
                "try severity=all or a wider window; zero lines is not proof there is no incident"
            )
        return apply_window_flags(payload, window)

    return invoke_tool(tool, _run, runtime, params=parsed.model_dump(), time_range=window.as_dict())


def get_trace_summary(
    params: dict[str, Any],
    *,
    backend: TracesBackend | None = None,
    runtime: ToolRuntime | None = None,
) -> dict[str, Any]:
    tool = "get_trace_summary"
    runtime = runtime or ToolRuntime.from_catalog(tool)
    try:
        parsed = parse_model(TraceSummaryInput, params)
    except Exception as exc:
        return validation_failure(tool, exc, params)
    if parsed.service and parsed.service not in SERVICE_NAMES:
        return structured_error(
            tool,
            error_type="validation",
            message="service must be a known lab service or empty",
            retryable=True,
            suggested_fix="pass a lab service name or omit service",
            params=params,
        )
    if not parsed.service and not parsed.trace_id:
        return structured_error(
            tool,
            error_type="validation",
            message="service or trace_id is required",
            retryable=True,
            suggested_fix="provide a service name or a trace_id",
            params=params,
        )
    window = window_or_error(tool, parsed.start, parsed.end, params)
    if not isinstance(window, TimeWindow):
        return window
    backend = backend or FakeTracesBackend()

    def _run() -> dict[str, Any]:
        traces = backend.search(
            window,
            service=parsed.service,
            trace_id=parsed.trace_id,
            min_duration_ms=parsed.min_duration_ms,
            limit=parsed.limit,
        )
        durations = [int(item.get("duration_ms", 0)) for item in traces]
        summary = aggregate_trace_summary(traces)
        summary["p95_duration_ms"] = _percentile(durations, 0.95)
        payload: dict[str, Any] = {
            "ok": True,
            "tool": tool,
            "time_range": window.as_dict(),
            "returned": len(traces),
            "empty": not traces,
            "summary": summary,
            "traces": traces,
        }
        if not traces:
            payload["suggested_fix"] = (
                "widen the window or omit min_duration_ms; empty traces are not a healthy signal"
            )
        elif summary.get("peer_services"):
            payload["suggested_fix"] = (
                "trace peers list other services on the same request; "
                "query those services if the selected service has empty logs or only mirrored 5xx"
            )
        return apply_window_flags(payload, window)

    return invoke_tool(tool, _run, runtime, params=parsed.model_dump(), time_range=window.as_dict())


def _aggregate(values: list[float], aggregation: str, window: TimeWindow) -> float | None:
    if not values:
        return None
    if aggregation == "max":
        return round(max(values), 6)
    if aggregation == "p95":
        return round(_percentile(values, 0.95), 6)
    if aggregation == "rate":
        # PromQL templates already apply rate()/ratio. Do not treat points as a counter.
        return round(mean(values), 6)
    return round(mean(values), 6)


def _percentile(values: list[float] | list[int], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(item) for item in values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * q))))
    return ordered[index]
