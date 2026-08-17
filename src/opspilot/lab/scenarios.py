from __future__ import annotations

import json
from pathlib import Path

from opspilot.domain.incidents import IncidentScenario

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATASET_DIR = _REPO_ROOT / "benchmarks" / "datasets" / "incidents" / "v1"
REQUIRED_SCENARIO_IDS = ("S01", "S02", "S03", "S04")


def dataset_dir() -> Path:
    return DEFAULT_DATASET_DIR


def load_scenario(path: Path) -> IncidentScenario:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return IncidentScenario.model_validate(payload)


def load_scenarios(root: Path | None = None) -> list[IncidentScenario]:
    directory = root or dataset_dir()
    return [load_scenario(path) for path in sorted(directory.glob("S*.json"))]


def scenario_by_id(scenario_id: str, root: Path | None = None) -> IncidentScenario:
    for scenario in load_scenarios(root):
        if scenario.scenario_id == scenario_id:
            return scenario
    raise KeyError(scenario_id)
