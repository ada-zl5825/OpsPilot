from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class RemediationActionType(StrEnum):
    ROLLBACK_DEPLOYMENT = "rollback_deployment"
    RESTART_WORKLOAD = "restart_workload"
    SCALE_WORKLOAD = "scale_workload"
    UPDATE_CONFIG = "update_config"


class ResourceRef(BaseModel):
    kind: str
    name: str
    namespace: str = "lab"
    service: str | None = None


class DryRunResult(BaseModel):
    allowed: bool
    summary: str
    violations: list[str] = Field(default_factory=list)


class RollbackPlan(BaseModel):
    action_type: RemediationActionType
    target: ResourceRef
    parameters: dict[str, Any] = Field(default_factory=dict)
    notes: str = ""


class RemediationProposal(BaseModel):
    proposal_id: UUID
    incident_run_id: UUID
    action_type: RemediationActionType
    target: ResourceRef
    parameters: dict[str, Any] = Field(default_factory=dict)
    rationale: str
    evidence_ids: list[UUID] = Field(default_factory=list)
    expected_effect: str
    risk_level: Literal["low", "medium", "high", "critical"]
    dry_run_result: DryRunResult | None = None
    rollback_plan: RollbackPlan
    idempotency_key: str
    expires_at: datetime


class ExecutionAttempt(BaseModel):
    execution_id: UUID
    proposal_id: UUID
    status: Literal["started", "succeeded", "failed", "rolled_back"]
    command_plan: list[str]
    started_at: datetime
    ended_at: datetime | None = None
    output_ref: str | None = None
    error_code: str | None = None
