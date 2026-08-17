from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

import httpx
from pydantic import BaseModel, Field

from opspilot.domain.evidence import Evidence, Hypothesis
from opspilot.domain.incidents import IncidentRun, IncidentScenario, IncidentStatus, TokenUsage
from opspilot.holmes.client import HolmesAskResult
from opspilot.investigation.budget import BudgetState, ToolBudget, evaluate_budget
from opspilot.investigation.constants import MUTATE_TOOLS
from opspilot.investigation.diagnosis import DiagnosisParseResult, parse_and_bind_diagnosis
from opspilot.investigation.evidence import collect_evidence, tool_name_of
from opspilot.investigation.outcome import StopReason, decide_outcome, is_successful_status
from opspilot.investigation.progress import evaluate_progress
from opspilot.investigation.prompt import to_agent_visible
from opspilot.investigation.roles import VERIFIER_ROLE
from opspilot.investigation.runner import HolmesAskPort, InvestigationResult, InvestigationRunner
from opspilot.investigation.store import InvestigationStore
from opspilot.lab.scenarios import scenario_by_id
from opspilot.logging import get_logger
from opspilot.settings import Settings, get_settings
from opspilot.telemetry.events import AgentEvent, AgentEventType
from opspilot.telemetry.tracing import investigation_span
from opspilot.verifier.budget import investigator_steps_used
from opspilot.verifier.bundle import build_bundle
from opspilot.verifier.policy import enforce_verdict
from opspilot.verifier.prompt import (
    assert_followup_prompt_safe,
    assert_verifier_template_safe,
    build_followup_prompt,
    build_verifier_prompt,
)
from opspilot.verifier.schema import InvestigatorBundle, VerifierVerdict, parse_verdict

logger = get_logger("opspilot.verifier")

_SKIP_VERIFIER = {
    StopReason.WRITE_BLOCKED,
    StopReason.HOLMES_ERROR,
    StopReason.CANCELLED,
    StopReason.BUDGET_EXHAUSTED,
    StopReason.DUPLICATE_TOOL_LIMIT,
}


class VerifierResult(BaseModel):
    investigation: InvestigationResult
    bundle: InvestigatorBundle
    verdicts: list[VerifierVerdict] = Field(default_factory=list)
    followup_used: bool = False
    followup_prompt: str | None = None
    verifier_prompts: list[str] = Field(default_factory=list)
    run: IncidentRun
    events: list[AgentEvent] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    budget: BudgetState
    parsed: DiagnosisParseResult
    stop_reason: StopReason
    analysis: str | None = None

    @property
    def successful(self) -> bool:
        return is_successful_status(self.run.status)


class VerifierRunner:
    def __init__(
        self,
        client: HolmesAskPort,
        store: InvestigationStore,
        *,
        settings: Settings | None = None,
        budget: ToolBudget | None = None,
        investigator: InvestigationRunner | None = None,
    ) -> None:
        self._client = client
        self._store = store
        self._settings = settings or get_settings()
        self._budget = budget or ToolBudget()
        self._investigator = investigator or InvestigationRunner(
            client,
            store,
            settings=self._settings,
            budget=self._budget,
        )

    async def run(
        self,
        scenario_id: str,
        *,
        source: Literal["benchmark", "manual", "alert"] = "benchmark",
        run_id: UUID | None = None,
        model: str | None = None,
        user_report: str | None = None,
    ) -> VerifierResult:
        investigation = await self._investigator.run(
            scenario_id,
            source=source,
            run_id=run_id,
            model=model,
            user_report=user_report,
        )
        scenario = scenario_by_id(scenario_id)
        visible = to_agent_visible(scenario, user_report=user_report)
        events = list(investigation.events)
        usage = investigation.run.token_usage
        followup_prompt: str | None = None
        verifier_prompts: list[str] = []
        verdicts: list[VerifierVerdict] = []
        followups_used = 0
        write_blocked = investigation.stop_reason is StopReason.WRITE_BLOCKED
        holmes_error = investigation.stop_reason is StopReason.HOLMES_ERROR
        cancelled = investigation.stop_reason is StopReason.CANCELLED
        analysis = investigation.analysis

        bundle = build_bundle(
            visible=visible,
            result=investigation,
            budget=self._budget,
            followups_used=0,
        )

        if investigation.stop_reason in _SKIP_VERIFIER:
            return self._finalize(
                investigation=investigation,
                bundle=bundle,
                verdicts=verdicts,
                followup_used=False,
                followup_prompt=None,
                verifier_prompts=verifier_prompts,
                events=events,
                usage=usage,
                analysis=analysis,
                write_blocked=write_blocked,
                holmes_error=holmes_error,
                cancelled=cancelled,
                verifier_decision=None,
            )

        with investigation_span(
            "verifier.review",
            run_id=str(investigation.run.run_id),
            scenario_id=scenario.scenario_id,
        ):
            try:
                first = await self._review(bundle, scenario, events)
                verifier_prompts.append(first.prompt)
                events.extend(first.events)
                usage = _add_usage(usage, first.usage)
                if first.write_blocked:
                    write_blocked = True
                elif first.holmes_error:
                    holmes_error = True
                elif first.verdict is not None:
                    applied = enforce_verdict(first.verdict, bundle)
                    verdicts.append(applied.verdict)
                    if applied.verdict.decision == "request_followup" and applied.verdict.followup:
                        followup_prompt = build_followup_prompt(
                            visible,
                            bundle,
                            applied.verdict.followup,
                            self._budget,
                        )
                        assert_followup_prompt_safe(
                            followup_prompt,
                            bundle,
                            applied.verdict.followup,
                            scenario,
                        )
                        follow = await self._followup(
                            followup_prompt,
                            investigation.run.run_id,
                            start=len(events) + 1,
                        )
                        events.extend(follow.events)
                        usage = _add_usage(usage, follow.usage)
                        followups_used = 1
                        if follow.write_blocked:
                            write_blocked = True
                        elif follow.holmes_error:
                            holmes_error = True
                        else:
                            analysis = follow.analysis or analysis
                            investigation = _refresh_investigation(
                                investigation,
                                events=events,
                                analysis=analysis,
                                usage=usage,
                                budget=self._budget,
                            )
                            bundle = build_bundle(
                                visible=visible,
                                result=investigation,
                                budget=self._budget,
                                followups_used=followups_used,
                            )
                            second = await self._review(bundle, scenario, events)
                            verifier_prompts.append(second.prompt)
                            events.extend(second.events)
                            usage = _add_usage(usage, second.usage)
                            if second.write_blocked:
                                write_blocked = True
                            elif second.holmes_error:
                                holmes_error = True
                            elif second.verdict is not None:
                                forced = second.verdict
                                if forced.decision == "request_followup":
                                    forced = forced.model_copy(
                                        update={
                                            "decision": (
                                                "accept"
                                                if forced.evidence_supports_conclusion
                                                and forced.safety_ok
                                                and bundle.evidence
                                                else "reject"
                                            ),
                                            "followup": None,
                                            "notes": [
                                                *forced.notes,
                                                "second follow-up is not allowed",
                                            ],
                                        }
                                    )
                                applied = enforce_verdict(forced, bundle)
                                verdicts.append(applied.verdict)
            except httpx.HTTPError:
                logger.exception(
                    "verifier_holmes_http_error",
                    run_id=str(investigation.run.run_id),
                )
                holmes_error = True

        investigation = _refresh_investigation(
            investigation,
            events=events,
            analysis=analysis,
            usage=usage,
            budget=self._budget,
        )
        bundle = build_bundle(
            visible=visible,
            result=investigation,
            budget=self._budget,
            followups_used=followups_used,
        )
        return self._finalize(
            investigation=investigation,
            bundle=bundle,
            verdicts=verdicts,
            followup_used=followups_used > 0,
            followup_prompt=followup_prompt,
            verifier_prompts=verifier_prompts,
            events=events,
            usage=usage,
            analysis=analysis,
            write_blocked=write_blocked,
            holmes_error=holmes_error,
            cancelled=cancelled,
            verifier_decision=verdicts[-1].decision if verdicts else None,
        )

    async def _review(
        self,
        bundle: InvestigatorBundle,
        scenario: IncidentScenario,
        events: Sequence[AgentEvent],
    ) -> _AskTurn:
        prompt = build_verifier_prompt(bundle)
        assert_verifier_template_safe(bundle, scenario)
        result = await self._client.ask(
            prompt,
            conversation_history=None,
            run_id=events[0].run_id if events else None,
        )
        run_id = events[0].run_id if events else result.run_id
        turn = _resequence(result.events, run_id, start=len(events) + 1, role=VERIFIER_ROLE)
        self._store.append_events(turn)
        write_blocked = _write_blocked(result)
        if write_blocked and result.pending_approvals:
            await self._client.reject_pending(result)
        holmes_error = any(event.event_type is AgentEventType.ERROR for event in turn)
        return _AskTurn(
            prompt=prompt,
            events=turn,
            usage=result.token_usage,
            analysis=result.analysis,
            verdict=parse_verdict(result.analysis),
            write_blocked=write_blocked,
            holmes_error=holmes_error,
        )

    async def _followup(
        self,
        prompt: str,
        run_id: UUID,
        *,
        start: int,
    ) -> _AskTurn:
        result = await self._client.ask(prompt, conversation_history=None, run_id=run_id)
        turn = _resequence(result.events, run_id, start=start, role=None)
        self._store.append_events(turn)
        write_blocked = _write_blocked(result)
        if write_blocked and result.pending_approvals:
            await self._client.reject_pending(result)
        holmes_error = any(event.event_type is AgentEventType.ERROR for event in turn)
        return _AskTurn(
            prompt=prompt,
            events=turn,
            usage=result.token_usage,
            analysis=result.analysis,
            verdict=None,
            write_blocked=write_blocked,
            holmes_error=holmes_error,
        )

    def _finalize(
        self,
        *,
        investigation: InvestigationResult,
        bundle: InvestigatorBundle,
        verdicts: list[VerifierVerdict],
        followup_used: bool,
        followup_prompt: str | None,
        verifier_prompts: list[str],
        events: list[AgentEvent],
        usage: TokenUsage,
        analysis: str | None,
        write_blocked: bool,
        holmes_error: bool,
        cancelled: bool,
        verifier_decision: str | None,
    ) -> VerifierResult:
        run = investigation.run
        evidence = collect_evidence(run.run_id, events)
        steps_used = investigator_steps_used(events)
        budget_state = evaluate_budget(
            events,
            self._budget,
            steps_used=steps_used,
            token_usage=usage,
        )
        progress = evaluate_progress(events, evidence, self._budget)
        parsed = parse_and_bind_diagnosis(analysis, evidence)
        if (
            verifier_decision == "accept"
            and verdicts
            and verdicts[-1].revised_root_cause
            and parsed.diagnosis is not None
        ):
            parsed = DiagnosisParseResult(
                draft=parsed.draft,
                diagnosis=parsed.diagnosis.model_copy(
                    update={"root_cause": verdicts[-1].revised_root_cause}
                ),
                hypotheses=parsed.hypotheses,
                error=parsed.error,
            )
        status, stop_reason = decide_outcome(
            parsed=parsed,
            budget=budget_state,
            progress=progress,
            successful_evidence=len(evidence),
            write_blocked=write_blocked,
            holmes_error=holmes_error,
            cancelled=cancelled,
            verifier_decision=verifier_decision,
        )
        if status is IncidentStatus.DIAGNOSIS_COMPLETE and parsed.diagnosis is None:
            status = IncidentStatus.EVIDENCE_INSUFFICIENT
            stop_reason = StopReason.INVALID_DIAGNOSIS

        run.status = status
        run.token_usage = usage
        run.estimated_cost = budget_state.estimated_cost
        run.ended_at = datetime.now(UTC)
        run.final_diagnosis = (
            parsed.diagnosis if status is IncidentStatus.DIAGNOSIS_COMPLETE else None
        )
        hypotheses = parsed.hypotheses if run.final_diagnosis is not None else []
        self._store.replace_evidence(run.run_id, evidence)
        self._store.replace_hypotheses(run.run_id, hypotheses)
        self._store.save_run(run)

        if is_successful_status(run.status):
            if run.final_diagnosis is None or not run.final_diagnosis.evidence_ids:
                raise RuntimeError(
                    "refusing to mark verifier success without evidence-backed diagnosis"
                )
            if write_blocked or holmes_error or cancelled or budget_state.exceeded:
                raise RuntimeError("refusing to mark verifier success after a failed control")

        logger.info(
            "verifier_end",
            run_id=str(run.run_id),
            scenario_id=run.scenario_id,
            status=run.status.value,
            stop_reason=stop_reason.value,
            followup_used=followup_used,
            verdicts=len(verdicts),
        )
        return VerifierResult(
            investigation=investigation,
            bundle=bundle,
            verdicts=verdicts,
            followup_used=followup_used,
            followup_prompt=followup_prompt,
            verifier_prompts=verifier_prompts,
            run=run,
            events=events,
            evidence=evidence,
            hypotheses=hypotheses,
            budget=budget_state,
            parsed=parsed,
            stop_reason=stop_reason,
            analysis=analysis,
        )


class _AskTurn(BaseModel):
    prompt: str
    events: list[AgentEvent]
    usage: TokenUsage
    analysis: str | None = None
    verdict: VerifierVerdict | None = None
    write_blocked: bool = False
    holmes_error: bool = False


def _refresh_investigation(
    result: InvestigationResult,
    *,
    events: Sequence[AgentEvent],
    analysis: str | None,
    usage: TokenUsage,
    budget: ToolBudget,
) -> InvestigationResult:
    evidence = collect_evidence(result.run.run_id, events)
    steps_used = investigator_steps_used(events)
    budget_state = evaluate_budget(events, budget, steps_used=steps_used, token_usage=usage)
    progress = evaluate_progress(events, evidence, budget)
    parsed = parse_and_bind_diagnosis(analysis, evidence)
    return result.model_copy(
        update={
            "events": list(events),
            "evidence": evidence,
            "budget": budget_state,
            "progress": progress,
            "parsed": parsed,
            "analysis": analysis,
        }
    )


def _resequence(
    events: Sequence[AgentEvent],
    run_id: UUID,
    *,
    start: int,
    role: str | None,
) -> list[AgentEvent]:
    rewritten: list[AgentEvent] = []
    for offset, event in enumerate(events):
        payload = dict(event.payload)
        if role:
            payload["role"] = role
        else:
            payload.setdefault("role", "investigator")
        rewritten.append(
            event.model_copy(
                update={"run_id": run_id, "sequence": start + offset, "payload": payload}
            )
        )
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
