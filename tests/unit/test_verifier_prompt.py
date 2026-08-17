from opspilot.investigation.budget import BudgetState, ToolBudget
from opspilot.investigation.diagnosis import DiagnosisDraft
from opspilot.investigation.prompt import to_agent_visible
from opspilot.investigation.safety import find_ground_truth_leaks
from opspilot.lab.scenarios import REQUIRED_SCENARIO_IDS, load_scenarios
from opspilot.verifier.budget import snapshot_budget
from opspilot.verifier.prompt import (
    assert_followup_prompt_safe,
    build_followup_prompt,
    build_verifier_prompt,
)
from opspilot.verifier.schema import EvidenceBundleItem, FollowupRequest, InvestigatorBundle


def test_verifier_and_followup_prompts_exclude_ground_truth() -> None:
    budget = ToolBudget()
    for scenario in load_scenarios():
        visible = to_agent_visible(scenario)
        bundle = InvestigatorBundle(
            scenario_id=scenario.scenario_id,
            incident=visible,
            budget=snapshot_budget(BudgetState(), budget),
        )
        verifier = build_verifier_prompt(bundle)
        followup = build_followup_prompt(
            visible,
            bundle,
            FollowupRequest(reason="collect one more read-only observation"),
            budget,
        )
        assert find_ground_truth_leaks(verifier, scenario) == []
        assert find_ground_truth_leaks(followup, scenario) == []
        assert "execute_approved_proposal" in verifier
        assert "do not call write" in followup.lower() or "Do not call write" in followup


def test_verifier_prompt_allows_discovered_connection_pool_wording() -> None:
    scenario = next(item for item in load_scenarios() if item.scenario_id == "S01")
    visible = to_agent_visible(scenario)
    bundle = InvestigatorBundle(
        scenario_id=scenario.scenario_id,
        incident=visible,
        budget=snapshot_budget(BudgetState(), ToolBudget()),
        diagnosis=DiagnosisDraft(
            root_cause="checkout errors after database connection wait",
            recommended_actions=["Investigate database connection pool configuration"],
        ),
        evidence=[
            EvidenceBundleItem(
                evidence_id="e1",
                source_tool="query_service_logs",
                source_system="loki",
                query_fingerprint="checkout-error",
                summary="checkout log: database connection pool wait exceeded deadline",
            )
        ],
    )
    prompt = build_verifier_prompt(bundle)
    assert "connection pool" in prompt.lower()
    request = FollowupRequest(reason="check connection pool gauges")
    followup = build_followup_prompt(visible, bundle, request, ToolBudget())
    assert "connection pool" in followup.lower()
    assert_followup_prompt_safe(followup, bundle, request, scenario)


def test_prompt_only_covers_s01_s04() -> None:
    assert {item.scenario_id for item in load_scenarios()} == set(REQUIRED_SCENARIO_IDS)
