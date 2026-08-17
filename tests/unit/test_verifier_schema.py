from uuid import uuid4

from opspilot.investigation.diagnosis import DiagnosisDraft
from opspilot.investigation.prompt import to_agent_visible
from opspilot.lab.scenarios import scenario_by_id
from opspilot.verifier.schema import (
    InvestigatorBundle,
    SharedBudgetSnapshot,
    VerifierVerdict,
    parse_verdict,
)


def _budget() -> SharedBudgetSnapshot:
    return SharedBudgetSnapshot(
        max_tool_calls=16,
        tool_calls_used=2,
        remaining_tool_calls=14,
        max_steps=3,
        steps_used=1,
        remaining_steps=2,
    )


def test_investigator_bundle_excludes_scorer_fields() -> None:
    fields = set(InvestigatorBundle.model_fields)
    assert "ground_truth_root_causes" not in fields
    assert "diagnosis_rubric" not in fields
    assert "verification_code" not in fields
    assert "required_evidence" not in fields
    scenario = scenario_by_id("S01")
    bundle = InvestigatorBundle(
        scenario_id=scenario.scenario_id,
        incident=to_agent_visible(scenario),
        diagnosis=DiagnosisDraft(root_cause="telemetry-backed fault", evidence_ids=[str(uuid4())]),
        budget=_budget(),
    )
    dumped = bundle.model_dump_json()
    assert scenario.ground_truth_root_causes[0] not in dumped
    assert scenario.verification_code not in dumped


def test_verdict_accept_requires_support_and_safety() -> None:
    try:
        VerifierVerdict(decision="accept", evidence_supports_conclusion=False)
    except Exception as exc:
        assert "evidence_supports_conclusion" in str(exc)
    else:
        raise AssertionError("accept without support must fail")
    try:
        VerifierVerdict(decision="accept", evidence_supports_conclusion=True, safety_ok=False)
    except Exception as exc:
        assert "safety_ok" in str(exc)
    else:
        raise AssertionError("accept without safety_ok must fail")


def test_parse_verdict_round_trip() -> None:
    raw = """```json
{"decision":"reject","evidence_supports_conclusion":false,"unsupported_claims":["guess"]}
```"""
    verdict = parse_verdict(raw)
    assert verdict is not None
    assert verdict.decision == "reject"
    assert parse_verdict("not json") is None
