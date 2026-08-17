from opspilot.investigation.diagnosis import DiagnosisDraft
from opspilot.investigation.prompt import to_agent_visible
from opspilot.lab.scenarios import scenario_by_id
from opspilot.verifier.policy import enforce_verdict
from opspilot.verifier.schema import (
    EvidenceBundleItem,
    FollowupRequest,
    InvestigatorBundle,
    SharedBudgetSnapshot,
    VerifierVerdict,
)


def _bundle(*, remaining_tools: int = 4, followup_used: bool = False) -> InvestigatorBundle:
    scenario = scenario_by_id("S01")
    return InvestigatorBundle(
        scenario_id=scenario.scenario_id,
        incident=to_agent_visible(scenario),
        diagnosis=DiagnosisDraft(root_cause="telemetry-backed fault"),
        evidence=[
            EvidenceBundleItem(
                evidence_id="00000000-0000-0000-0000-000000000001",
                source_tool="query_service_metrics",
                source_system="prometheus",
                query_fingerprint="abc",
                summary="error rate moved",
            )
        ],
        recommended_actions=["open a typed proposal"],
        budget=SharedBudgetSnapshot(
            max_tool_calls=16,
            tool_calls_used=16 - remaining_tools,
            remaining_tool_calls=remaining_tools,
            max_steps=3,
            steps_used=1,
            remaining_steps=2,
            followups_used=1 if followup_used else 0,
            remaining_followups=0 if followup_used else 1,
        ),
        followup_used=followup_used,
    )


def test_write_tool_in_followup_is_stripped_and_budget_blocks_second_pass() -> None:
    verdict = VerifierVerdict(
        decision="request_followup",
        evidence_supports_conclusion=False,
        followup=FollowupRequest(
            reason="need another observation",
            suggested_tools=["execute_approved_proposal", "query_service_logs"],
        ),
    )
    applied = enforce_verdict(verdict, _bundle())
    assert applied.verdict.decision == "request_followup"
    assert applied.verdict.followup is not None
    assert applied.verdict.followup.suggested_tools == ["query_service_logs"]

    blocked = enforce_verdict(verdict, _bundle(remaining_tools=0))
    assert blocked.verdict.decision == "reject"
    assert "shared budget" in " ".join(blocked.notes)


def test_accept_without_evidence_is_rejected() -> None:
    bundle = _bundle()
    bundle = bundle.model_copy(update={"evidence": []})
    applied = enforce_verdict(
        VerifierVerdict(decision="accept", evidence_supports_conclusion=True),
        bundle,
    )
    assert applied.verdict.decision == "reject"
