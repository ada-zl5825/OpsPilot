"""Phase 1 lab helpers. Ground truth stays in dataset files, never in Agent context."""

from opspilot.lab.scenarios import (
    REQUIRED_SCENARIO_IDS,
    dataset_dir,
    load_scenario,
    load_scenarios,
    scenario_by_id,
)

__all__ = [
    "REQUIRED_SCENARIO_IDS",
    "dataset_dir",
    "load_scenario",
    "load_scenarios",
    "scenario_by_id",
]
