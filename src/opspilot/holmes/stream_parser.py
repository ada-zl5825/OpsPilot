from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from opspilot.telemetry.events import AgentEvent, AgentEventType


class HolmesStreamParser:
    """Parse HolmesGPT stream events into OpsPilot AgentEvent records.

    Phase 0 will map real Holmes event names. This stub only accepts already-normalized
    payloads so unit tests can lock the output contract.
    """

    def parse(self, raw_events: Iterable[dict[str, Any]]) -> list[AgentEvent]:
        events: list[AgentEvent] = []
        for item in raw_events:
            event_type = AgentEventType(item["event_type"])
            events.append(AgentEvent.model_validate({**item, "event_type": event_type}))
        return events
