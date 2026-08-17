from pathlib import Path

from mcp_servers.common.artifacts import ArtifactStore
from mcp_servers.common.runtime import ToolRuntime
from mcp_servers.contracts import tool_by_name
from mcp_servers.deployments.backends import CatalogBackend
from mcp_servers.deployments.tools import (
    compare_deployments,
    get_ci_failure_summary,
    get_recent_deployments,
)
from mcp_servers.observability.fakes import FakeLogsBackend, FakeMetricsBackend, FakeTracesBackend
from mcp_servers.observability.tools import (
    get_trace_summary,
    query_service_logs,
    query_service_metrics,
)
from mcp_servers.runbooks.tools import search_runbooks


def _runtime(name: str, tmp_path: Path, timeout: int | None = None) -> ToolRuntime:
    contract = tool_by_name(name)
    return ToolRuntime(
        timeout_seconds=timeout or contract["timeout_seconds"],
        max_result_bytes=contract["max_result_bytes"],
        artifacts=ArtifactStore(tmp_path),
    )


def test_query_service_metrics_contract(tmp_path: Path) -> None:
    result = query_service_metrics(
        {
            "service": "checkout",
            "metric": "request_rate",
            "start": "2026-08-17T09:00:00Z",
            "end": "2026-08-17T10:00:00Z",
            "aggregation": "avg",
            "limit": 20,
        },
        backend=FakeMetricsBackend(),
        runtime=_runtime("query_service_metrics", tmp_path),
    )
    assert result["ok"] is True
    assert result["tool"] == "query_service_metrics"
    assert "time_range" in result


def test_query_service_logs_contract(tmp_path: Path) -> None:
    result = query_service_logs(
        {
            "service": "checkout",
            "start": "2026-08-17T09:00:00Z",
            "end": "2026-08-17T10:00:00Z",
            "severity": "error",
            "limit": 20,
        },
        backend=FakeLogsBackend(),
        runtime=_runtime("query_service_logs", tmp_path),
    )
    assert result["ok"] is True
    assert result["tool"] == "query_service_logs"


def test_get_trace_summary_contract(tmp_path: Path) -> None:
    result = get_trace_summary(
        {
            "start": "2026-08-17T09:00:00Z",
            "end": "2026-08-17T10:00:00Z",
            "service": "checkout",
            "limit": 10,
        },
        backend=FakeTracesBackend(),
        runtime=_runtime("get_trace_summary", tmp_path),
    )
    assert result["ok"] is True
    assert result["tool"] == "get_trace_summary"


def test_get_recent_deployments_contract(tmp_path: Path) -> None:
    result = get_recent_deployments(
        {
            "service": "all",
            "start": "2026-08-17T06:00:00Z",
            "end": "2026-08-17T11:00:00Z",
            "limit": 20,
        },
        backend=CatalogBackend(),
        runtime=_runtime("get_recent_deployments", tmp_path),
    )
    assert result["ok"] is True
    assert {item["service"] for item in result["deployments"]} <= {
        "checkout",
        "payment",
        "gateway",
        "inventory",
        "notification",
    }


def test_compare_deployments_contract(tmp_path: Path) -> None:
    result = compare_deployments(
        {
            "service": "payment",
            "from_version": "2.0.4",
            "to_version": "2.1.0",
            "start": "2026-08-17T06:00:00Z",
            "end": "2026-08-17T11:00:00Z",
        },
        backend=CatalogBackend(),
        runtime=_runtime("compare_deployments", tmp_path),
    )
    assert result["ok"] is True
    assert result["files"]


def test_get_ci_failure_summary_contract(tmp_path: Path) -> None:
    result = get_ci_failure_summary(
        {
            "service": "checkout",
            "start": "2026-08-17T09:00:00Z",
            "end": "2026-08-17T11:00:00Z",
            "limit": 10,
        },
        backend=CatalogBackend(),
        runtime=_runtime("get_ci_failure_summary", tmp_path),
    )
    assert result["ok"] is True
    assert result["tool"] == "get_ci_failure_summary"


def test_search_runbooks_contract(tmp_path: Path) -> None:
    result = search_runbooks(
        {
            "query": "latency",
            "start": "2026-08-17T09:00:00Z",
            "end": "2026-08-17T10:00:00Z",
            "limit": 10,
        },
        runtime=_runtime("search_runbooks", tmp_path),
    )
    assert result["ok"] is True
    assert result["untrusted_content"] is True


def test_each_phase2_tool_enforces_timeout_from_catalog(tmp_path: Path) -> None:
    contract = tool_by_name("query_service_metrics")
    assert contract["timeout_seconds"] == 15
    from mcp_servers.observability.fakes import FakeMetricsBackend

    result = query_service_metrics(
        {
            "service": "checkout",
            "metric": "error_rate",
            "start": "2026-08-17T09:00:00Z",
            "end": "2026-08-17T10:00:00Z",
        },
        backend=FakeMetricsBackend(sleep_s=2),
        runtime=_runtime("query_service_metrics", tmp_path, timeout=1),
    )
    assert result["error_type"] == "timeout"
