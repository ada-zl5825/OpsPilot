from __future__ import annotations

from typing import Literal

from pydantic import Field

from mcp_servers.common.schemas import ServiceName, StrictModel, azure_input_schema

Namespace = Literal["lab"]


class CapabilitiesInput(StrictModel):
    unused: str = Field(default="", max_length=1)


class ResourceSnapshotInput(StrictModel):
    service: ServiceName
    namespace: Namespace = "lab"


class DryRunInput(StrictModel):
    proposal_id: str = Field(min_length=36, max_length=36)


class VerifyRecoveryInput(StrictModel):
    service: ServiceName
    namespace: Namespace = "lab"
    max_latency_ms: int = Field(default=1500, ge=1, le=60000)
    proposal_id: str = Field(default="", max_length=36)


class ProposeRestartInput(StrictModel):
    incident_run_id: str = Field(min_length=36, max_length=36)
    service: ServiceName
    rationale: str = Field(min_length=8, max_length=500)
    expected_effect: str = Field(min_length=4, max_length=300)
    namespace: Namespace = "lab"
    idempotency_key: str = Field(default="", max_length=128)


class ProposeScaleInput(StrictModel):
    incident_run_id: str = Field(min_length=36, max_length=36)
    service: ServiceName
    rationale: str = Field(min_length=8, max_length=500)
    expected_effect: str = Field(min_length=4, max_length=300)
    replicas: int = Field(ge=1, le=10)
    namespace: Namespace = "lab"
    idempotency_key: str = Field(default="", max_length=128)


class ProposeRollbackInput(StrictModel):
    incident_run_id: str = Field(min_length=36, max_length=36)
    service: ServiceName
    rationale: str = Field(min_length=8, max_length=500)
    expected_effect: str = Field(min_length=4, max_length=300)
    to_revision: str = Field(default="", max_length=32)
    namespace: Namespace = "lab"
    idempotency_key: str = Field(default="", max_length=128)


class ProposeUpdateConfigInput(StrictModel):
    incident_run_id: str = Field(min_length=36, max_length=36)
    service: ServiceName
    rationale: str = Field(min_length=8, max_length=500)
    expected_effect: str = Field(min_length=4, max_length=300)
    key: str = Field(min_length=1, max_length=64)
    value: str = Field(min_length=1, max_length=128)
    namespace: Namespace = "lab"
    idempotency_key: str = Field(default="", max_length=128)


REMEDIATION_INPUT_SCHEMAS = {
    "get_remediation_capabilities": azure_input_schema(CapabilitiesInput),
    "get_resource_snapshot": azure_input_schema(ResourceSnapshotInput),
    "dry_run_remediation": azure_input_schema(DryRunInput),
    "verify_recovery": azure_input_schema(VerifyRecoveryInput),
    "propose_rollback_deployment": azure_input_schema(ProposeRollbackInput),
    "propose_restart_workload": azure_input_schema(ProposeRestartInput),
    "propose_scale_workload": azure_input_schema(ProposeScaleInput),
    "propose_update_config": azure_input_schema(ProposeUpdateConfigInput),
}
