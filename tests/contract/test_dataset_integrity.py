from benchmarks.datasets.check_integrity import REQUIRED_IDS, check_integrity

from opspilot.lab.scenarios import load_scenarios


def test_current_dataset_has_no_integrity_errors() -> None:
    assert check_integrity() == []
    assert {item.scenario_id for item in load_scenarios()} == REQUIRED_IDS
