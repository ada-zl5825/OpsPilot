from pathlib import Path

from mcp_servers.common.artifacts import ArtifactStore
from mcp_servers.common.redaction import REDACTED
from mcp_servers.common.runtime import ToolRuntime
from mcp_servers.deployments.backends import CatalogBackend
from mcp_servers.deployments.tools import (
    compare_deployments,
    get_ci_failure_summary,
    get_recent_deployments,
)


def _runtime(tmp_path: Path) -> ToolRuntime:
    return ToolRuntime(timeout_seconds=5, max_result_bytes=32768, artifacts=ArtifactStore(tmp_path))


def test_get_recent_deployments_filters_service_and_window(tmp_path: Path) -> None:
    result = get_recent_deployments(
        {
            "service": "checkout",
            "start": "2026-08-17T06:00:00Z",
            "end": "2026-08-17T11:00:00Z",
            "limit": 10,
        },
        backend=CatalogBackend(),
        runtime=_runtime(tmp_path),
    )
    assert result["ok"] is True
    versions = [item["version"] for item in result["deployments"]]
    assert versions == ["1.4.2"]
    assert result["deployments"][0]["git_sha"] == "c3f91aa8"
    assert result["deployments"][0]["actor"] == "release-bot"


def test_get_recent_deployments_rejects_unknown_service(tmp_path: Path) -> None:
    result = get_recent_deployments(
        {
            "service": "kube-system",
            "start": "2026-08-17T06:00:00Z",
            "end": "2026-08-17T11:00:00Z",
        },
        runtime=_runtime(tmp_path),
    )
    assert result["ok"] is False
    assert result["error_type"] == "validation"


def test_compare_deployments_omits_secrets_and_redacts(tmp_path: Path) -> None:
    result = compare_deployments(
        {
            "service": "checkout",
            "from_version": "1.4.1",
            "to_version": "1.4.2",
            "start": "2026-08-17T09:00:00Z",
            "end": "2026-08-17T10:30:00Z",
        },
        backend=CatalogBackend(),
        runtime=_runtime(tmp_path),
    )
    assert result["ok"] is True
    paths = [item["path"] for item in result["files"]]
    assert "simulator/services/checkout/pricing.py" in paths
    assert ".env" not in paths
    assert "deploy/kubeconfig" not in paths
    summaries = " ".join(item["summary"] for item in result["files"])
    assert "sk-abcdefghijklmnopqrst" not in summaries
    assert REDACTED in summaries


def test_compare_deployments_not_found(tmp_path: Path) -> None:
    result = compare_deployments(
        {
            "service": "checkout",
            "from_version": "9.9.9",
            "to_version": "9.9.10",
            "start": "2026-08-17T09:00:00Z",
            "end": "2026-08-17T10:30:00Z",
        },
        backend=CatalogBackend(),
        runtime=_runtime(tmp_path),
    )
    assert result["ok"] is False
    assert result["error_type"] == "not_found"
    assert result["retryable"] is False


def test_get_ci_failure_summary_filters_and_redacts(tmp_path: Path) -> None:
    result = get_ci_failure_summary(
        {
            "service": "checkout",
            "start": "2026-08-17T09:00:00Z",
            "end": "2026-08-17T11:00:00Z",
            "workflow": "checkout-ci",
            "limit": 5,
        },
        backend=CatalogBackend(),
        runtime=_runtime(tmp_path),
    )
    assert result["ok"] is True
    assert result["returned"] == 1
    assert result["failures"][0]["commit"] == "c3f91aa8"
    assert result["failures"][0]["failed_steps"][0]["name"] == "unit-tests"
    assert "super-secret" not in result["failures"][0]["error_summary"]
    assert REDACTED in result["failures"][0]["error_summary"]
