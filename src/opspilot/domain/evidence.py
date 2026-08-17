from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class Evidence(BaseModel):
    evidence_id: UUID
    run_id: UUID
    source_tool: str
    source_system: str
    captured_at: datetime
    query_fingerprint: str
    content_digest: str
    summary: str
    raw_artifact_ref: str | None = None
    supports_hypotheses: list[str] = Field(default_factory=list)
    contradicts_hypotheses: list[str] = Field(default_factory=list)
    sensitivity: Literal["public", "internal", "sensitive"] = "internal"


class Hypothesis(BaseModel):
    hypothesis_id: str
    statement: str
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_evidence_ids: list[UUID] = Field(default_factory=list)
    contradicting_evidence_ids: list[UUID] = Field(default_factory=list)
    status: Literal["open", "rejected", "confirmed"] = "open"
