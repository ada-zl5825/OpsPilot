from __future__ import annotations

from enum import StrEnum

from opspilot.domain.incidents import IncidentStatus
from opspilot.investigation.budget import BudgetState, BudgetViolation
from opspilot.investigation.diagnosis import DiagnosisParseResult
from opspilot.investigation.progress import ProgressState


class StopReason(StrEnum):
    COMPLETED = "completed"
    BUDGET_EXHAUSTED = "budget_exhausted"
    DUPLICATE_TOOL_LIMIT = "duplicate_tool_limit"
    NO_PROGRESS = "no_progress"
    INVALID_DIAGNOSIS = "invalid_diagnosis"
    MISSING_EVIDENCE_CITATION = "missing_evidence_citation"
    NO_SUCCESSFUL_EVIDENCE = "no_successful_evidence"
    WRITE_BLOCKED = "write_blocked"
    HOLMES_ERROR = "holmes_error"
    CANCELLED = "cancelled"


_DUPLICATE_VIOLATIONS = {
    BudgetViolation.MAX_REPEATS_PER_TOOL,
    BudgetViolation.MAX_REPEATS_PER_QUERY,
}


def decide_outcome(
    *,
    parsed: DiagnosisParseResult,
    budget: BudgetState,
    progress: ProgressState,
    successful_evidence: int,
    write_blocked: bool,
    holmes_error: bool,
    cancelled: bool,
) -> tuple[IncidentStatus, StopReason]:
    if cancelled:
        return IncidentStatus.CANCELLED, StopReason.CANCELLED
    if holmes_error:
        return IncidentStatus.HUMAN_ESCALATION, StopReason.HOLMES_ERROR
    if write_blocked:
        return IncidentStatus.POLICY_REJECTED, StopReason.WRITE_BLOCKED
    if budget.exceeded:
        if _DUPLICATE_VIOLATIONS.intersection(budget.violations):
            return IncidentStatus.EVIDENCE_INSUFFICIENT, StopReason.DUPLICATE_TOOL_LIMIT
        return IncidentStatus.EVIDENCE_INSUFFICIENT, StopReason.BUDGET_EXHAUSTED
    if progress.no_progress and not parsed.valid:
        return IncidentStatus.EVIDENCE_INSUFFICIENT, StopReason.NO_PROGRESS
    if successful_evidence == 0:
        return IncidentStatus.EVIDENCE_INSUFFICIENT, StopReason.NO_SUCCESSFUL_EVIDENCE
    if parsed.valid:
        return IncidentStatus.DIAGNOSIS_COMPLETE, StopReason.COMPLETED
    if parsed.draft is not None:
        return IncidentStatus.EVIDENCE_INSUFFICIENT, StopReason.MISSING_EVIDENCE_CITATION
    return IncidentStatus.EVIDENCE_INSUFFICIENT, StopReason.INVALID_DIAGNOSIS


def is_successful_status(status: IncidentStatus) -> bool:
    return status is IncidentStatus.DIAGNOSIS_COMPLETE
