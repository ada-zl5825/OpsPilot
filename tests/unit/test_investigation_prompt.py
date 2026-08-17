from opspilot.investigation.budget import ToolBudget
from opspilot.investigation.prompt import (
    AgentVisibleIncident,
    build_investigation_prompt,
    to_agent_visible,
)
from opspilot.investigation.safety import find_ground_truth_leaks
from opspilot.lab.scenarios import REQUIRED_SCENARIO_IDS, load_scenarios, scenario_by_id


def test_agent_visible_incident_excludes_scorer_fields() -> None:
    fields = set(AgentVisibleIncident.model_fields)
    assert "ground_truth_root_causes" not in fields
    assert "verification_code" not in fields
    assert "required_evidence" not in fields
    assert "allowed_remediations" not in fields


def test_to_agent_visible_drops_ground_truth() -> None:
    scenario = scenario_by_id("S01")
    visible = to_agent_visible(scenario)
    dumped = visible.model_dump_json()
    assert scenario.ground_truth_root_causes[0] not in dumped
    assert scenario.verification_code not in dumped
    assert scenario.required_evidence[0].description not in dumped


def test_prompts_for_s01_s04_exclude_ground_truth() -> None:
    budget = ToolBudget()
    assert {item.scenario_id for item in load_scenarios()} == set(REQUIRED_SCENARIO_IDS)
    for scenario in load_scenarios():
        prompt = build_investigation_prompt(to_agent_visible(scenario), budget)
        assert find_ground_truth_leaks(prompt, scenario) == []
        assert "execute_approved_proposal" not in prompt
        assert "query_service_metrics" in prompt
        assert "Final Diagnosis" in prompt or "evidence_ids" in prompt
