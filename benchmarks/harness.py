from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from uuid import uuid4

from benchmarks.datasets.variants import ScenarioVariant, load_variants, parent_scenario
from benchmarks.gate import evaluate_gate
from benchmarks.report import build_report, write_report
from benchmarks.trajectories import (
    BuiltTrajectory,
    build_deterministic,
    build_single_agent,
)
from opspilot.eval.models import BenchmarkReport, ScoreCard
from opspilot.eval.scorer import score_trajectory
from opspilot.investigation.constants import PROMPT_VERSION, TOOL_CATALOG_VERSION

DEFAULT_OUT = Path("artifacts") / "benchmarks"
CONDITIONS = ("deterministic", "single_agent")


def _score_built(built: BuiltTrajectory) -> ScoreCard:
    scenario = parent_scenario(built.variant)
    diagnosis = built.replayed.diagnosis or built.run.final_diagnosis
    return score_trajectory(
        built.events,
        scenario,
        variant_id=built.variant.variant_id,
        condition=built.condition,
        split=built.variant.split,
        model=built.run.model,
        prompt_version=built.run.prompt_version or PROMPT_VERSION,
        tool_catalog_version=built.run.tool_catalog_version or TOOL_CATALOG_VERSION,
        diagnosis=diagnosis,
        run=built.run,
        prompt=built.prompt,
        stop_reason=built.replayed.stop_reason,
    )


def build_condition(condition: str, variants: Sequence[ScenarioVariant]) -> list[BuiltTrajectory]:
    builder = build_deterministic if condition == "deterministic" else build_single_agent
    if condition not in CONDITIONS:
        raise ValueError(f"unknown condition {condition}")
    return [builder(item) for item in variants]


def run_offline(
    *,
    split: str = "eval",
    conditions: Sequence[str] = CONDITIONS,
    out_dir: Path | None = None,
    gate: bool = False,
) -> BenchmarkReport:
    variants = load_variants(split=split)
    if not variants:
        raise ValueError(f"no variants for split={split}")
    cards: list[ScoreCard] = []
    for condition in conditions:
        for built in build_condition(condition, variants):
            cards.append(_score_built(built))
    failures: list[str] = []
    passed: bool | None = None
    if gate:
        draft = build_report(cards, split=split, conditions=conditions)
        failures = evaluate_gate(draft)
        passed = not failures
    target = (out_dir or DEFAULT_OUT) / str(uuid4())
    report = build_report(
        cards,
        split=split,
        conditions=conditions,
        gate_passed=passed,
        gate_failures=failures,
    )
    report.extra["artifact_dir"] = str(target)
    write_report(report, target)
    return report
