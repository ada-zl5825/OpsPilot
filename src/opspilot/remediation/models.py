from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from opspilot.domain.approvals import ApprovalDecision
from opspilot.domain.remediation import (
    DryRunResult,
    ExecutionAttempt,
    ProposalStatus,
    RemediationProposal,
)
from opspilot.executor.cluster import WorkloadSnapshot
from opspilot.verification.recovery import RecoveryReport


class AuditEvent(BaseModel):
    timestamp: datetime
    action: str
    actor_id: str
    actor_role: str
    proposal_id: UUID
    digest: str
    result: str
    error_code: str | None = None
    detail: str = ""
    target: dict[str, Any] = Field(default_factory=dict)


class ProposalRecord(BaseModel):
    proposal: RemediationProposal
    digest: str
    status: ProposalStatus
    approval: ApprovalDecision | None = None
    executions: list[ExecutionAttempt] = Field(default_factory=list)
    created_at: datetime
    pre_execution_snapshot: WorkloadSnapshot | None = None
    last_command: dict[str, Any] | None = None
    recovery: RecoveryReport | None = None
    audit: list[AuditEvent] = Field(default_factory=list)

    @property
    def dry_run_result(self) -> DryRunResult | None:
        return self.proposal.dry_run_result

    def succeeded(self) -> bool:
        return any(item.status == "succeeded" for item in self.executions)
