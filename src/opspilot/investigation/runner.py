from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Literal, Protocol
from uuid import UUID, uuid4

import httpx
from pydantic import BaseModel, Field

from opspilot.domain.evidence import Evidence, Hypothesis
from opspilot.domain.incidents import IncidentRun, IncidentStatus, TokenUsage
from opspilot.holmes.client import HolmesAskResult
from opspilot.investigation.budget import BudgetState, ToolBudget, evaluate_budget
from opspilot.investigation.constants import (
    MUTATE_TOOLS,
    PROMPT_VERSION,
    TOOL_CATALOG_VERSION,
)
from opspilot.investigation.diagnosis import DiagnosisParseResult, parse_and_bind_diagnosis
from opspilot.investigation.evidence import collect_evidence, format_evidence_line, tool_name_of
from opspilot.investigation.outcome import StopReason, decide_outcome, is_successful_status
from opspilot.investigation.progress import ProgressState, evaluate_progress
from opspilot.investigation.prompt import (
    build_diagnosis_followup,
    build_investigation_prompt,
    to_agent_visible,
)
from opspilot.investigation.safety import assert_no_ground_truth
from opspilot.investigation.store import InvestigationStore
from opspilot.lab.scenarios import scenario_by_id
from opspilot.logging import get_logger
from opspilot.settings import Settings, get_settings
from opspilot.telemetry.events import AgentEvent, AgentEventType
from opspilot.telemetry.tracing import investigation_span

logger = get_logger("opspilot.investigation")


class HolmesAskPort(Protocol):
    async def ask(
        self,
        prompt: str,
        *,
        extra: dict[str, Any] | None = None,
        enable_tool_approval: bool = True,
        model: str | None = None,
        conversation_history: list[dict[str, Any]] | None = None,
        tool_decisions: Sequence[Any] | None = None,
        run_id: UUID | None = None,
    ) -> HolmesAskResult: ...

    async def reject_pending(self, result: HolmesAskResult) -> HolmesAskResult: ...


class InvestigationResult(BaseModel):
    run: IncidentRun
    events: list[AgentEvent] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    prompt: str
    followup_prompts: list[str] = Field(default_factory=list)
    budget: BudgetState
    progress: ProgressState
    parsed: DiagnosisParseResult
    stop_reason: StopReason
    analysis: str | None = None

    @property
    def successful(self) -> bool:
        return is_successful_status(self.run.status)


class InvestigationRunner:
    def __init__(
        self,
        client: HolmesAskPort,
        store: InvestigationStore,
        *,
        settings: Settings | None = None,
        budget: ToolBudget | None = None,
    ) -> None:
        self._client = client
        self._store = store
        self._settings = settings or get_settings()
        self._budget = budget or ToolBudget()

    async def run(
        self,
        scenario_id: str,
        *,
        source: Literal["benchmark", "manual", "alert"] = "benchmark",
        run_id: UUID | None = None,
        model: str | None = None,
        user_report: str | None = None,
    ) -> InvestigationResult:
        scenario = scenario_by_id(scenario_id)
        visible = to_agent_visible(scenario, user_report=user_report)
        prompt = build_investigation_prompt(visible, self._budget)
        assert_no_ground_truth(prompt, scenario)

        run = IncidentRun(
            run_id=run_id or uuid4(),
            scenario_id=scenario.scenario_id,
            source=source,
            status=IncidentStatus.INVESTIGATING,
            model=model or self._settings.holmes_model,
            prompt_version=PROMPT_VERSION,
            tool_catalog_version=TOOL_CATALOG_VERSION,
            started_at=datetime.now(UTC),
        )
        self._store.save_run(run)

        events: list[AgentEvent] = []
        followups: list[str] = []
        history: list[dict[str, Any]] | None = None
        analysis: str | None = None
        usage = TokenUsage()
        write_blocked = False
        holmes_error = False
        cancelled = False

        with investigation_span(
            "incident.run",
            run_id=str(run.run_id),
            scenario_id=scenario.scenario_id,
        ):
            try:
                for step in range(1, self._budget.max_steps + 1):
                    current = self._store.get_run(run.run_id)
                    if current is not None and current.status is IncidentStatus.CANCELLED:
                        cancelled = True
                        break

                    ask_prompt = prompt
                    if step > 1:
                        evidence_so_far = collect_evidence(run.run_id, events)
                        ask_prompt = build_diagnosis_followup(
                            [format_evidence_line(item) for item in evidence_so_far]
                        )
                        followups.append(ask_prompt)
                        assert_no_ground_truth(ask_prompt, scenario)

                    with investigation_span("holmes.investigation", step=str(step)):
                        result = await self._client.ask(
                            ask_prompt,
                            conversation_history=history,
                            run_id=run.run_id,
                        )
                    turn = _resequence(result.events, run.run_id, start=len(events) + 1)
                    events.extend(turn)
                    self._store.append_events(turn)
                    if result.conversation_history:
                        history = result.conversation_history
                    analysis = result.analysis or analysis
                    usage = _add_usage(usage, result.token_usage)

                    if _write_blocked(result):
                        write_blocked = True
                        if result.pending_approvals:
                            await self._client.reject_pending(result)
                        logger.info(
                            "investigation_write_blocked",
                            run_id=str(run.run_id),
                            pending=[item.tool_name for item in result.pending_approvals],
                        )
                        break
                    if any(event.event_type is AgentEventType.ERROR for event in turn):
                        holmes_error = True
                        break

                    snapshot = _evaluate(
                        run,
                        events,
                        analysis,
                        usage,
                        self._budget,
                        steps_used=step,
                    )
                    if (
                        snapshot.budget.exceeded
                        or snapshot.parsed.valid
                        or snapshot.progress.no_progress
                    ):
                        break
            except httpx.HTTPError:
                logger.exception("investigation_holmes_http_error", run_id=str(run.run_id))
                holmes_error = True

        snapshot = _evaluate(
            run,
            events,
            analysis,
            usage,
            self._budget,
            steps_used=max(
                1, sum(1 for event in events if event.event_type is AgentEventType.LLM_END)
            ),
        )
        status, stop_reason = decide_outcome(
            parsed=snapshot.parsed,
            budget=snapshot.budget,
            progress=snapshot.progress,
            successful_evidence=len(snapshot.evidence),
            write_blocked=write_blocked,
            holmes_error=holmes_error,
            cancelled=cancelled,
        )
        if status is IncidentStatus.DIAGNOSIS_COMPLETE and snapshot.parsed.diagnosis is None:
            status = IncidentStatus.EVIDENCE_INSUFFICIENT
            stop_reason = StopReason.INVALID_DIAGNOSIS

        run.status = status
        run.token_usage = usage
        run.estimated_cost = snapshot.budget.estimated_cost
        run.ended_at = datetime.now(UTC)
        run.final_diagnosis = (
            snapshot.parsed.diagnosis if status is IncidentStatus.DIAGNOSIS_COMPLETE else None
        )
        hypotheses = snapshot.parsed.hypotheses if run.final_diagnosis is not None else []
        self._store.replace_evidence(run.run_id, snapshot.evidence)
        self._store.replace_hypotheses(run.run_id, hypotheses)
        self._store.save_run(run)

        if is_successful_status(run.status):
            if run.final_diagnosis is None or not run.final_diagnosis.evidence_ids:
                raise RuntimeError(
                    "refusing to mark investigation success without evidence-backed diagnosis"
                )
            if write_blocked or holmes_error or cancelled or snapshot.budget.exceeded:
                raise RuntimeError("refusing to mark investigation success after a failed control")

        logger.info(
            "investigation_end",
            run_id=str(run.run_id),
            scenario_id=scenario.scenario_id,
            status=run.status.value,
            stop_reason=stop_reason.value,
            evidence=len(snapshot.evidence),
            successful=is_successful_status(run.status),
        )
        return InvestigationResult(
            run=run,
            events=events,
            evidence=snapshot.evidence,
            hypotheses=hypotheses,
            prompt=prompt,
            followup_prompts=followups,
            budget=snapshot.budget,
            progress=snapshot.progress,
            parsed=snapshot.parsed,
            stop_reason=stop_reason,
            analysis=analysis,
        )


class _Snapshot(BaseModel):
    evidence: list[Evidence]
    budget: BudgetState
    progress: ProgressState
    parsed: DiagnosisParseResult


def _evaluate(
    run: IncidentRun,
    events: Sequence[AgentEvent],
    analysis: str | None,
    usage: TokenUsage,
    budget: ToolBudget,
    *,
    steps_used: int,
) -> _Snapshot:
    evidence = collect_evidence(run.run_id, events)
    budget_state = evaluate_budget(events, budget, steps_used=steps_used, token_usage=usage)
    progress = evaluate_progress(events, evidence, budget)
    parsed = parse_and_bind_diagnosis(analysis, evidence)
    return _Snapshot(evidence=evidence, budget=budget_state, progress=progress, parsed=parsed)


def _resequence(events: Sequence[AgentEvent], run_id: UUID, *, start: int) -> list[AgentEvent]:
    rewritten: list[AgentEvent] = []
    for offset, event in enumerate(events):
        rewritten.append(event.model_copy(update={"run_id": run_id, "sequence": start + offset}))
    return rewritten


def _add_usage(left: TokenUsage, right: TokenUsage) -> TokenUsage:
    return TokenUsage(
        input_tokens=left.input_tokens + right.input_tokens,
        output_tokens=left.output_tokens + right.output_tokens,
        total_tokens=left.total_tokens + right.total_tokens,
    )


def _write_blocked(result: HolmesAskResult) -> bool:
    if result.unapproved_write_attempted:
        return True
    if any(item.tool_name in MUTATE_TOOLS for item in result.pending_approvals):
        return True
    for event in result.events:
        name = tool_name_of(event)
        if name in MUTATE_TOOLS:
            return True
        if event.event_type is AgentEventType.APPROVAL_REQUIRED:
            pending = event.payload.get("pending_approvals") or []
            for item in pending:
                if isinstance(item, dict) and str(item.get("tool_name")) in MUTATE_TOOLS:
                    return True
    return False


def create_incident_run(
    store: InvestigationStore,
    *,
    scenario_id: str | None,
    source: Literal["benchmark", "manual", "alert"],
    model: str,
    run_id: UUID | None = None,
) -> IncidentRun:
    run = IncidentRun(
        run_id=run_id or uuid4(),
        scenario_id=scenario_id,
        source=source,
        status=IncidentStatus.INCIDENT_CREATED,
        model=model,
        prompt_version=PROMPT_VERSION,
        tool_catalog_version=TOOL_CATALOG_VERSION,
        started_at=datetime.now(UTC),
    )
    store.save_run(run)
    return run


def cancel_incident_run(store: InvestigationStore, run_id: UUID) -> IncidentRun:
    run = store.get_run(run_id)
    if run is None:
        raise KeyError(run_id)
    if run.status in {
        IncidentStatus.DIAGNOSIS_COMPLETE,
        IncidentStatus.CANCELLED,
        IncidentStatus.RESOLVED,
    }:
        raise ValueError(f"cannot cancel run in status {run.status.value}")
    run.status = IncidentStatus.CANCELLED
    run.ended_at = datetime.now(UTC)
    store.save_run(run)
    return run
