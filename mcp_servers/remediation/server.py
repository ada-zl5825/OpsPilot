from __future__ import annotations

from typing import Literal

from mcp.server.fastmcp import FastMCP

from mcp_servers.common.http_server import run_streamable_http
from mcp_servers.common.runtime import ToolRuntime
from mcp_servers.remediation.tools import (
    dry_run_remediation as dry_run_remediation_impl,
)
from mcp_servers.remediation.tools import (
    get_remediation_capabilities as get_remediation_capabilities_impl,
)
from mcp_servers.remediation.tools import (
    get_resource_snapshot as get_resource_snapshot_impl,
)
from mcp_servers.remediation.tools import (
    propose_restart_workload as propose_restart_workload_impl,
)
from mcp_servers.remediation.tools import (
    propose_rollback_deployment as propose_rollback_deployment_impl,
)
from mcp_servers.remediation.tools import (
    propose_scale_workload as propose_scale_workload_impl,
)
from mcp_servers.remediation.tools import (
    propose_update_config as propose_update_config_impl,
)
from mcp_servers.remediation.tools import (
    verify_recovery as verify_recovery_impl,
)

mcp = FastMCP("opspilot-remediation")

_Service = Literal["gateway", "checkout", "payment", "inventory", "notification"]
_Namespace = Literal["lab"]


@mcp.tool()
def get_remediation_capabilities(unused: str = "") -> dict[str, object]:
    """List allowlisted remediation actions. Does not execute writes."""
    return get_remediation_capabilities_impl(
        {"unused": unused},
        runtime=ToolRuntime.from_catalog("get_remediation_capabilities"),
    )


@mcp.tool()
def get_resource_snapshot(service: _Service, namespace: _Namespace = "lab") -> dict[str, object]:
    """Read the current lab workload snapshot. Read-only."""
    return get_resource_snapshot_impl(
        {"service": service, "namespace": namespace},
        runtime=ToolRuntime.from_catalog("get_resource_snapshot"),
    )


@mcp.tool()
def dry_run_remediation(proposal_id: str) -> dict[str, object]:
    """Compile a typed command and evaluate policy. Does not mutate the cluster."""
    return dry_run_remediation_impl(
        {"proposal_id": proposal_id},
        runtime=ToolRuntime.from_catalog("dry_run_remediation"),
    )


@mcp.tool()
def verify_recovery(
    service: _Service,
    namespace: _Namespace = "lab",
    max_latency_ms: int = 1500,
    proposal_id: str = "",
) -> dict[str, object]:
    """Check whether a lab service looks recovered. Read-only."""
    return verify_recovery_impl(
        {
            "service": service,
            "namespace": namespace,
            "max_latency_ms": max_latency_ms,
            "proposal_id": proposal_id,
        },
        runtime=ToolRuntime.from_catalog("verify_recovery"),
    )


@mcp.tool()
def propose_restart_workload(
    incident_run_id: str,
    service: _Service,
    rationale: str,
    expected_effect: str,
    namespace: _Namespace = "lab",
    idempotency_key: str = "",
) -> dict[str, object]:
    """Create a restart proposal. Does not restart the workload."""
    return propose_restart_workload_impl(
        {
            "incident_run_id": incident_run_id,
            "service": service,
            "rationale": rationale,
            "expected_effect": expected_effect,
            "namespace": namespace,
            "idempotency_key": idempotency_key,
        },
        runtime=ToolRuntime.from_catalog("propose_restart_workload"),
    )


@mcp.tool()
def propose_scale_workload(
    incident_run_id: str,
    service: _Service,
    rationale: str,
    expected_effect: str,
    replicas: int,
    namespace: _Namespace = "lab",
    idempotency_key: str = "",
) -> dict[str, object]:
    """Create a scale proposal. Does not change replicas."""
    return propose_scale_workload_impl(
        {
            "incident_run_id": incident_run_id,
            "service": service,
            "rationale": rationale,
            "expected_effect": expected_effect,
            "replicas": replicas,
            "namespace": namespace,
            "idempotency_key": idempotency_key,
        },
        runtime=ToolRuntime.from_catalog("propose_scale_workload"),
    )


@mcp.tool()
def propose_rollback_deployment(
    incident_run_id: str,
    service: _Service,
    rationale: str,
    expected_effect: str,
    to_revision: str = "",
    namespace: _Namespace = "lab",
    idempotency_key: str = "",
) -> dict[str, object]:
    """Create a rollback proposal. Does not roll back the deployment."""
    return propose_rollback_deployment_impl(
        {
            "incident_run_id": incident_run_id,
            "service": service,
            "rationale": rationale,
            "expected_effect": expected_effect,
            "to_revision": to_revision,
            "namespace": namespace,
            "idempotency_key": idempotency_key,
        },
        runtime=ToolRuntime.from_catalog("propose_rollback_deployment"),
    )


@mcp.tool()
def propose_update_config(
    incident_run_id: str,
    service: _Service,
    rationale: str,
    expected_effect: str,
    key: str,
    value: str,
    namespace: _Namespace = "lab",
    idempotency_key: str = "",
) -> dict[str, object]:
    """Create a config-update proposal. Phase 4 policy rejects execution of this action."""
    return propose_update_config_impl(
        {
            "incident_run_id": incident_run_id,
            "service": service,
            "rationale": rationale,
            "expected_effect": expected_effect,
            "key": key,
            "value": value,
            "namespace": namespace,
            "idempotency_key": idempotency_key,
        },
        runtime=ToolRuntime.from_catalog("propose_update_config"),
    )


if __name__ == "__main__":
    run_streamable_http(mcp, 8004)
