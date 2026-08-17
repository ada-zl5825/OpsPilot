from __future__ import annotations

import os
from typing import Any, Protocol

import httpx

from mcp_servers.common.errors import BackendError
from mcp_servers.common.time_range import TimeWindow
from mcp_servers.observability.schemas import MetricQueryInput

_PATH_SAFE = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/_-.:")

METRIC_TEMPLATES = {
    "request_rate": 'sum(rate(http_requests_total{service="$service"$path}[$rate]))',
    "error_rate": (
        'sum(rate(http_requests_total{service="$service",status=~"5.."$path}[$rate]))'
        " / clamp_min("
        'sum(rate(http_requests_total{service="$service"$path}[$rate])),1e-9)'
    ),
    "latency_p95": (
        "histogram_quantile(0.95, sum(rate("
        'http_request_duration_seconds_bucket{service="$service"$path}[$rate])) by (le))'
    ),
    "latency_avg": (
        'sum(rate(http_request_duration_seconds_sum{service="$service"$path}[$rate]))'
        " / clamp_min("
        'sum(rate(http_request_duration_seconds_count{service="$service"$path}[$rate])),1e-9)'
    ),
    "db_pool_checked_out": "checkout_db_pool_checked_out",
    "db_pool_available": "checkout_db_pool_available",
    "db_pool_max": "checkout_db_pool_max",
    "cache_lookup_p95": (
        "histogram_quantile(0.95, sum(rate(cache_lookup_duration_seconds_bucket[$rate])) by (le))"
    ),
    "downstream_p95": (
        "histogram_quantile(0.95, sum(rate("
        "downstream_request_duration_seconds_bucket[$rate])) by (le))"
    ),
}


class MetricsBackend(Protocol):
    def query_range(self, query: str, window: TimeWindow, limit: int) -> list[dict[str, Any]]: ...


class LogsBackend(Protocol):
    def query_range(
        self,
        service: str,
        window: TimeWindow,
        *,
        severity: str,
        contains: str,
        limit: int,
    ) -> list[dict[str, Any]]: ...


class TracesBackend(Protocol):
    def search(
        self,
        window: TimeWindow,
        *,
        service: str,
        trace_id: str,
        min_duration_ms: int,
        limit: int,
    ) -> list[dict[str, Any]]: ...


def render_metric_query(params: MetricQueryInput, window: TimeWindow) -> str:
    template = METRIC_TEMPLATES[params.metric]
    path = ""
    if params.path:
        if any(ch not in _PATH_SAFE for ch in params.path):
            raise ValueError("path contains unsupported characters")
        path = f',path="{params.path}"'
    return (
        template.replace("$service", params.service)
        .replace("$path", path)
        .replace("$rate", window.rate_window())
    )


class LiveMetricsBackend:
    def __init__(self, base_url: str, timeout: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def query_range(self, query: str, window: TimeWindow, limit: int) -> list[dict[str, Any]]:
        params = {
            "query": query,
            "start": window.start.timestamp(),
            "end": window.end.timestamp(),
            "step": window.prometheus_step(),
        }
        payload = _get_json(self._base_url, "/api/v1/query_range", params, self._timeout)
        if payload.get("status") != "success":
            raise BackendError("prometheus query failed")
        result = payload.get("data", {}).get("result", [])
        points: list[dict[str, Any]] = []
        for series in result:
            for ts, value in series.get("values", []):
                points.append({"t": float(ts), "v": _to_float(value)})
                if len(points) >= limit:
                    return points
        return points


class LiveLogsBackend:
    def __init__(self, base_url: str, timeout: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def query_range(
        self,
        service: str,
        window: TimeWindow,
        *,
        severity: str,
        contains: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        query = _loki_query(service, severity, contains)
        params = {
            "query": query,
            "start": _nano(window.start.timestamp()),
            "end": _nano(window.end.timestamp()),
            "limit": str(limit),
        }
        payload = _get_json(self._base_url, "/loki/api/v1/query_range", params, self._timeout)
        if payload.get("status") != "success":
            raise BackendError("loki query failed")
        entries: list[dict[str, Any]] = []
        for stream in payload.get("data", {}).get("result", []):
            labels = stream.get("stream", {})
            for ts, line in stream.get("values", []):
                entries.append(
                    {
                        "ts": ts,
                        "service": labels.get("service_name") or labels.get("service") or service,
                        "severity": _infer_severity(line, severity),
                        "message": line,
                    }
                )
                if len(entries) >= limit:
                    return entries
        return entries


class LiveTracesBackend:
    def __init__(self, base_url: str, timeout: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def search(
        self,
        window: TimeWindow,
        *,
        service: str,
        trace_id: str,
        min_duration_ms: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        if trace_id:
            return [self._by_id(trace_id)]
        params: dict[str, str] = {
            "start": str(int(window.start.timestamp())),
            "end": str(int(window.end.timestamp())),
            "limit": str(limit),
        }
        if service:
            params["tags"] = f"service.name={service}"
        if min_duration_ms:
            params["minDuration"] = f"{min_duration_ms}ms"
        payload = _get_json(self._base_url, "/api/search", params, self._timeout)
        traces = payload.get("traces", [])
        summaries: list[dict[str, Any]] = []
        for item in traces[:limit]:
            summaries.append(
                {
                    "trace_id": item.get("traceID") or item.get("trace_id"),
                    "root_service": item.get("rootServiceName") or service,
                    "root_name": item.get("rootTraceName") or "",
                    "duration_ms": int(item.get("durationMs") or 0),
                    "span_count": int(item.get("spanSet", {}).get("matched", 0) or 0),
                    "error_count": 0,
                    "services": [service] if service else [],
                }
            )
        return summaries

    def _by_id(self, trace_id: str) -> dict[str, Any]:
        payload = _get_json(self._base_url, f"/api/traces/{trace_id}", {}, self._timeout)
        batches = payload.get("batches") or payload.get("resourceSpans") or []
        services: list[str] = []
        span_count = 0
        duration_ms = 0
        for batch in batches:
            resource = batch.get("resource", {})
            for attr in resource.get("attributes", []):
                if attr.get("key") == "service.name":
                    services.append(str(attr.get("value", {}).get("stringValue", "")))
            spans = batch.get("scopeSpans") or batch.get("instrumentationLibrarySpans") or []
            for scope in spans:
                items = scope.get("spans", [])
                span_count += len(items)
                for span in items:
                    start = int(span.get("startTimeUnixNano") or 0)
                    end = int(span.get("endTimeUnixNano") or 0)
                    if end > start:
                        duration_ms = max(duration_ms, int((end - start) / 1_000_000))
        return {
            "trace_id": trace_id,
            "root_service": services[0] if services else "",
            "root_name": "",
            "duration_ms": duration_ms,
            "span_count": span_count,
            "error_count": 0,
            "services": [name for name in services if name],
        }


def live_backends(timeout: float) -> tuple[LiveMetricsBackend, LiveLogsBackend, LiveTracesBackend]:
    return (
        LiveMetricsBackend(os.environ.get("PROMETHEUS_URL", "http://127.0.0.1:9090"), timeout),
        LiveLogsBackend(os.environ.get("LOKI_URL", "http://127.0.0.1:3100"), timeout),
        LiveTracesBackend(os.environ.get("TEMPO_URL", "http://127.0.0.1:3200"), timeout),
    )


def _loki_query(service: str, severity: str, contains: str) -> str:
    query = f'{{service_name="{service}"}}'
    if severity != "all":
        query += f' |~ "(?i){severity}"'
    if contains:
        escaped = contains.replace("`", "").replace("\\", "")
        query += f" |= `{escaped}`"
    return query


def _get_json(base_url: str, path: str, params: dict[str, Any], timeout: float) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(f"{base_url}{path}", params=params)
    except httpx.HTTPError as exc:
        raise BackendError(
            f"backend unreachable: {type(exc).__name__}",
            suggested_fix="start the lab observability stack and retry",
        ) from exc
    if response.status_code >= 400:
        raise BackendError(f"backend HTTP {response.status_code}")
    payload = response.json()
    if not isinstance(payload, dict):
        raise BackendError("backend returned a non-object payload")
    return payload


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _nano(seconds: float) -> str:
    return str(int(seconds * 1_000_000_000))


def _infer_severity(line: str, requested: str) -> str:
    lower = line.lower()
    for level in ("error", "warn", "info", "debug"):
        if level in lower:
            return level
    return requested if requested != "all" else "info"
