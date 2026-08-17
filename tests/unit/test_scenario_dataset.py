from benchmarks.datasets.check_integrity import check_integrity
from simulator.services.common.tokens import SCENARIO_TOKENS

from opspilot.lab.scenarios import REQUIRED_SCENARIO_IDS, load_scenarios


def test_phase1_scenarios_load_and_stay_off_prompt() -> None:
    scenarios = load_scenarios()
    assert {item.scenario_id for item in scenarios} == set(REQUIRED_SCENARIO_IDS)
    for scenario in scenarios:
        prompt = " ".join([scenario.title, *scenario.initial_symptoms, *scenario.prompt_variants])
        assert scenario.verification_code
        assert scenario.verification_code not in prompt
        for cause in scenario.ground_truth_root_causes:
            assert cause not in prompt
        assert scenario.required_evidence
        assert scenario.allowed_remediations
        assert scenario.recovery_checks
        assert SCENARIO_TOKENS[scenario.scenario_id] == scenario.verification_code


def test_dataset_integrity_passes() -> None:
    assert check_integrity() == []
