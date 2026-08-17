from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from pydantic import BaseModel, Field

from opspilot.domain.evidence import Evidence, Hypothesis
from opspilot.domain.incidents import Diagnosis, IncidentRun, IncidentStatus, TokenUsage
from opspilot.investigation.budget import BudgetState, ToolBudget, evaluate_budget
from opspilot.investigation.diagnosis import DiagnosisParseResult, parse_and_bind_diagnosis
from opspilot.investigation.evidence import collect_evidence
from opspilot.investigation.outcome import StopReason, decide_outcome, is_successful_status
from opspilot.investigation.progress import ProgressState, evaluate_progress
from opspilot.investigation.store import InvestigationStore
from opspilot.telemetry.events import AgentEvent, AgentEventType


class ReplayResult(BaseModel):
    run: IncidentRun
    events: list[AgentEvent] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    budget: BudgetState
    progress: ProgressState
    parsed: DiagnosisParseResult
    status: IncidentStatus
    stop_reason: StopReason
    diagnosis: Diagnosis | None = None

    @property
    def successful(self) -> bool:
        return is_successful_status(self.status)


def last_analysis(events: Sequence[AgentEvent]) -> str | None:
    analysis: str | None = None
    for event in events:
        if event.event_type is AgentEventType.LLM_END:
            value = event.payload.get("analysis")
            if isinstance(value, str):
                analysis = value
    return analysis


def replay_events(
    run: IncidentRun,
    events: Sequence[AgentEvent],
    budget: ToolBudget,
    *,
    write_blocked: bool = False,
    holmes_error: bool = False,
    cancelled: bool = False,
) -> ReplayResult:
    ordered = sorted(events, key=lambda item: item.sequence)
    evidence = collect_evidence(run.run_id, ordered)
    usage = run.token_usage if run.token_usage.total_tokens else TokenUsage()
    llm_ends = sum(1 for event in ordered if event.event_type is AgentEventType.LLM_END)
    steps_used = max(run_steps_from_events(ordered), llm_ends, 1 if ordered else 0)
    budget_state = evaluate_budget(ordered, budget, steps_used=steps_used, token_usage=usage)
    progress = evaluate_progress(ordered, evidence, budget)
    parsed = parse_and_bind_diagnosis(last_analysis(ordered), evidence)
    status, stop_reason = decide_outcome(
        parsed=parsed,
        budget=budget_state,
        progress=progress,
        successful_evidence=len(evidence),
        write_blocked=write_blocked,
        holmes_error=holmes_error,
        cancelled=cancelled,
    )
    diagnosis = parsed.diagnosis if status is IncidentStatus.DIAGNOSIS_COMPLETE else None
    return ReplayResult(
        run=run,
        events=list(ordered),
        evidence=evidence,
        hypotheses=parsed.hypotheses if diagnosis is not None else [],
        budget=budget_state,
        progress=progress,
        parsed=parsed,
        status=status,
        stop_reason=stop_reason,
        diagnosis=diagnosis,
    )


def run_steps_from_events(events: Sequence[AgentEvent]) -> int:
    return sum(1 for event in events if event.event_type is AgentEventType.LLM_END)


def replay_store(
    store: InvestigationStore,
    run_id: UUID,
    budget: ToolBudget | None = None,
) -> ReplayResult:
    run = store.get_run(run_id)
    if run is None:
        raise KeyError(run_id)
    events = store.list_events(run_id)
    write_blocked = run.status is IncidentStatus.POLICY_REJECTED
    holmes_error = run.status is IncidentStatus.HUMAN_ESCALATION
    cancelled = run.status is IncidentStatus.CANCELLED
    result = replay_events(
        run,
        events,
        budget or ToolBudget(),
        write_blocked=write_blocked,
        holmes_error=holmes_error,
        cancelled=cancelled,
    )
    stored_success = is_successful_status(run.status)
    replayed_success = result.successful
    if stored_success and not replayed_success:
        raise ValueError("stored run marked success but replay did not confirm it")
    return result
