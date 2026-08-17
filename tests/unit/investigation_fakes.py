from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from opspilot.domain.incidents import TokenUsage
from opspilot.holmes.client import HolmesAskResult, PendingApproval
from opspilot.telemetry.events import AgentEvent, AgentEventType


def event(
    event_type: AgentEventType,
    payload: dict[str, Any],
    *,
    sequence: int = 1,
) -> AgentEvent:
    return AgentEvent(
        event_id=uuid4(),
        run_id=uuid4(),
        sequence=sequence,
        event_type=event_type,
        timestamp=datetime.now(UTC),
        payload=payload,
    )


def successful_tool_pair(
    tool: str,
    params: dict[str, Any],
    summary: str,
    *,
    sequence: int,
) -> list[AgentEvent]:
    return [
        event(AgentEventType.TOOL_CALL, {"tool_name": tool}, sequence=sequence),
        event(
            AgentEventType.TOOL_RESULT,
            {
                "tool_name": tool,
                "status": "success",
                "ok": True,
                "params": params,
                "result_summary": summary,
            },
            sequence=sequence + 1,
        ),
    ]


def failed_tool_pair(
    tool: str,
    params: dict[str, Any],
    *,
    sequence: int,
    status: str = "error",
    error: str = "backend",
) -> list[AgentEvent]:
    return [
        event(AgentEventType.TOOL_CALL, {"tool_name": tool}, sequence=sequence),
        event(
            AgentEventType.TOOL_RESULT,
            {
                "tool_name": tool,
                "status": status,
                "ok": False,
                "error": error,
                "params": params,
                "result_summary": '{"ok": false, "error_type": "backend"}',
            },
            sequence=sequence + 1,
        ),
    ]


def diagnosis_json(
    refs: list[dict[str, Any]], *, root_cause: str = "telemetry-backed fault"
) -> str:
    return json.dumps(
        {
            "root_cause": root_cause,
            "evidence_refs": refs,
            "confidence": 0.7,
            "rejected_hypotheses": ["unrelated neighbor release"],
            "uncertainties": ["window bounds"],
            "recommended_actions": ["open a proposal after review"],
            "hypotheses": [
                {
                    "hypothesis_id": "H1",
                    "statement": root_cause,
                    "confidence": 0.7,
                    "status": "confirmed",
                }
            ],
        }
    )


def successful_ask(tools: list[str]) -> HolmesAskResult:
    events: list[AgentEvent] = [event(AgentEventType.LLM_START, {}, sequence=1)]
    refs: list[dict[str, Any]] = []
    sequence = 2
    for index, tool in enumerate(tools):
        params = {"service": "checkout", "call": index}
        events.extend(
            successful_tool_pair(
                tool,
                params,
                f"{tool} returned a distinct observation {index}",
                sequence=sequence,
            )
        )
        refs.append({"tool": tool, "params": params})
        sequence += 2
    analysis = diagnosis_json(refs)
    events.append(event(AgentEventType.LLM_END, {"analysis": analysis}, sequence=sequence))
    return HolmesAskResult(
        run_id=uuid4(),
        events=events,
        analysis=analysis,
        token_usage=TokenUsage(input_tokens=20, output_tokens=10, total_tokens=30),
    )


class ScriptedHolmes:
    def __init__(self, results: list[HolmesAskResult]) -> None:
        self.results = list(results)
        self.prompts: list[str] = []
        self.rejected = 0

    async def ask(self, prompt: str, **kwargs: Any) -> HolmesAskResult:
        self.prompts.append(prompt)
        if not self.results:
            raise AssertionError("unexpected extra Holmes ask")
        return self.results.pop(0)

    async def reject_pending(self, result: HolmesAskResult) -> HolmesAskResult:
        self.rejected += 1
        return result


def approval_ask(tool_name: str = "lab_mutate_probe") -> HolmesAskResult:
    pending = PendingApproval(tool_call_id="call_mut_1", tool_name=tool_name)
    events = [
        event(AgentEventType.TOOL_CALL, {"tool_name": tool_name}, sequence=1),
        event(
            AgentEventType.APPROVAL_REQUIRED,
            {"pending_approvals": [{"tool_call_id": "call_mut_1", "tool_name": tool_name}]},
            sequence=2,
        ),
    ]
    return HolmesAskResult(
        run_id=uuid4(),
        events=events,
        analysis=None,
        pending_approvals=[pending],
        paused_for_approval=True,
        token_usage=TokenUsage(input_tokens=8, output_tokens=2, total_tokens=10),
    )
