import json
from uuid import uuid4

import pytest
from tests.unit.investigation_fakes import (
    ScriptedHolmes,
    approval_ask,
    diagnosis_json,
    event,
    successful_ask,
    successful_tool_pair,
)

from opspilot.domain.incidents import IncidentStatus, TokenUsage
from opspilot.holmes.client import HolmesAskResult
from opspilot.investigation.budget import ToolBudget
from opspilot.investigation.outcome import StopReason
from opspilot.investigation.store import InMemoryInvestigationStore
from opspilot.settings import Settings
from opspilot.telemetry.events import AgentEventType
from opspilot.verifier.runner import VerifierRunner


def _runner(holmes: ScriptedHolmes, budget: ToolBudget | None = None) -> VerifierRunner:
    return VerifierRunner(
        holmes,
        InMemoryInvestigationStore(),
        settings=Settings(),
        budget=budget or ToolBudget(),
    )


def _verdict_ask(
    decision: str,
    *,
    supports: bool = True,
    followup_tool: str | None = None,
    safety_ok: bool = True,
) -> HolmesAskResult:
    payload: dict[str, object] = {
        "decision": decision,
        "evidence_supports_conclusion": supports,
        "unsupported_claims": [],
        "counterexamples": [],
        "remediation_consistent": True,
        "safety_ok": safety_ok,
        "confidence": 0.7,
        "notes": [],
    }
    if decision == "request_followup":
        payload["followup"] = {
            "reason": "need one more read-only observation",
            "missing_checks": ["another telemetry source"],
            "suggested_tools": [followup_tool or "query_service_logs"],
            "suggested_params": [{"service": "checkout"}],
        }
    analysis = json.dumps(payload)
    events = [
        event(AgentEventType.LLM_START, {"role": "verifier"}, sequence=1),
        event(AgentEventType.LLM_END, {"analysis": analysis, "role": "verifier"}, sequence=2),
    ]
    return HolmesAskResult(
        run_id=uuid4(),
        events=events,
        analysis=analysis,
        token_usage=TokenUsage(input_tokens=12, output_tokens=8, total_tokens=20),
    )


@pytest.mark.asyncio
async def test_verifier_accepts_without_a_second_investigation() -> None:
    holmes = ScriptedHolmes(
        [successful_ask(["query_service_metrics", "query_service_logs"]), _verdict_ask("accept")]
    )
    result = await _runner(holmes).run("S01")
    assert result.successful
    assert result.followup_used is False
    assert [item.decision for item in result.verdicts] == ["accept"]
    assert result.run.status is IncidentStatus.DIAGNOSIS_COMPLETE
    assert holmes.prompts[1]
    assert "Investigator bundle" in holmes.prompts[1]
    assert len(holmes.prompts) == 2


@pytest.mark.asyncio
async def test_verifier_followup_runs_once_then_cannot_request_again() -> None:
    first = successful_ask(["query_service_metrics"])
    follow = successful_ask(["query_service_logs"])
    holmes = ScriptedHolmes(
        [
            first,
            _verdict_ask("request_followup", supports=False, followup_tool="query_service_logs"),
            follow,
            _verdict_ask("request_followup", supports=True, followup_tool="get_trace_summary"),
        ]
    )
    result = await _runner(holmes).run("S01")
    assert result.followup_used is True
    assert result.followup_prompt is not None
    assert "Structured follow-up request" in result.followup_prompt
    assert len(holmes.prompts) == 4
    assert result.verdicts[-1].decision in {"accept", "reject"}
    assert result.verdicts[-1].decision != "request_followup" or result.followup_used


@pytest.mark.asyncio
async def test_shared_budget_blocks_followup() -> None:
    params = {"service": "checkout", "call": 0}
    events = [event(AgentEventType.LLM_START, {}, sequence=1)]
    events.extend(
        successful_tool_pair("query_service_metrics", params, "metrics moved", sequence=2)
    )
    analysis = diagnosis_json([{"tool": "query_service_metrics", "params": params}])
    events.append(event(AgentEventType.LLM_END, {"analysis": analysis}, sequence=4))
    investigator = HolmesAskResult(
        run_id=uuid4(),
        events=events,
        analysis=analysis,
        token_usage=TokenUsage(total_tokens=10),
    )
    holmes = ScriptedHolmes(
        [
            investigator,
            _verdict_ask("request_followup", supports=False),
        ]
    )
    result = await _runner(holmes, ToolBudget(max_tool_calls=1, max_steps=1)).run("S01")
    assert result.followup_used is False
    assert result.successful is False
    assert result.stop_reason in {
        StopReason.VERIFIER_REJECTED,
        StopReason.VERIFIER_FOLLOWUP_BLOCKED,
        StopReason.BUDGET_EXHAUSTED,
    }
    assert len(holmes.prompts) == 2


@pytest.mark.asyncio
async def test_write_blocked_skips_verifier() -> None:
    holmes = ScriptedHolmes([approval_ask()])
    result = await _runner(holmes).run("S01")
    assert result.successful is False
    assert result.run.status is IncidentStatus.POLICY_REJECTED
    assert result.verdicts == []
    assert len(holmes.prompts) == 1


@pytest.mark.asyncio
async def test_verifier_ask_has_no_conversation_history() -> None:
    holmes = ScriptedHolmes(
        [successful_ask(["query_service_metrics", "query_service_logs"]), _verdict_ask("accept")]
    )

    async def ask(prompt: str, **kwargs: object) -> HolmesAskResult:
        holmes.prompts.append(prompt)
        history = kwargs.get("conversation_history")
        assert history in (None, []) or "conversation_history" not in kwargs
        if not holmes.results:
            raise AssertionError("unexpected extra Holmes ask")
        return holmes.results.pop(0)

    holmes.ask = ask  # type: ignore[method-assign]
    result = await _runner(holmes).run("S02")
    assert result.successful
    assert len(holmes.prompts) == 2
