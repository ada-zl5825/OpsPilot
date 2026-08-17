from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, Field

from opspilot.domain.evidence import Evidence
from opspilot.investigation.budget import ToolBudget
from opspilot.investigation.evidence import content_digest, tool_name_of, tool_result_succeeded
from opspilot.telemetry.events import AgentEvent, AgentEventType


class ProgressState(BaseModel):
    new_evidence_count: int = 0
    stalled_steps: int = 0
    no_progress: bool = False
    unique_digests: list[str] = Field(default_factory=list)


def evaluate_progress(
    events: Sequence[AgentEvent],
    evidence: Sequence[Evidence],
    budget: ToolBudget,
) -> ProgressState:
    seen: set[str] = set()
    stalled = 0
    max_stalled = 0
    for event in events:
        if event.event_type is not AgentEventType.TOOL_RESULT:
            continue
        if not tool_result_succeeded(event) or not tool_name_of(event):
            stalled += 1
            max_stalled = max(max_stalled, stalled)
            continue
        digest = content_digest(str(event.payload.get("result_summary") or ""))
        if digest in seen:
            stalled += 1
        else:
            seen.add(digest)
            stalled = 0
        max_stalled = max(max_stalled, stalled)
    no_progress = False
    if max_stalled >= budget.max_no_progress_steps:
        no_progress = True
    if evidence and not seen:
        no_progress = True
    return ProgressState(
        new_evidence_count=len(evidence),
        stalled_steps=max_stalled,
        no_progress=no_progress,
        unique_digests=sorted(seen),
    )
