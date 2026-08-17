from benchmarks.datasets.check_integrity import FORBIDDEN_HINTS

from opspilot.investigation.budget import BudgetState, ToolBudget
from opspilot.investigation.prompt import to_agent_visible
from opspilot.investigation.safety import find_ground_truth_leaks
from opspilot.lab.scenarios import REQUIRED_SCENARIO_IDS, load_scenarios
from opspilot.verifier.budget import snapshot_budget
from opspilot.verifier.prompt import build_followup_prompt, build_verifier_prompt
from opspilot.verifier.schema import FollowupRequest, InvestigatorBundle


def test_phase6_prompts_pass_dataset_anti_cheat_rules() -> None:
    budget = ToolBudget()
    scenarios = load_scenarios()
    assert {item.scenario_id for item in scenarios} == set(REQUIRED_SCENARIO_IDS)
    for scenario in scenarios:
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
            FollowupRequest(
                reason="collect one more read-only observation",
                suggested_tools=["query_service_logs"],
            ),
            budget,
        )
        for text in (verifier, followup):
            lowered = text.lower()
            assert find_ground_truth_leaks(text, scenario) == []
            for hint in FORBIDDEN_HINTS:
                assert hint not in lowered
            assert scenario.verification_code not in text
            for cause in scenario.ground_truth_root_causes:
                assert cause not in text
            assert scenario.diagnosis_rubric is not None
            assert scenario.diagnosis_rubric.fault_kind not in text
            for item in scenario.required_evidence:
                assert item.description not in text
            assert "execute_approved_proposal" not in followup
