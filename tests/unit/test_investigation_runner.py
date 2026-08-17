from uuid import uuid4

import pytest
from tests.unit.investigation_fakes import (
    ScriptedHolmes,
    approval_ask,
    diagnosis_json,
    event,
    failed_tool_pair,
    successful_ask,
    successful_tool_pair,
)

from opspilot.domain.incidents import IncidentStatus, TokenUsage
from opspilot.holmes.client import HolmesAskResult
from opspilot.investigation.budget import ToolBudget
from opspilot.investigation.outcome import StopReason
from opspilot.investigation.replay import replay_store
from opspilot.investigation.runner import InvestigationRunner
from opspilot.investigation.store import InMemoryInvestigationStore
from opspilot.lab.scenarios import REQUIRED_SCENARIO_IDS, scenario_by_id
from opspilot.settings import Settings
from opspilot.telemetry.events import AgentEventType

SCENARIO_TOOLS = {
    "S01": ["query_service_metrics", "query_service_logs"],
    "S02": ["query_service_metrics", "query_service_logs"],
    "S03": ["get_recent_deployments", "query_service_logs", "query_service_metrics"],
    "S04": ["get_trace_summary", "query_service_logs", "query_service_metrics"],
}


def _runner(holmes: ScriptedHolmes, budget: ToolBudget | None = None) -> InvestigationRunner:
    return InvestigationRunner(
        holmes,
        InMemoryInvestigationStore(),
        settings=Settings(),
        budget=budget or ToolBudget(),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario_id", REQUIRED_SCENARIO_IDS)
async def test_runner_completes_s01_s04_with_evidence_backed_diagnosis(scenario_id: str) -> None:
    holmes = ScriptedHolmes([successful_ask(SCENARIO_TOOLS[scenario_id])])
    result = await _runner(holmes).run(scenario_id)
    scenario = scenario_by_id(scenario_id)
    assert scenario.ground_truth_root_causes[0] not in result.prompt
    assert scenario.verification_code not in result.prompt
    assert result.successful
    assert result.run.status is IncidentStatus.DIAGNOSIS_COMPLETE
    assert result.run.final_diagnosis is not None
    assert result.run.final_diagnosis.evidence_ids
    assert set(result.run.final_diagnosis.evidence_ids) <= {
        item.evidence_id for item in result.evidence
    }
    assert result.run.status is not IncidentStatus.RESOLVED
    replayed = replay_store(_store_from(result), result.run.run_id)
    assert replayed.successful
    assert replayed.diagnosis is not None
    assert replayed.diagnosis.evidence_ids == result.run.final_diagnosis.evidence_ids


def _store_from(result: object) -> InMemoryInvestigationStore:
    # The runner already persisted onto its store; rebuild from the result for replay.
    store = InMemoryInvestigationStore()
    from opspilot.investigation.runner import InvestigationResult

    assert isinstance(result, InvestigationResult)
    store.save_run(result.run)
    store.append_events(result.events)
    store.replace_evidence(result.run.run_id, result.evidence)
    store.replace_hypotheses(result.run.run_id, result.hypotheses)
    return store


@pytest.mark.asyncio
async def test_failed_tool_results_cannot_produce_a_successful_run() -> None:
    events = [event(AgentEventType.LLM_START, {}, sequence=1)]
    events.extend(failed_tool_pair("query_service_metrics", {"service": "checkout"}, sequence=2))
    analysis = diagnosis_json(
        [{"tool": "query_service_metrics", "params": {"service": "checkout"}}]
    )
    events.append(event(AgentEventType.LLM_END, {"analysis": analysis}, sequence=4))
    holmes = ScriptedHolmes(
        [
            HolmesAskResult(
                run_id=uuid4(),
                events=events,
                analysis=analysis,
                token_usage=TokenUsage(total_tokens=12),
            )
        ]
    )
    result = await _runner(holmes, ToolBudget(max_steps=1)).run("S01")
    assert result.successful is False
    assert result.run.status is not IncidentStatus.DIAGNOSIS_COMPLETE
    assert result.run.status is not IncidentStatus.RESOLVED
    assert result.run.final_diagnosis is None
    assert result.evidence == []


@pytest.mark.asyncio
async def test_duplicate_tool_calls_are_capped() -> None:
    params = {"service": "checkout", "metric": "error_rate"}
    events = [event(AgentEventType.LLM_START, {}, sequence=1)]
    sequence = 2
    for _ in range(3):
        events.extend(
            successful_tool_pair(
                "query_service_metrics", params, "same window", sequence=sequence
            )
        )
        sequence += 2
    analysis = diagnosis_json([{"tool": "query_service_metrics", "params": params}])
    events.append(event(AgentEventType.LLM_END, {"analysis": analysis}, sequence=sequence))
    holmes = ScriptedHolmes(
        [
            HolmesAskResult(
                run_id=uuid4(),
                events=events,
                analysis=analysis,
                token_usage=TokenUsage(total_tokens=20),
            )
        ]
    )
    result = await _runner(holmes, ToolBudget(max_repeats_per_query=2, max_repeats_per_tool=5)).run(
        "S01"
    )
    assert result.successful is False
    assert result.stop_reason is StopReason.DUPLICATE_TOOL_LIMIT
    assert result.run.status is IncidentStatus.EVIDENCE_INSUFFICIENT


@pytest.mark.asyncio
async def test_write_attempt_is_rejected_and_not_success() -> None:
    holmes = ScriptedHolmes([approval_ask()])
    result = await _runner(holmes).run("S01")
    assert holmes.rejected == 1
    assert result.successful is False
    assert result.run.status is IncidentStatus.POLICY_REJECTED
    assert result.stop_reason is StopReason.WRITE_BLOCKED


@pytest.mark.asyncio
async def test_diagnosis_without_evidence_ids_is_not_success() -> None:
    events = [event(AgentEventType.LLM_START, {}, sequence=1)]
    events.extend(
        successful_tool_pair(
            "query_service_metrics",
            {"service": "checkout"},
            "error rate up",
            sequence=2,
        )
    )
    events.append(
        event(
            AgentEventType.LLM_END,
            {"analysis": '{"root_cause": "unknown", "confidence": 0.2}'},
            sequence=4,
        )
    )
    holmes = ScriptedHolmes(
        [
            HolmesAskResult(
                run_id=uuid4(),
                events=events,
                analysis='{"root_cause": "unknown", "confidence": 0.2}',
                token_usage=TokenUsage(total_tokens=9),
            )
        ]
    )
    result = await _runner(holmes, ToolBudget(max_steps=1)).run("S02")
    assert result.successful is False
    assert result.stop_reason is StopReason.MISSING_EVIDENCE_CITATION
    assert result.run.final_diagnosis is None


@pytest.mark.asyncio
async def test_followup_prompt_stays_ground_truth_free() -> None:
    first = successful_ask(["query_service_metrics"])
    first.analysis = None
    first.events = [item for item in first.events if item.event_type is not AgentEventType.LLM_END]
    second = successful_ask(["query_service_logs"])
    holmes = ScriptedHolmes([first, second])
    result = await _runner(holmes, ToolBudget(max_steps=3)).run("S01")
    scenario = scenario_by_id("S01")
    assert holmes.prompts
    assert len(result.followup_prompts) == 1
    assert scenario.ground_truth_root_causes[0] not in result.followup_prompts[0]
    assert scenario.verification_code not in result.followup_prompts[0]
    assert result.successful
