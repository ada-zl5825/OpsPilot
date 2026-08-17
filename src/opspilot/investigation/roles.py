from __future__ import annotations

from opspilot.telemetry.events import AgentEvent

INVESTIGATOR_ROLE = "investigator"
VERIFIER_ROLE = "verifier"


def event_role(event: AgentEvent) -> str:
    role = event.payload.get("role")
    if role == VERIFIER_ROLE:
        return VERIFIER_ROLE
    return INVESTIGATOR_ROLE


def is_investigator_event(event: AgentEvent) -> bool:
    return event_role(event) == INVESTIGATOR_ROLE


def is_verifier_event(event: AgentEvent) -> bool:
    return event_role(event) == VERIFIER_ROLE
