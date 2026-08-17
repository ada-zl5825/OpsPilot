from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class IncidentStatus(StrEnum):
    INCIDENT_CREATED = "incident_created"
    INVESTIGATING = "investigating"
    EVIDENCE_INSUFFICIENT = "evidence_insufficient"
    ROOT_CAUSE_PROPOSED = "root_cause_proposed"
    VERIFICATION_REVIEW = "verification_review"
    DIAGNOSIS_COMPLETE = "diagnosis_complete"
    REMEDIATION_PROPOSED = "remediation_proposed"
    POLICY_REJECTED = "policy_rejected"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    RECOVERY_VERIFICATION = "recovery_verification"
    RESOLVED = "resolved"
    ROLLED_BACK = "rolled_back"
    HUMAN_ESCALATION = "human_escalation"
    CANCELLED = "cancelled"


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class Diagnosis(BaseModel):
    root_cause: str
    evidence_ids: list[UUID]
    rejected_hypotheses: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    uncertainties: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


class EvidenceExpectation(BaseModel):
    source_system: str
    description: str
    required: bool = True


class RecoveryCheck(BaseModel):
    check_id: str
    description: str
    metric_or_endpoint: str
    success_criteria: str


class RemediationTemplate(BaseModel):
    action_type: str
    description: str


class IncidentScenario(BaseModel):
    """Benchmark-only fields such as ground_truth must never enter Agent context."""

    scenario_id: str
    version: str
    title: str
    difficulty: Literal["L1", "L2", "L3", "L4", "L5"]
    initial_symptoms: list[str]
    ground_truth_root_causes: list[str]
    required_evidence: list[EvidenceExpectation]
    necessary_tool_categories: set[str]
    forbidden_shortcuts: list[str]
    allowed_remediations: list[RemediationTemplate]
    recovery_checks: list[RecoveryCheck]
    distractors: list[str]
    prompt_variants: list[str]
    verification_code: str | None = None


class IncidentRun(BaseModel):
    run_id: UUID
    scenario_id: str | None = None
    source: Literal["benchmark", "manual", "alert"]
    status: IncidentStatus
    model: str
    prompt_version: str
    tool_catalog_version: str
    started_at: datetime
    ended_at: datetime | None = None
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    estimated_cost: Decimal = Decimal("0")
    final_diagnosis: Diagnosis | None = None
