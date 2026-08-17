from pathlib import Path

from mcp_servers.common.artifacts import ArtifactStore
from mcp_servers.common.redaction import REDACTED
from mcp_servers.common.runtime import ToolRuntime
from mcp_servers.observability.fakes import FakeLogsBackend, FakeMetricsBackend, FakeTracesBackend
from mcp_servers.observability.tools import (
    get_trace_summary,
    query_service_logs,
    query_service_metrics,
)


def _runtime(tmp_path: Path, max_result_bytes: int = 65536) -> ToolRuntime:
    return ToolRuntime(
        timeout_seconds=5,
        max_result_bytes=max_result_bytes,
        artifacts=ArtifactStore(tmp_path),
    )


def test_query_service_metrics_typed_template_and_aggregation(tmp_path: Path) -> None:
    backend = FakeMetricsBackend()
    result = query_service_metrics(
        {
            "service": "checkout",
            "metric": "error_rate",
            "start": "2026-08-17T09:00:00Z",
            "end": "2026-08-17T10:00:00Z",
            "aggregation": "max",
            "limit": 10,
        },
        backend=backend,
        runtime=_runtime(tmp_path),
    )
    assert result["ok"] is True
    assert result["aggregated_value"] == 0.18
    assert "http_requests_total" in backend.last_query
    assert 'status=~"5.."' in backend.last_query
    assert "promql" not in result


def test_query_service_metrics_rate_uses_mean_not_counter_delta(tmp_path: Path) -> None:
    backend = FakeMetricsBackend(
        [
            {"t": 1_700_000_000.0, "v": 0.12},
            {"t": 1_700_000_060.0, "v": 0.18},
        ]
    )
    result = query_service_metrics(
        {
            "service": "checkout",
            "metric": "error_rate",
            "start": "2026-08-17T09:00:00Z",
            "end": "2026-08-17T10:00:00Z",
            "aggregation": "rate",
            "limit": 10,
        },
        backend=backend,
        runtime=_runtime(tmp_path),
    )
    assert result["ok"] is True
    assert result["aggregated_value"] == 0.15
    assert result["peak_value"] == 0.18
    assert result["empty"] is False


def test_query_service_metrics_ignores_unknown_path_and_retries(tmp_path: Path) -> None:
    class PathSensitiveFake(FakeMetricsBackend):
        def query_range(self, query: str, window, limit: int):  # type: ignore[no-untyped-def]
            self.last_query = query
            if "path=" in query:
                return []
            return super().query_range(query, window, limit)

    result = query_service_metrics(
        {
            "service": "checkout",
            "metric": "error_rate",
            "start": "2026-08-17T09:00:00Z",
            "end": "2026-08-17T10:00:00Z",
            "aggregation": "max",
            "path": "/checkout",
            "limit": 10,
        },
        backend=PathSensitiveFake(),
        runtime=_runtime(tmp_path),
    )
    assert result["ok"] is True
    assert result["path_ignored"] is True
    assert result["path_requested"] == "/checkout"
    assert result["empty"] is False
    assert result["aggregated_value"] == 0.18
    assert "path" in result["suggested_fix"]


def test_query_service_metrics_empty_series_is_not_healthy(tmp_path: Path) -> None:
    result = query_service_metrics(
        {
            "service": "checkout",
            "metric": "error_rate",
            "start": "2026-08-17T09:00:00Z",
            "end": "2026-08-17T10:00:00Z",
            "aggregation": "max",
            "limit": 10,
        },
        backend=FakeMetricsBackend(points=[]),
        runtime=_runtime(tmp_path),
    )
    assert result["ok"] is True
    assert result["empty"] is True
    assert result["aggregated_value"] is None
    assert "not evidence" in result["suggested_fix"]


def test_query_service_metrics_accepts_null_optional_path(tmp_path: Path) -> None:
    result = query_service_metrics(
        {
            "service": "checkout",
            "metric": "error_rate",
            "start": "2026-08-17T09:00:00Z",
            "end": "2026-08-17T10:00:00Z",
            "aggregation": "max",
            "path": None,
            "limit": 10,
        },
        backend=FakeMetricsBackend(),
        runtime=_runtime(tmp_path),
    )
    assert result["ok"] is True


def test_query_service_metrics_rejects_unknown_metric(tmp_path: Path) -> None:
    result = query_service_metrics(
        {
            "service": "checkout",
            "metric": "up{job='x'}",
            "start": "2026-08-17T09:00:00Z",
            "end": "2026-08-17T10:00:00Z",
        },
        runtime=_runtime(tmp_path),
    )
    assert result["ok"] is False
    assert result["error_type"] == "validation"


def test_query_service_metrics_rejects_unsafe_path(tmp_path: Path) -> None:
    result = query_service_metrics(
        {
            "service": "checkout",
            "metric": "request_rate",
            "start": "2026-08-17T09:00:00Z",
            "end": "2026-08-17T10:00:00Z",
            "path": '"/api",status=~".*"',
        },
        runtime=_runtime(tmp_path),
    )
    assert result["ok"] is False
    assert result["error_type"] == "validation"


def test_query_service_logs_filters_and_redacts(tmp_path: Path) -> None:
    result = query_service_logs(
        {
            "service": "checkout",
            "start": "2026-08-17T09:00:00Z",
            "end": "2026-08-17T10:00:00Z",
            "severity": "error",
            "contains": "deadline",
            "limit": 20,
        },
        backend=FakeLogsBackend(),
        runtime=_runtime(tmp_path),
    )
    assert result["ok"] is True
    assert result["returned"] == 1
    assert "deadline" in result["entries"][0]["message"]

    leaked = query_service_logs(
        {
            "service": "checkout",
            "start": "2026-08-17T09:00:00Z",
            "end": "2026-08-17T10:00:00Z",
            "severity": "error",
            "contains": "authorization",
            "limit": 20,
        },
        backend=FakeLogsBackend(),
        runtime=_runtime(tmp_path),
    )
    assert leaked["ok"] is True
    assert REDACTED in leaked["entries"][0]["message"]
    assert "sk-lab-secret" not in leaked["entries"][0]["message"]


def test_query_service_logs_spills_when_over_budget(tmp_path: Path) -> None:
    huge = FakeLogsBackend(
        [
            {
                "ts": str(i),
                "service": "checkout",
                "severity": "error",
                "message": "failure " + ("x" * 80),
            }
            for i in range(30)
        ]
    )
    result = query_service_logs(
        {
            "service": "checkout",
            "start": "2026-08-17T09:00:00Z",
            "end": "2026-08-17T10:00:00Z",
            "severity": "error",
            "limit": 30,
        },
        backend=huge,
        runtime=_runtime(tmp_path, max_result_bytes=800),
    )
    assert result["ok"] is True
    assert result["truncated"] is True
    assert result["artifact_ref"].startswith("artifact://")
    assert len(result.get("entries", [])) <= 3


def test_get_trace_summary_requires_service_or_trace_id(tmp_path: Path) -> None:
    result = get_trace_summary(
        {
            "start": "2026-08-17T09:00:00Z",
            "end": "2026-08-17T10:00:00Z",
        },
        runtime=_runtime(tmp_path),
    )
    assert result["ok"] is False
    assert result["error_type"] == "validation"


def test_get_trace_summary_filters_by_duration(tmp_path: Path) -> None:
    result = get_trace_summary(
        {
            "start": "2026-08-17T09:00:00Z",
            "end": "2026-08-17T10:00:00Z",
            "service": "checkout",
            "min_duration_ms": 1000,
            "limit": 10,
        },
        backend=FakeTracesBackend(),
        runtime=_runtime(tmp_path),
    )
    assert result["ok"] is True
    assert result["returned"] == 1
    assert result["traces"][0]["duration_ms"] == 2100
    assert result["summary"]["count"] == 1
