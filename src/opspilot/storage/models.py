from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON, Uuid


class Base(DeclarativeBase):
    pass


def _json_type() -> JSON:
    return JSON().with_variant(JSONB, "postgresql")


class IncidentRunRow(Base):
    __tablename__ = "incident_runs"

    run_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    scenario_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(128))
    prompt_version: Mapped[str] = mapped_column(String(64))
    tool_catalog_version: Mapped[str] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    token_usage: Mapped[dict[str, Any]] = mapped_column(_json_type())
    estimated_cost: Mapped[str] = mapped_column(String(32))
    final_diagnosis: Mapped[dict[str, Any] | None] = mapped_column(_json_type(), nullable=True)
    recovery_verified: Mapped[bool] = mapped_column(default=False)


class EvidenceRow(Base):
    __tablename__ = "evidence"

    evidence_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    run_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    source_tool: Mapped[str] = mapped_column(String(128))
    source_system: Mapped[str] = mapped_column(String(64))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    query_fingerprint: Mapped[str] = mapped_column(String(32))
    content_digest: Mapped[str] = mapped_column(String(32))
    summary: Mapped[str] = mapped_column(Text)
    raw_artifact_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    supports_hypotheses: Mapped[list[str]] = mapped_column(_json_type())
    contradicts_hypotheses: Mapped[list[str]] = mapped_column(_json_type())
    sensitivity: Mapped[str] = mapped_column(String(32))


class HypothesisRow(Base):
    __tablename__ = "hypotheses"

    hypothesis_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    statement: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float]
    supporting_evidence_ids: Mapped[list[str]] = mapped_column(_json_type())
    contradicting_evidence_ids: Mapped[list[str]] = mapped_column(_json_type())
    status: Mapped[str] = mapped_column(String(32))


class AgentEventRow(Base):
    __tablename__ = "agent_events"

    event_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    run_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(64))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, Any]] = mapped_column(_json_type())
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    span_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
