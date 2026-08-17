from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError

from opspilot.domain.evidence import Evidence, Hypothesis
from opspilot.domain.incidents import Diagnosis
from opspilot.investigation.evidence import fingerprint_for

_FENCED_JSON = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


class EvidenceRef(BaseModel):
    tool: str
    params: dict[str, Any] = Field(default_factory=dict)


class HypothesisDraft(BaseModel):
    hypothesis_id: str
    statement: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    status: Literal["open", "rejected", "confirmed"] = "open"
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)


class DiagnosisDraft(BaseModel):
    root_cause: str
    evidence_ids: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    rejected_hypotheses: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    uncertainties: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    hypotheses: list[HypothesisDraft] = Field(default_factory=list)


class DiagnosisParseResult(BaseModel):
    draft: DiagnosisDraft | None = None
    diagnosis: Diagnosis | None = None
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    error: str | None = None

    @property
    def valid(self) -> bool:
        return self.diagnosis is not None and self.error is None


def extract_json_object(text: str) -> dict[str, Any] | None:
    fenced = _FENCED_JSON.search(text)
    candidates = [fenced.group(1)] if fenced else []
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])
    for raw in candidates:
        try:
            loaded = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(loaded, dict):
            return loaded
    return None


def parse_diagnosis_draft(analysis: str | None) -> DiagnosisDraft | None:
    if not analysis or not analysis.strip():
        return None
    payload = extract_json_object(analysis)
    if payload is None:
        return None
    try:
        return DiagnosisDraft.model_validate(payload)
    except ValidationError:
        return None


def resolve_evidence_ids(draft: DiagnosisDraft, evidence: Sequence[Evidence]) -> list[UUID]:
    known = {item.evidence_id: item for item in evidence}
    resolved: list[UUID] = []
    seen: set[UUID] = set()

    for raw in draft.evidence_ids:
        try:
            evidence_id = UUID(raw)
        except ValueError:
            continue
        if evidence_id in known and evidence_id not in seen:
            resolved.append(evidence_id)
            seen.add(evidence_id)

    for ref in draft.evidence_refs:
        match = _match_ref(ref, evidence)
        if match is not None and match.evidence_id not in seen:
            resolved.append(match.evidence_id)
            seen.add(match.evidence_id)
    return resolved


def _match_ref(ref: EvidenceRef, evidence: Sequence[Evidence]) -> Evidence | None:
    named = [item for item in evidence if item.source_tool == ref.tool]
    if not named:
        return None
    if ref.params:
        expected = fingerprint_for(ref.tool, ref.params)
        exact = [item for item in named if item.query_fingerprint == expected]
        if exact:
            return exact[0]
    return named[0]


def bind_diagnosis(draft: DiagnosisDraft, evidence: Sequence[Evidence]) -> DiagnosisParseResult:
    evidence_ids = resolve_evidence_ids(draft, evidence)
    if not evidence_ids:
        return DiagnosisParseResult(
            draft=draft,
            error="final diagnosis must cite successful evidence ids",
        )
    diagnosis = Diagnosis(
        root_cause=draft.root_cause,
        evidence_ids=evidence_ids,
        rejected_hypotheses=list(draft.rejected_hypotheses),
        confidence=draft.confidence,
        uncertainties=list(draft.uncertainties),
        recommended_actions=list(draft.recommended_actions),
    )
    known = {item.evidence_id for item in evidence}
    hypotheses = _hypotheses_from_draft(draft, known, evidence_ids)
    return DiagnosisParseResult(draft=draft, diagnosis=diagnosis, hypotheses=hypotheses)


def parse_and_bind_diagnosis(
    analysis: str | None, evidence: Sequence[Evidence]
) -> DiagnosisParseResult:
    draft = parse_diagnosis_draft(analysis)
    if draft is None:
        return DiagnosisParseResult(error="final diagnosis JSON is missing or invalid")
    return bind_diagnosis(draft, evidence)


def _parse_uuid(raw: str) -> UUID | None:
    try:
        return UUID(raw)
    except ValueError:
        return None


def _hypotheses_from_draft(
    draft: DiagnosisDraft,
    known: set[UUID],
    diagnosis_ids: Sequence[UUID],
) -> list[Hypothesis]:
    hypotheses: list[Hypothesis] = []
    for item in draft.hypotheses:
        supporting = [
            parsed
            for raw in item.supporting_evidence_ids
            if (parsed := _parse_uuid(raw)) in known
        ]
        contradicting = [
            parsed
            for raw in item.contradicting_evidence_ids
            if (parsed := _parse_uuid(raw)) in known
        ]
        if item.status == "confirmed" and not supporting:
            supporting = list(diagnosis_ids)
        hypotheses.append(
            Hypothesis(
                hypothesis_id=item.hypothesis_id,
                statement=item.statement,
                confidence=item.confidence,
                supporting_evidence_ids=supporting,
                contradicting_evidence_ids=contradicting,
                status=item.status,
            )
        )
    if hypotheses:
        return hypotheses
    if draft.root_cause:
        hypotheses.append(
            Hypothesis(
                hypothesis_id="H-final",
                statement=draft.root_cause,
                confidence=draft.confidence,
                supporting_evidence_ids=list(diagnosis_ids),
                status="confirmed",
            )
        )
    for index, rejected in enumerate(draft.rejected_hypotheses, start=1):
        hypotheses.append(
            Hypothesis(
                hypothesis_id=f"H-rejected-{index}",
                statement=rejected,
                confidence=0.0,
                status="rejected",
            )
        )
    return hypotheses
