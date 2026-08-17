from __future__ import annotations

from typing import Any

from mcp_servers.common.errors import structured_error
from mcp_servers.common.runtime import ToolRuntime, invoke_tool
from mcp_servers.common.time_range import TimeWindow
from mcp_servers.common.validation import parse_model, validation_failure, window_or_error
from mcp_servers.deployments.backends import CatalogBackend, DeploymentBackend
from mcp_servers.deployments.schemas import (
    CiFailureInput,
    CompareDeploymentsInput,
    RecentDeploymentsInput,
)
from mcp_servers.deployments.store import is_readable_path


def get_recent_deployments(
    params: dict[str, Any],
    *,
    backend: DeploymentBackend | None = None,
    runtime: ToolRuntime | None = None,
) -> dict[str, Any]:
    tool = "get_recent_deployments"
    runtime = runtime or ToolRuntime.from_catalog(tool)
    try:
        parsed = parse_model(RecentDeploymentsInput, params)
    except Exception as exc:
        return validation_failure(tool, exc, params)
    window = window_or_error(tool, parsed.start, parsed.end, params)
    if not isinstance(window, TimeWindow):
        return window
    backend = backend or CatalogBackend()

    def _run() -> dict[str, Any]:
        deployments = backend.list_deployments(parsed.service, window, parsed.limit)
        return {
            "ok": True,
            "tool": tool,
            "service": parsed.service,
            "time_range": window.as_dict(),
            "returned": len(deployments),
            "deployments": deployments,
        }

    return invoke_tool(tool, _run, runtime, params=parsed.model_dump(), time_range=window.as_dict())


def compare_deployments(
    params: dict[str, Any],
    *,
    backend: DeploymentBackend | None = None,
    runtime: ToolRuntime | None = None,
) -> dict[str, Any]:
    tool = "compare_deployments"
    runtime = runtime or ToolRuntime.from_catalog(tool)
    try:
        parsed = parse_model(CompareDeploymentsInput, params)
    except Exception as exc:
        return validation_failure(tool, exc, params)
    window = window_or_error(tool, parsed.start, parsed.end, params)
    if not isinstance(window, TimeWindow):
        return window
    backend = backend or CatalogBackend()

    def _run() -> dict[str, Any]:
        diff = backend.compare(parsed.service, parsed.from_version, parsed.to_version)
        if diff is None:
            return structured_error(
                tool,
                error_type="not_found",
                message="no readable diff for that version pair",
                retryable=False,
                suggested_fix="use versions returned by get_recent_deployments",
                params=parsed.model_dump(),
                time_range=window.as_dict(),
            )
        files = [
            item
            for item in diff.get("files", [])
            if isinstance(item, dict) and is_readable_path(str(item.get("path", "")))
        ]
        return {
            "ok": True,
            "tool": tool,
            "service": parsed.service,
            "from_version": parsed.from_version,
            "to_version": parsed.to_version,
            "time_range": window.as_dict(),
            "files": files,
            "omitted_sensitive_files": True,
        }

    return invoke_tool(tool, _run, runtime, params=parsed.model_dump(), time_range=window.as_dict())


def get_ci_failure_summary(
    params: dict[str, Any],
    *,
    backend: DeploymentBackend | None = None,
    runtime: ToolRuntime | None = None,
) -> dict[str, Any]:
    tool = "get_ci_failure_summary"
    runtime = runtime or ToolRuntime.from_catalog(tool)
    try:
        parsed = parse_model(CiFailureInput, params)
    except Exception as exc:
        return validation_failure(tool, exc, params)
    window = window_or_error(tool, parsed.start, parsed.end, params)
    if not isinstance(window, TimeWindow):
        return window
    backend = backend or CatalogBackend()

    def _run() -> dict[str, Any]:
        failures = backend.ci_failures(parsed.service, window, parsed.workflow, parsed.limit)
        summaries = []
        for item in failures:
            summaries.append(
                {
                    "service": item.get("service"),
                    "workflow": item.get("workflow"),
                    "run_id": item.get("run_id"),
                    "commit": item.get("commit"),
                    "failed_at": item.get("failed_at"),
                    "failed_steps": item.get("failed_steps", []),
                    "error_summary": item.get("log_excerpt", ""),
                }
            )
        return {
            "ok": True,
            "tool": tool,
            "service": parsed.service,
            "time_range": window.as_dict(),
            "returned": len(summaries),
            "failures": summaries,
        }

    return invoke_tool(tool, _run, runtime, params=parsed.model_dump(), time_range=window.as_dict())
