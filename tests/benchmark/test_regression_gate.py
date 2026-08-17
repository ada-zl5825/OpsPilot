from pathlib import Path

from benchmarks.gate import evaluate_gate
from benchmarks.harness import run_offline
from benchmarks.report import build_report


def test_eval_gate_passes_frozen_baselines(tmp_path: Path) -> None:
    report = run_offline(split="eval", out_dir=tmp_path, gate=True)
    assert report.gate_passed is True
    assert report.gate_failures == []
    det = next(item for item in report.summaries if item.condition == "deterministic")
    agent = next(item for item in report.summaries if item.condition == "single_agent")
    assert det.composite.mean == 1.0
    assert agent.composite.mean == 0.8372
    assert det.unsafe_action_rate == 0.0
    assert agent.unapproved_write_count == 0


def test_gate_fails_when_composite_drops(tmp_path: Path) -> None:
    report = run_offline(split="eval", out_dir=tmp_path, gate=False)
    lowered = report.summaries[0].model_copy(
        update={"composite": report.summaries[0].composite.model_copy(update={"mean": 0.1})}
    )
    broken = build_report(
        report.cards,
        split="eval",
        conditions=report.conditions,
    )
    broken.summaries = [lowered, *report.summaries[1:]]
    failures = evaluate_gate(broken)
    assert failures


def test_holdout_is_scored_but_not_the_ci_gate(tmp_path: Path) -> None:
    holdout = run_offline(split="holdout", out_dir=tmp_path, gate=False)
    assert holdout.split == "holdout"
    assert all(card.split == "holdout" for card in holdout.cards)
    assert {card.variant_id for card in holdout.cards} >= {
        "S01-V05",
        "S02-V05",
        "S03-V05",
        "S04-V05",
    }
