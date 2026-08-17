from benchmarks.datasets.check_integrity import FORBIDDEN_HINTS

from opspilot.investigation.budget import ToolBudget
from opspilot.investigation.prompt import build_investigation_prompt, to_agent_visible
from opspilot.investigation.safety import find_ground_truth_leaks
from opspilot.lab.scenarios import REQUIRED_SCENARIO_IDS, load_scenarios


def test_phase3_prompts_pass_dataset_anti_cheat_rules() -> None:
    budget = ToolBudget()
    scenarios = load_scenarios()
    assert {item.scenario_id for item in scenarios} == set(REQUIRED_SCENARIO_IDS)
    for scenario in scenarios:
        prompt = build_investigation_prompt(to_agent_visible(scenario), budget)
        lowered = prompt.lower()
        assert find_ground_truth_leaks(prompt, scenario) == []
        for hint in FORBIDDEN_HINTS:
            assert hint not in lowered
        assert scenario.verification_code not in prompt
        for cause in scenario.ground_truth_root_causes:
            assert cause not in prompt
        assert scenario.diagnosis_rubric is not None
        assert scenario.diagnosis_rubric.fault_kind not in prompt
        for item in scenario.required_evidence:
            assert item.description not in prompt
