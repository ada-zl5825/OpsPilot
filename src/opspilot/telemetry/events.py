from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AgentEventType(StrEnum):
    LLM_START = "llm_start"
    LLM_END = "llm_end"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    APPROVAL_REQUIRED = "approval_required"
    APPROVAL_DECISION = "approval_decision"
    PROPOSAL_CREATED = "proposal_created"
    EXECUTION_START = "execution_start"
    EXECUTION_END = "execution_end"
    VERIFICATION_RESULT = "verification_result"
    ERROR = "error"


class AgentEvent(BaseModel):
    event_id: UUID
    run_id: UUID
    sequence: int
    event_type: AgentEventType
    timestamp: datetime
    payload: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = None
    span_id: str | None = None
