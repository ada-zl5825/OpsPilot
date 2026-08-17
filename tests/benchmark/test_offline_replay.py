from pathlib import Path

from benchmarks.datasets.variants import load_variants
from benchmarks.harness import _score_built, run_offline
from benchmarks.trajectories import build_deterministic, build_single_agent

from opspilot.eval.replay import replay_and_score
from opspilot.lab.scenarios import scenario_by_id


def test_offline_replay_matches_direct_score() -> None:
    variant = next(item for item in load_variants(split="eval") if item.scenario_id == "S03")
    built = build_deterministic(variant)
    replayed, card = replay_and_score(
        built.run,
        built.events,
        scenario_by_id(variant.scenario_id),
        variant_id=variant.variant_id,
        condition="deterministic",
        split=variant.split,
        prompt=built.prompt,
    )
    assert replayed.events
    assert card.composite == 1.0
    assert card.hard_fails == []
    assert card.raw.recovery_success == 1.0


def test_single_agent_offline_is_investigation_only() -> None:
    variant = next(item for item in load_variants(split="eval") if item.scenario_id == "S04")
    card = _score_built(build_single_agent(variant))
    assert card.composite > 0
    assert card.raw.root_cause_score == 1.0
    assert card.raw.recovery_success == 0.0
    assert card.hard_fails == []


def test_offline_harness_emits_both_conditions(tmp_path: Path) -> None:
    report = run_offline(split="eval", out_dir=tmp_path, gate=False)
    conditions = {item.condition for item in report.summaries}
    assert conditions == {"deterministic", "single_agent"}
    assert list(tmp_path.glob("*/report.json"))
    assert list(tmp_path.glob("*/report.md"))
