from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from opspilot.domain.incidents import IncidentScenario
from opspilot.investigation.safety import FORBIDDEN_PROMPT_HINTS, scorer_only_strings
from opspilot.lab.scenarios import load_scenarios, scenario_by_id

VARIANT_CATALOG = Path(__file__).parent / "variants" / "v1" / "catalog.json"
MIN_VARIANTS = 20


class ScenarioVariant(BaseModel):
    variant_id: str
    scenario_id: str
    split: str
    seed: int = 1
    user_report: str
    notes: str = ""


class VariantCatalog(BaseModel):
    version: str
    frozen_at: str
    parent_scenarios: list[str] = Field(default_factory=list)
    notes: str = ""
    variants: list[ScenarioVariant] = Field(default_factory=list)


def catalog_path() -> Path:
    return VARIANT_CATALOG


def load_catalog(path: Path | None = None) -> VariantCatalog:
    payload = json.loads((path or VARIANT_CATALOG).read_text(encoding="utf-8"))
    return VariantCatalog.model_validate(payload)


def load_variants(
    *,
    split: str | None = None,
    scenario_id: str | None = None,
    path: Path | None = None,
) -> list[ScenarioVariant]:
    items = load_catalog(path).variants
    if split:
        items = [item for item in items if item.split == split]
    if scenario_id:
        items = [item for item in items if item.scenario_id == scenario_id]
    return items


def variant_by_id(variant_id: str, path: Path | None = None) -> ScenarioVariant:
    for item in load_variants(path=path):
        if item.variant_id == variant_id:
            return item
    raise KeyError(variant_id)


def parent_scenario(variant: ScenarioVariant) -> IncidentScenario:
    return scenario_by_id(variant.scenario_id)


def check_variant_integrity(path: Path | None = None) -> list[str]:
    errors: list[str] = []
    catalog_file = path or VARIANT_CATALOG
    if not catalog_file.exists():
        return [f"missing variant catalog: {catalog_file}"]
    try:
        catalog = load_catalog(catalog_file)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"variant catalog is invalid: {exc}"]

    parents = {item.scenario_id for item in load_scenarios()}
    seen: set[str] = set()
    splits: set[str] = set()
    if len(catalog.variants) < MIN_VARIANTS:
        errors.append(
            f"need at least {MIN_VARIANTS} frozen variants, found {len(catalog.variants)}"
        )
    for item in catalog.variants:
        if item.variant_id in seen:
            errors.append(f"duplicate variant_id {item.variant_id}")
        seen.add(item.variant_id)
        splits.add(item.split)
        if item.split not in {"eval", "holdout"}:
            errors.append(f"{item.variant_id}: split must be eval or holdout")
        if item.scenario_id not in parents:
            errors.append(f"{item.variant_id}: unknown parent scenario {item.scenario_id}")
            continue
        scenario = scenario_by_id(item.scenario_id)
        blob = item.user_report.lower()
        for hint in FORBIDDEN_PROMPT_HINTS:
            if hint in blob:
                errors.append(f"{item.variant_id}: user_report leaks '{hint}'")
        for value in scorer_only_strings(scenario):
            if value and value in item.user_report:
                errors.append(f"{item.variant_id}: scorer-only value leaked into user_report")
        if scenario.verification_code and scenario.verification_code in item.user_report:
            errors.append(f"{item.variant_id}: verification_code leaked into user_report")
    if "eval" not in splits:
        errors.append("variant catalog has no eval split")
    if "holdout" not in splits:
        errors.append("variant catalog has no holdout split")
    eval_ids = {item.variant_id for item in catalog.variants if item.split == "eval"}
    holdout_ids = {item.variant_id for item in catalog.variants if item.split == "holdout"}
    overlap = eval_ids & holdout_ids
    if overlap:
        errors.append(f"holdout overlaps eval: {', '.join(sorted(overlap))}")
    return errors
