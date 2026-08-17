from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from opspilot.domain.incidents import TokenUsage
from opspilot.holmes.sse import HolmesSseEvent
from opspilot.policy.redaction import redact_mapping
from opspilot.telemetry.events import AgentEvent, AgentEventType

_HOLMES_TO_AGENT: dict[str, AgentEventType] = {
    "start_tool_calling": AgentEventType.TOOL_CALL,
    "tool_calling_result": AgentEventType.TOOL_RESULT,
    "ai_message": AgentEventType.LLM_START,
    "ai_answer_end": AgentEventType.LLM_END,
    "approval_required": AgentEventType.APPROVAL_REQUIRED,
    "error": AgentEventType.ERROR,
}


class HolmesStreamParser:
    """Normalize HolmesGPT SSE / JSON events into OpsPilot AgentEvent records."""

    def parse(self, raw_events: Iterable[dict[str, Any]]) -> list[AgentEvent]:
        events: list[AgentEvent] = []
        for item in raw_events:
            if "event" in item and "event_type" not in item:
                sse = HolmesSseEvent.model_validate(item)
                run_id = UUID(str(item.get("run_id", uuid4())))
                events.extend(self.parse_holmes_events([sse], run_id=run_id))
                continue
            event_type = AgentEventType(item["event_type"])
            events.append(AgentEvent.model_validate({**item, "event_type": event_type}))
        return events

    def parse_holmes_events(
        self,
        raw_events: Iterable[HolmesSseEvent],
        *,
        run_id: UUID,
    ) -> list[AgentEvent]:
        events: list[AgentEvent] = []
        sequence = 0
        for raw in raw_events:
            mapped = _HOLMES_TO_AGENT.get(raw.event)
            if mapped is None:
                continue
            sequence += 1
            events.append(
                AgentEvent(
                    event_id=uuid4(),
                    run_id=run_id,
                    sequence=sequence,
                    event_type=mapped,
                    timestamp=datetime.now(UTC),
                    payload=redact_mapping(_payload_for(raw)),
                )
            )
        return events

    def extract_token_usage(self, raw_events: Iterable[HolmesSseEvent]) -> TokenUsage:
        usage = TokenUsage()
        for raw in raw_events:
            metadata = raw.data.get("metadata")
            if not isinstance(metadata, dict):
                continue
            provider = metadata.get("usage")
            if not isinstance(provider, dict):
                continue
            usage = TokenUsage(
                input_tokens=int(provider.get("prompt_tokens") or 0),
                output_tokens=int(provider.get("completion_tokens") or 0),
                total_tokens=int(provider.get("total_tokens") or 0),
            )
        return usage

    def extract_final_answer(self, raw_events: Iterable[HolmesSseEvent]) -> str | None:
        analysis: str | None = None
        for raw in raw_events:
            if raw.event == "ai_answer_end":
                value = raw.data.get("analysis")
                if isinstance(value, str):
                    analysis = value
        return analysis


def _payload_for(raw: HolmesSseEvent) -> dict[str, Any]:
    data = dict(raw.data)
    if raw.event == "start_tool_calling":
        return {
            "tool_name": data.get("tool_name"),
            "tool_call_id": data.get("id") or data.get("tool_call_id"),
        }
    if raw.event == "tool_calling_result":
        result = data.get("result")
        result_obj = result if isinstance(result, dict) else {"data": result}
        inner = _coerce_result_data(result_obj.get("data"))
        ok = result_obj.get("ok")
        if ok is None and isinstance(inner, dict):
            ok = inner.get("ok")
        artifact_ref = None
        if isinstance(inner, dict):
            artifact_ref = inner.get("artifact_ref")
        return {
            "tool_name": data.get("name") or data.get("tool_name"),
            "tool_call_id": data.get("tool_call_id"),
            "status": result_obj.get("status"),
            "ok": ok,
            "error": result_obj.get("error")
            or (inner.get("error_type") if isinstance(inner, dict) else None),
            "params": result_obj.get("params") or {},
            "artifact_ref": artifact_ref,
            "result_summary": _summarize(inner if inner is not None else result_obj.get("data")),
        }
    if raw.event == "ai_answer_end":
        return {
            "analysis": data.get("analysis"),
            "usage": (data.get("metadata") or {}).get("usage")
            if isinstance(data.get("metadata"), dict)
            else None,
        }
    if raw.event == "approval_required":
        return {
            "pending_approvals": data.get("pending_approvals") or [],
            "pending_frontend_tool_calls": data.get("pending_frontend_tool_calls") or [],
        }
    return data


def _coerce_result_data(value: Any) -> Any:
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("{") or text.startswith("["):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return value
    return value


def _summarize(value: Any, *, limit: int = 240) -> str | None:
    if value is None:
        return None
    text = value if isinstance(value, str) else str(value)
    if len(text) <= limit:
        return text
    return text[:limit] + "...[truncated]"
