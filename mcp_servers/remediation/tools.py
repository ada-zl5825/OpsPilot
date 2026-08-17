from __future__ import annotations

from typing import Any
from uuid import UUID

from mcp_servers.common.errors import structured_error
from mcp_servers.common.runtime import ToolRuntime, invoke_tool
from mcp_servers.common.validation import parse_model, validation_failure
from mcp_servers.contracts import agent_visible_tools, mutate_tools
from mcp_servers.remediation.plane import get_plane
from mcp_servers.remediation.schemas import (
    CapabilitiesInput,
    DryRunInput,
    ProposeRestartInput,
    ProposeRollbackInput,
    ProposeScaleInput,
    ProposeUpdateConfigInput,
    ResourceSnapshotInput,
    VerifyRecoveryInput,
)
from opspilot.domain.remediation import ProposalStatus, RemediationActionType
from opspilot.remediation.errors import RemediationError
from opspilot.remediation.models import ProposalRecord
from opspilot.remediation.service import ControlPlane


def get_remediation_capabilities(
    params: dict[str, Any] | None = None,
    *,
    runtime: ToolRuntime | None = None,
) -> dict[str, Any]:
    tool = "get_remediation_capabilities"
    runtime = runtime or ToolRuntime.from_catalog(tool)
    try:
        parse_model(CapabilitiesInput, params or {})
    except Exception as exc:
        return validation_failure(tool, exc, params or {})

    def _run() -> dict[str, Any]:
        return {
            "ok": True,
            "tool": tool,
            "actions": ["rollback_deployment", "restart_workload", "scale_workload"],
            "namespaces": ["lab"],
            "services": ["gateway", "checkout", "payment", "inventory", "notification"],
            "agent_visible_tools": [
                item["name"] for item in agent_visible_tools() if item["server"] == "remediation"
            ],
            "mutate_tools_agent_visible": False,
            "control_plane_only_count": len(list(mutate_tools())),
        }

    return invoke_tool(tool, _run, runtime, params=params or {})


def get_resource_snapshot(
    params: dict[str, Any],
    *,
    plane: ControlPlane | None = None,
    runtime: ToolRuntime | None = None,
) -> dict[str, Any]:
    tool = "get_resource_snapshot"
    runtime = runtime or ToolRuntime.from_catalog(tool)
    try:
        parsed = parse_model(ResourceSnapshotInput, params)
    except Exception as exc:
        return validation_failure(tool, exc, params)
    plane = plane or get_plane()

    def _run() -> dict[str, Any]:
        snapshot = plane.cluster.snapshot(parsed.service, parsed.namespace)
        return {
            "ok": True,
            "tool": tool,
            "snapshot": snapshot.model_dump(mode="json"),
        }

    return invoke_tool(tool, _run, runtime, params=parsed.model_dump())


def dry_run_remediation(
    params: dict[str, Any],
    *,
    plane: ControlPlane | None = None,
    runtime: ToolRuntime | None = None,
) -> dict[str, Any]:
    tool = "dry_run_remediation"
    runtime = runtime or ToolRuntime.from_catalog(tool)
    try:
        parsed = parse_model(DryRunInput, params)
        proposal_id = UUID(parsed.proposal_id)
    except Exception as exc:
        return validation_failure(tool, exc, params)
    plane = plane or get_plane()

    def _run() -> dict[str, Any]:
        result = plane.dry_run(proposal_id)
        return {"ok": True, "tool": tool, "proposal_id": parsed.proposal_id, **result.model_dump()}

    return _invoke_plane(tool, _run, runtime, parsed.model_dump())


def verify_recovery(
    params: dict[str, Any],
    *,
    plane: ControlPlane | None = None,
    runtime: ToolRuntime | None = None,
) -> dict[str, Any]:
    tool = "verify_recovery"
    runtime = runtime or ToolRuntime.from_catalog(tool)
    try:
        parsed = parse_model(VerifyRecoveryInput, params)
        proposal_id = UUID(parsed.proposal_id) if parsed.proposal_id else None
    except Exception as exc:
        return validation_failure(tool, exc, params)
    plane = plane or get_plane()

    def _run() -> dict[str, Any]:
        report = plane.verify(
            proposal_id,
            service=parsed.service,
            namespace=parsed.namespace,
            max_latency_ms=parsed.max_latency_ms,
        )
        return {"ok": True, "tool": tool, **report.model_dump(mode="json")}

    return _invoke_plane(tool, _run, runtime, parsed.model_dump())


def propose_restart_workload(
    params: dict[str, Any],
    *,
    plane: ControlPlane | None = None,
    runtime: ToolRuntime | None = None,
) -> dict[str, Any]:
    return _propose(
        "propose_restart_workload",
        ProposeRestartInput,
        RemediationActionType.RESTART_WORKLOAD,
        params,
        plane=plane,
        runtime=runtime,
    )


def propose_scale_workload(
    params: dict[str, Any],
    *,
    plane: ControlPlane | None = None,
    runtime: ToolRuntime | None = None,
) -> dict[str, Any]:
    return _propose(
        "propose_scale_workload",
        ProposeScaleInput,
        RemediationActionType.SCALE_WORKLOAD,
        params,
        plane=plane,
        runtime=runtime,
        extra=lambda parsed: {"replicas": parsed.replicas},
    )


def propose_rollback_deployment(
    params: dict[str, Any],
    *,
    plane: ControlPlane | None = None,
    runtime: ToolRuntime | None = None,
) -> dict[str, Any]:
    return _propose(
        "propose_rollback_deployment",
        ProposeRollbackInput,
        RemediationActionType.ROLLBACK_DEPLOYMENT,
        params,
        plane=plane,
        runtime=runtime,
        extra=lambda parsed: {"to_revision": parsed.to_revision} if parsed.to_revision else {},
    )


def propose_update_config(
    params: dict[str, Any],
    *,
    plane: ControlPlane | None = None,
    runtime: ToolRuntime | None = None,
) -> dict[str, Any]:
    return _propose(
        "propose_update_config",
        ProposeUpdateConfigInput,
        RemediationActionType.UPDATE_CONFIG,
        params,
        plane=plane,
        runtime=runtime,
        extra=lambda parsed: {"key": parsed.key, "value": parsed.value},
    )


def _propose(
    tool: str,
    model: type[Any],
    action_type: RemediationActionType,
    params: dict[str, Any],
    *,
    plane: ControlPlane | None,
    runtime: ToolRuntime | None,
    extra: Any = None,
) -> dict[str, Any]:
    runtime = runtime or ToolRuntime.from_catalog(tool)
    try:
        parsed = parse_model(model, params)
        run_id = UUID(parsed.incident_run_id)
    except Exception as exc:
        return validation_failure(tool, exc, params)
    plane = plane or get_plane()
    parameters = extra(parsed) if extra is not None else {}

    def _run() -> dict[str, Any]:
        record = plane.propose(
            incident_run_id=run_id,
            action_type=action_type,
            service=parsed.service,
            namespace=parsed.namespace,
            parameters=parameters,
            rationale=parsed.rationale,
            expected_effect=parsed.expected_effect,
            idempotency_key=parsed.idempotency_key,
        )
        return _proposal_payload(tool, record)

    return _invoke_plane(tool, _run, runtime, parsed.model_dump())


def _proposal_payload(tool: str, record: ProposalRecord) -> dict[str, Any]:
    return {
        "ok": True,
        "tool": tool,
        "proposal_id": str(record.proposal.proposal_id),
        "digest": record.digest,
        "status": record.status.value,
        "action_type": record.proposal.action_type.value,
        "expires_at": record.proposal.expires_at.isoformat(),
        "policy_allowed": record.status is not ProposalStatus.POLICY_REJECTED,
        "executed": False,
        "write_performed": False,
    }


def _invoke_plane(
    tool: str,
    handler: Any,
    runtime: ToolRuntime,
    params: dict[str, Any],
) -> dict[str, Any]:
    def _wrapped() -> dict[str, Any]:
        try:
            return handler()
        except RemediationError as exc:
            error_type = "not_found" if exc.code == "not_found" else "validation"
            return structured_error(
                tool,
                error_type=error_type,
                message=exc.message,
                retryable=False,
                suggested_fix="create a new typed proposal or approve the current digest",
                params=params,
            )

    return invoke_tool(tool, _wrapped, runtime, params=params)
