from __future__ import annotations

import os
from typing import Literal

from mcp_servers.common.http_server import create_mcp, run_streamable_http
from mcp_servers.common.runtime import ToolRuntime
from mcp_servers.deployments.backends import CatalogBackend, LiveDeploymentBackend
from mcp_servers.deployments.tools import (
    compare_deployments as compare_deployments_impl,
)
from mcp_servers.deployments.tools import (
    get_ci_failure_summary as get_ci_failure_summary_impl,
)
from mcp_servers.deployments.tools import (
    get_recent_deployments as get_recent_deployments_impl,
)

mcp = create_mcp("opspilot-deployments")

_Service = Literal["gateway", "checkout", "payment", "inventory", "notification"]
_ServiceOrAll = Literal["all", "gateway", "checkout", "payment", "inventory", "notification"]


def _backend() -> CatalogBackend | LiveDeploymentBackend:
    timeout = float(os.environ.get("OPSPILOT_MCP_BACKEND_TIMEOUT", "12"))
    if os.environ.get("OPSPILOT_MCP_BACKEND", "live") == "fake":
        return CatalogBackend()
    return LiveDeploymentBackend(timeout)


@mcp.tool()
def get_recent_deployments(
    start: str,
    end: str,
    service: _ServiceOrAll = "all",
    limit: int = 20,
) -> dict[str, object]:
    """List recent deployments for a service. Returns version, time, SHA, status, and actor."""
    return get_recent_deployments_impl(
        {"service": service, "start": start, "end": end, "limit": limit},
        backend=_backend(),
        runtime=ToolRuntime.from_catalog("get_recent_deployments"),
    )


@mcp.tool()
def compare_deployments(
    service: _Service,
    from_version: str,
    to_version: str,
    start: str,
    end: str,
) -> dict[str, object]:
    """Structured deployment diff. Secrets, kubeconfig, and .env files are omitted."""
    return compare_deployments_impl(
        {
            "service": service,
            "from_version": from_version,
            "to_version": to_version,
            "start": start,
            "end": end,
        },
        backend=_backend(),
        runtime=ToolRuntime.from_catalog("compare_deployments"),
    )


@mcp.tool()
def get_ci_failure_summary(
    service: _Service,
    start: str,
    end: str,
    workflow: str = "",
    limit: int = 10,
) -> dict[str, object]:
    """Server-filtered CI failures: failed steps, error summary, and related commit only."""
    return get_ci_failure_summary_impl(
        {
            "service": service,
            "start": start,
            "end": end,
            "workflow": workflow,
            "limit": limit,
        },
        backend=_backend(),
        runtime=ToolRuntime.from_catalog("get_ci_failure_summary"),
    )


if __name__ == "__main__":
    run_streamable_http(mcp, 8002)
