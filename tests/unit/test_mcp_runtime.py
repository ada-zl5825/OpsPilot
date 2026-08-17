from pathlib import Path

import pytest
from mcp_servers.common.artifacts import ArtifactStore
from mcp_servers.common.budget import apply_budget
from mcp_servers.common.errors import structured_error
from mcp_servers.common.redaction import REDACTED, redact_mapping
from mcp_servers.common.runtime import ToolRuntime, invoke_tool
from mcp_servers.common.time_range import MAX_WINDOW_SECONDS, parse_time_range
from mcp_servers.observability.fakes import FakeMetricsBackend
from mcp_servers.observability.tools import query_service_metrics

WINDOW = {
    "service": "checkout",
    "metric": "error_rate",
    "start": "2026-08-17T09:00:00Z",
    "end": "2026-08-17T10:00:00Z",
    "aggregation": "avg",
    "limit": 60,
}


def test_time_range_rejects_inverted_and_oversized_windows() -> None:
    with pytest.raises(ValueError, match="after start"):
        parse_time_range("2026-08-17T10:00:00Z", "2026-08-17T09:00:00Z")
    with pytest.raises(ValueError, match="at most"):
        parse_time_range("2026-08-17T00:00:00Z", "2026-08-18T00:00:00Z")
    assert MAX_WINDOW_SECONDS == 6 * 60 * 60


def test_structured_error_has_required_fields() -> None:
    error = structured_error(
        "query_service_logs",
        error_type="timeout",
        message="timed out",
        retryable=True,
        suggested_fix="narrow the time range",
        params={"service": "checkout", "token": "leak"},
        time_range={"start": "2026-08-17T09:00:00Z", "end": "2026-08-17T10:00:00Z"},
    )
    assert error["ok"] is False
    assert error["tool"] == "query_service_logs"
    assert error["error_type"] == "timeout"
    assert error["retryable"] is True
    assert error["time_range"]["start"].startswith("2026-08-17")
    assert error["safe_params"]["token"] == REDACTED


def test_budget_spills_and_truncates(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    payload = {
        "ok": True,
        "tool": "query_service_logs",
        "entries": [{"message": "x" * 200} for _ in range(40)],
    }
    result = apply_budget(
        "query_service_logs",
        payload,
        max_result_bytes=400,
        store=store,
        time_range={"start": "2026-08-17T09:00:00Z", "end": "2026-08-17T10:00:00Z"},
    )
    assert result["ok"] is True
    assert result["truncated"] is True
    assert result["artifact_ref"].startswith("artifact://")
    assert len(result.get("entries", [])) <= 3
    spilled = tmp_path / result["artifact_ref"].removeprefix("artifact://")
    assert spilled.is_file()


def test_redaction_strips_secrets_from_tool_payloads() -> None:
    payload = redact_mapping(
        {"message": "authorization=Bearer abc.def", "kubeconfig": "value", "ok": True}
    )
    assert payload["kubeconfig"] == REDACTED
    assert "Bearer abc.def" not in payload["message"]


def test_timeout_returns_structured_error() -> None:
    runtime = ToolRuntime(timeout_seconds=1, max_result_bytes=65536, artifacts=ArtifactStore())
    result = query_service_metrics(
        WINDOW,
        backend=FakeMetricsBackend(sleep_s=2),
        runtime=runtime,
    )
    assert result["ok"] is False
    assert result["error_type"] == "timeout"
    assert result["retryable"] is True


def test_invoke_tool_passes_success_through(tmp_path: Path) -> None:
    runtime = ToolRuntime(
        timeout_seconds=2,
        max_result_bytes=4096,
        artifacts=ArtifactStore(tmp_path),
    )
    result = invoke_tool(
        "search_runbooks",
        lambda: {"ok": True, "tool": "search_runbooks", "runbooks": []},
        runtime,
        params={"query": "5xx"},
        time_range={"start": "2026-08-17T09:00:00Z", "end": "2026-08-17T10:00:00Z"},
    )
    assert result["ok"] is True
    assert result["truncated"] is False
