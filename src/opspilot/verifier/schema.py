from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, model_validator

from opspilot.investigation.diagnosis import (
    DiagnosisDraft,
    HypothesisDraft,
    extract_json_object,
)
from opspilot.investigation.prompt import AgentVisibleIncident
from opspilot.verifier.constants import INVESTIGATOR_SCHEMA_VERSION, VERIFIER_SCHEMA_VERSION


class SharedBudgetSnapshot(BaseModel):
    """Investigator and Verifier share one tool/step budget. Follow-up is at most once."""

    max_tool_calls: int
    tool_calls_used: int
    remaining_tool_calls: int
    max_steps: int
    steps_used: int
    remaining_steps: int
    max_followups: int = 1
    followups_used: int = 0
    remaining_followups: int = 1


class EvidenceBundleItem(BaseModel):
    """Successful tool evidence only. Failed results never enter the handoff."""

    evidence_id: str
    source_tool: str
    source_system: str
    query_fingerprint: str
    summary: str


class InvestigatorBundle(BaseModel):
    """Schema handoff from Investigator to Verifier. Not a free-form chat message."""

    schema_version: str = INVESTIGATOR_SCHEMA_VERSION
    scenario_id: str
    incident: AgentVisibleIncident
    diagnosis: DiagnosisDraft | None = None
    evidence: list[EvidenceBundleItem] = Field(default_factory=list)
    hypotheses: list[HypothesisDraft] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    rejected_hypotheses: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    budget: SharedBudgetSnapshot
    followup_used: bool = False

    @model_validator(mode="after")
    def _bundle_excludes_scorer_fields(self) -> InvestigatorBundle:
        dumped = self.model_dump()
        if "ground_truth_root_causes" in dumped:
            raise ValueError("investigator bundle must not carry ground truth")
        if "verification_code" in dumped:
            raise ValueError("investigator bundle must not carry verification codes")
        return self


class FollowupRequest(BaseModel):
    reason: str
    missing_checks: list[str] = Field(default_factory=list)
    suggested_tools: list[str] = Field(default_factory=list)
    suggested_params: list[dict[str, Any]] = Field(default_factory=list)


class VerifierVerdict(BaseModel):
    schema_version: str = VERIFIER_SCHEMA_VERSION
    decision: Literal["accept", "request_followup", "reject"]
    evidence_supports_conclusion: bool
    unsupported_claims: list[str] = Field(default_factory=list)
    counterexamples: list[str] = Field(default_factory=list)
    remediation_consistent: bool = True
    safety_ok: bool = True
    followup: FollowupRequest | None = None
    revised_root_cause: str | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _decision_matches_payload(self) -> VerifierVerdict:
        if self.decision == "request_followup" and self.followup is None:
            raise ValueError("request_followup requires a followup object")
        if self.decision == "accept" and not self.evidence_supports_conclusion:
            raise ValueError("accept requires evidence_supports_conclusion")
        if self.decision == "accept" and not self.safety_ok:
            raise ValueError("accept requires safety_ok")
        return self


def parse_verdict(text: str | None) -> VerifierVerdict | None:
    if not text or not text.strip():
        return None
    payload = extract_json_object(text)
    if payload is None:
        return None
    try:
        return VerifierVerdict.model_validate(payload)
    except ValidationError:
        return None
