from benchmarks.datasets.variants import check_variant_integrity, load_catalog, load_variants

from opspilot.investigation.prompt import build_investigation_prompt, to_agent_visible
from opspilot.investigation.safety import find_ground_truth_leaks
from opspilot.lab.scenarios import scenario_by_id


def test_frozen_catalog_has_twenty_variants_and_holdout() -> None:
    catalog = load_catalog()
    variants = catalog.variants
    assert len(variants) >= 20
    eval_ids = {item.variant_id for item in variants if item.split == "eval"}
    holdout_ids = {item.variant_id for item in variants if item.split == "holdout"}
    assert eval_ids
    assert holdout_ids
    assert eval_ids.isdisjoint(holdout_ids)
    assert {item.scenario_id for item in variants} == {"S01", "S02", "S03", "S04"}
    assert check_variant_integrity() == []


def test_variant_prompts_exclude_ground_truth() -> None:
    from opspilot.investigation.budget import ToolBudget

    budget = ToolBudget()
    for variant in load_variants():
        scenario = scenario_by_id(variant.scenario_id)
        prompt = build_investigation_prompt(
            to_agent_visible(scenario, user_report=variant.user_report),
            budget,
        )
        assert find_ground_truth_leaks(prompt, scenario) == []
        assert scenario.verification_code not in prompt
        for cause in scenario.ground_truth_root_causes:
            assert cause not in prompt
        assert scenario.diagnosis_rubric is not None
        assert scenario.diagnosis_rubric.fault_kind not in prompt
