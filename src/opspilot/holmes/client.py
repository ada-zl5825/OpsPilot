from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID, uuid4

import httpx
from pydantic import BaseModel, Field

from opspilot.domain.incidents import TokenUsage
from opspilot.holmes.sse import HolmesSseEvent, parse_sse_buffer
from opspilot.holmes.stream_parser import HolmesStreamParser
from opspilot.logging import get_logger
from opspilot.settings import Settings
from opspilot.telemetry.events import AgentEvent

logger = get_logger("opspilot.holmes")


class PendingApproval(BaseModel):
    tool_call_id: str
    tool_name: str
    description: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class ToolDecision(BaseModel):
    tool_call_id: str
    approved: bool


class HolmesAskResult(BaseModel):
    run_id: UUID
    events: list[AgentEvent] = Field(default_factory=list)
    raw_events: list[HolmesSseEvent] = Field(default_factory=list)
    analysis: str | None = None
    conversation_history: list[dict[str, Any]] = Field(default_factory=list)
    pending_approvals: list[PendingApproval] = Field(default_factory=list)
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    paused_for_approval: bool = False

    @property
    def unapproved_write_attempted(self) -> bool:
        return any(
            event.event_type.value == "tool_result"
            and event.payload.get("status") == "success"
            and str(event.payload.get("tool_name", "")).endswith("mutate_probe")
            for event in self.events
        )


class HolmesClient:
    """HTTP client for the pinned HolmesGPT container."""

    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient | None = None,
        *,
        auto_approve: bool = False,
    ) -> None:
        if auto_approve:
            raise ValueError("HolmesClient refuses auto_approve; approvals are human-only")
        self._settings = settings
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(base_url=settings.holmes_base_url, timeout=60.0)
        self._parser = HolmesStreamParser()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def healthz(self) -> dict[str, Any]:
        response = await self._client.get("/healthz")
        response.raise_for_status()
        payload = response.json() if response.content else {"status": "ok"}
        logger.info("holmes_healthz", status=response.status_code)
        return payload if isinstance(payload, dict) else {"status": "ok"}

    async def ask(
        self,
        prompt: str,
        *,
        extra: dict[str, Any] | None = None,
        enable_tool_approval: bool = True,
        model: str | None = None,
        conversation_history: list[dict[str, Any]] | None = None,
        tool_decisions: Sequence[ToolDecision] | None = None,
        run_id: UUID | None = None,
    ) -> HolmesAskResult:
        if tool_decisions and any(decision.approved for decision in tool_decisions):
            raise PermissionError("approved tool_decisions must go through the control plane")
        run_id = run_id or uuid4()
        body: dict[str, Any] = {
            "ask": prompt,
            "stream": True,
            "enable_tool_approval": enable_tool_approval,
            "behavior_controls": {
                "todowrite_instructions": False,
                "todowrite_reminder": False,
            },
        }
        if model or self._settings.holmes_model_name:
            body["model"] = model or self._settings.holmes_model_name
        if conversation_history:
            body["conversation_history"] = conversation_history
        if tool_decisions:
            body["tool_decisions"] = [decision.model_dump() for decision in tool_decisions]
        if extra:
            body.update(extra)

        logger.info("holmes_ask_start", run_id=str(run_id), prompt_length=len(prompt))
        raw_events = await self._stream_chat(body)
        events = self._parser.parse_holmes_events(raw_events, run_id=run_id)
        pending = _pending_approvals(raw_events)
        history = _conversation_history(raw_events)
        result = HolmesAskResult(
            run_id=run_id,
            events=events,
            raw_events=raw_events,
            analysis=self._parser.extract_final_answer(raw_events),
            conversation_history=history,
            pending_approvals=pending,
            token_usage=self._parser.extract_token_usage(raw_events),
            paused_for_approval=bool(pending),
        )
        logger.info(
            "holmes_ask_end",
            run_id=str(run_id),
            event_count=len(events),
            paused_for_approval=result.paused_for_approval,
            pending_tools=[item.tool_name for item in pending],
        )
        return result

    async def reject_pending(self, result: HolmesAskResult) -> HolmesAskResult:
        if not result.pending_approvals:
            return result
        decisions = [
            ToolDecision(tool_call_id=item.tool_call_id, approved=False)
            for item in result.pending_approvals
        ]
        return await self.ask(
            prompt="continue",
            conversation_history=result.conversation_history,
            tool_decisions=decisions,
            run_id=result.run_id,
        )

    async def _stream_chat(self, body: dict[str, Any]) -> list[HolmesSseEvent]:
        events: list[HolmesSseEvent] = []
        buffer = ""
        async with self._client.stream(
            "POST",
            "/api/chat",
            json=body,
            headers={"Accept": "text/event-stream"},
        ) as response:
            response.raise_for_status()
            async for chunk in response.aiter_text():
                buffer += chunk
                parsed, buffer = parse_sse_buffer(buffer)
                events.extend(parsed)
        if buffer.strip():
            trailing, _ = parse_sse_buffer(buffer + "\n\n")
            events.extend(trailing)
        return events


def _pending_approvals(raw_events: Sequence[HolmesSseEvent]) -> list[PendingApproval]:
    pending: list[PendingApproval] = []
    for raw in raw_events:
        if raw.event != "approval_required":
            continue
        for item in raw.data.get("pending_approvals") or []:
            if isinstance(item, dict):
                pending.append(
                    PendingApproval(
                        tool_call_id=str(item.get("tool_call_id")),
                        tool_name=str(item.get("tool_name")),
                        description=item.get("description"),
                        params=item.get("params") or {},
                    )
                )
    return pending


def _conversation_history(raw_events: Sequence[HolmesSseEvent]) -> list[dict[str, Any]]:
    history: list[dict[str, Any]] = []
    for raw in raw_events:
        value = raw.data.get("conversation_history")
        if isinstance(value, list):
            history = [item for item in value if isinstance(item, dict)]
    return history
