from uuid import uuid4

from tests.unit.investigation_fakes import diagnosis_json

from opspilot.domain.evidence import Evidence
from opspilot.investigation.diagnosis import (
    bind_diagnosis,
    parse_and_bind_diagnosis,
    parse_diagnosis_draft,
)
from opspilot.investigation.evidence import evidence_id_for, fingerprint_for


def _evidence(tool: str, params: dict[str, str]) -> Evidence:
    run_id = uuid4()
    fingerprint = fingerprint_for(tool, params)
    from datetime import UTC, datetime

    return Evidence(
        evidence_id=evidence_id_for(run_id, fingerprint),
        run_id=run_id,
        source_tool=tool,
        source_system="prometheus",
        captured_at=datetime.now(UTC),
        query_fingerprint=fingerprint,
        content_digest="abc",
        summary=f"{tool} ok",
    )


def test_diagnosis_binds_evidence_refs_to_ids() -> None:
    params = {"service": "checkout", "call": 0}
    evidence = _evidence("query_service_metrics", params)
    parsed = parse_and_bind_diagnosis(
        diagnosis_json([{"tool": "query_service_metrics", "params": params}]),
        [evidence],
    )
    assert parsed.valid
    assert parsed.diagnosis is not None
    assert parsed.diagnosis.evidence_ids == [evidence.evidence_id]


def test_diagnosis_rejects_missing_citations() -> None:
    evidence = _evidence("query_service_metrics", {"service": "checkout"})
    parsed = parse_and_bind_diagnosis(
        '{"root_cause": "guess", "confidence": 0.9, "evidence_refs": []}',
        [evidence],
    )
    assert parsed.valid is False
    assert parsed.diagnosis is None
    assert parsed.error is not None


def test_diagnosis_cannot_cite_failed_or_unknown_ids() -> None:
    evidence = _evidence("query_service_logs", {"service": "checkout"})
    draft = parse_diagnosis_draft(
        f'{{"root_cause": "guess", "confidence": 0.4, "evidence_ids": ["{uuid4()}"]}}'
    )
    assert draft is not None
    parsed = bind_diagnosis(draft, [evidence])
    assert parsed.valid is False


def test_unparseable_analysis_is_invalid() -> None:
    parsed = parse_and_bind_diagnosis("the root cause is probably checkout", [])
    assert parsed.valid is False
    assert parsed.draft is None
