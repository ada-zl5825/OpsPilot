from __future__ import annotations

from collections.abc import Callable
from typing import Any

TRACE_ENRICH_LIMIT = 5

_ERROR_CODES = {2, "2", "STATUS_CODE_ERROR", "ERROR"}


def summarize_otlp_trace(trace_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    services: list[str] = []
    seen_services: set[str] = set()
    span_count = 0
    error_count = 0
    duration_ms = 0
    slowest: dict[str, Any] | None = None
    root_name = ""
    root_service = ""

    for batch in _iter_batches(payload):
        resource_service = _resource_service(batch.get("resource") or {})
        _remember_service(resource_service, services, seen_services)
        if not root_service and resource_service:
            root_service = resource_service
        for span in _iter_spans(batch):
            span_count += 1
            name = str(span.get("name") or "")
            if not root_name and name:
                root_name = name
            peer = _span_attr(span, "peer.service")
            _remember_service(peer, services, seen_services)
            if _span_is_error(span):
                error_count += 1
            span_ms = _span_duration_ms(span)
            duration_ms = max(duration_ms, span_ms)
            if slowest is None or span_ms > int(slowest.get("duration_ms") or 0):
                slowest = {
                    "name": name,
                    "service": resource_service,
                    "duration_ms": span_ms,
                    "peer_service": peer,
                }

    peers = [name for name in services if name and name != root_service]
    return {
        "trace_id": trace_id,
        "root_service": root_service,
        "root_name": root_name,
        "duration_ms": duration_ms,
        "span_count": span_count,
        "error_count": error_count,
        "services": services,
        "peer_services": peers,
        "slowest_span": slowest,
        "enriched": True,
    }


def search_hits_to_summaries(
    hits: list[dict[str, Any]],
    *,
    service: str,
    limit: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in hits[:limit]:
        rows.append(
            {
                "trace_id": item.get("traceID") or item.get("trace_id"),
                "root_service": item.get("rootServiceName") or service,
                "root_name": item.get("rootTraceName") or "",
                "duration_ms": int(item.get("durationMs") or item.get("duration_ms") or 0),
                "span_count": int(
                    (item.get("spanSet") or {}).get("matched") or item.get("span_count") or 0
                ),
                "services": [service] if service else [],
                "peer_services": [],
                "enriched": False,
            }
        )
    return rows


def enrich_longest_traces(
    rows: list[dict[str, Any]],
    fetch_detail: Callable[[str], dict[str, Any]],
    *,
    limit: int = TRACE_ENRICH_LIMIT,
) -> list[dict[str, Any]]:
    ranked = sorted(rows, key=lambda item: int(item.get("duration_ms") or 0), reverse=True)
    wanted = {str(item.get("trace_id") or "") for item in ranked[:limit] if item.get("trace_id")}
    for row in rows:
        trace_id = str(row.get("trace_id") or "")
        if not trace_id or trace_id not in wanted:
            continue
        try:
            detail = fetch_detail(trace_id)
        except Exception:
            continue
        if not isinstance(detail, dict):
            continue
        for key in (
            "root_service",
            "root_name",
            "duration_ms",
            "span_count",
            "error_count",
            "services",
            "peer_services",
            "slowest_span",
            "enriched",
        ):
            if key == "root_name" and row.get("root_name") and not detail.get("root_name"):
                continue
            if key == "root_service" and row.get("root_service") and not detail.get("root_service"):
                continue
            if key in detail:
                row[key] = detail[key]
        if not row.get("peer_services"):
            root = str(row.get("root_service") or "")
            row["peer_services"] = [
                name for name in row.get("services") or [] if name and name != root
            ]
        row["enriched"] = True
    return rows


def aggregate_trace_summary(traces: list[dict[str, Any]]) -> dict[str, Any]:
    services: list[str] = []
    seen: set[str] = set()
    peers: list[str] = []
    peer_seen: set[str] = set()
    slowest: dict[str, Any] | None = None
    for item in traces:
        for name in item.get("services") or []:
            _remember_service(str(name), services, seen)
        for name in item.get("peer_services") or []:
            _remember_service(str(name), peers, peer_seen)
        span = item.get("slowest_span")
        if not isinstance(span, dict):
            continue
        if slowest is None or int(span.get("duration_ms") or 0) > int(
            slowest.get("duration_ms") or 0
        ):
            slowest = span
    return {
        "count": len(traces),
        "error_traces": sum(1 for item in traces if int(item.get("error_count") or 0) > 0),
        "services": services,
        "peer_services": peers,
        "slowest_span": slowest,
    }


def _iter_batches(payload: dict[str, Any]) -> list[dict[str, Any]]:
    batches = payload.get("batches")
    if isinstance(batches, list):
        return [item for item in batches if isinstance(item, dict)]
    spans = payload.get("resourceSpans")
    if isinstance(spans, list):
        return [item for item in spans if isinstance(item, dict)]
    traces = payload.get("traces")
    if isinstance(traces, list) and traces and isinstance(traces[0], dict):
        return _iter_batches(traces[0])
    return []


def _iter_spans(batch: dict[str, Any]) -> list[dict[str, Any]]:
    scopes = batch.get("scopeSpans") or batch.get("instrumentationLibrarySpans") or []
    spans: list[dict[str, Any]] = []
    if not isinstance(scopes, list):
        return spans
    for scope in scopes:
        if not isinstance(scope, dict):
            continue
        items = scope.get("spans") or []
        if isinstance(items, list):
            spans.extend(item for item in items if isinstance(item, dict))
    return spans


def _resource_service(resource: dict[str, Any]) -> str:
    for attr in resource.get("attributes") or []:
        if isinstance(attr, dict) and attr.get("key") in {"service.name", "service"}:
            return _otlp_string(attr.get("value"))
    return ""


def _span_attr(span: dict[str, Any], key: str) -> str:
    for attr in span.get("attributes") or []:
        if isinstance(attr, dict) and attr.get("key") == key:
            return _otlp_string(attr.get("value"))
    return ""


def _span_is_error(span: dict[str, Any]) -> bool:
    status = span.get("status") or {}
    if not isinstance(status, dict):
        return False
    return status.get("code") in _ERROR_CODES


def _span_duration_ms(span: dict[str, Any]) -> int:
    start = _as_int(span.get("startTimeUnixNano"))
    end = _as_int(span.get("endTimeUnixNano"))
    if end > start:
        return int((end - start) / 1_000_000)
    return 0


def _otlp_string(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("stringValue") or "")
    if value is None:
        return ""
    return str(value)


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _remember_service(name: str, dest: list[str], seen: set[str]) -> None:
    if name and name not in seen:
        seen.add(name)
        dest.append(name)
