from __future__ import annotations

from collections.abc import Sequence

from opspilot.investigation.budget import BudgetState, ToolBudget, remaining_tool_calls
from opspilot.investigation.roles import is_investigator_event
from opspilot.telemetry.events import AgentEvent, AgentEventType
from opspilot.verifier.constants import MAX_FOLLOWUPS
from opspilot.verifier.schema import SharedBudgetSnapshot


def investigator_steps_used(events: Sequence[AgentEvent]) -> int:
    return sum(
        1
        for event in events
        if event.event_type is AgentEventType.LLM_END and is_investigator_event(event)
    )


def snapshot_budget(
    state: BudgetState,
    budget: ToolBudget,
    *,
    followups_used: int = 0,
    steps_used: int | None = None,
) -> SharedBudgetSnapshot:
    used_steps = state.steps if steps_used is None else steps_used
    remaining_steps = max(0, budget.max_steps - used_steps)
    remaining_followups = max(0, MAX_FOLLOWUPS - followups_used)
    return SharedBudgetSnapshot(
        max_tool_calls=budget.max_tool_calls,
        tool_calls_used=state.tool_calls,
        remaining_tool_calls=remaining_tool_calls(state, budget),
        max_steps=budget.max_steps,
        steps_used=used_steps,
        remaining_steps=remaining_steps,
        max_followups=MAX_FOLLOWUPS,
        followups_used=followups_used,
        remaining_followups=remaining_followups,
    )


def can_followup(snapshot: SharedBudgetSnapshot) -> bool:
    return (
        snapshot.remaining_followups > 0
        and snapshot.remaining_tool_calls > 0
        and snapshot.remaining_steps > 0
        and not snapshot.followups_used >= snapshot.max_followups
    )
