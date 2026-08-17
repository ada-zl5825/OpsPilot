from pathlib import Path

from benchmarks.harness import _score_built, build_condition
from experiments.single_vs_verifier.compare import (
    accepted_missing_evidence,
    accepted_wrong,
    compare_failure_pair,
)
from experiments.single_vs_verifier.failures import all_failure_pairs
from experiments.single_vs_verifier.report import run_experiment


def test_eval_ab_does_not_promote_when_single_agent_already_correct(tmp_path: Path) -> None:
    report = run_experiment(split="eval", out_dir=tmp_path, include_holdout=True)
    cmp = report.comparison
    assert cmp.single.root_cause == 1.0
    assert cmp.verifier.root_cause == 1.0
    assert cmp.l3_root_cause_lift == 0.0
    assert cmp.token_ratio > 1.0
    assert cmp.cost_ratio > 1.0
    assert cmp.latency_ratio > 1.0
    assert cmp.single.unsafe_rate == 0.0
    assert cmp.verifier.unsafe_rate == 0.0
    assert cmp.promotion.promote is False
    assert report.holdout is not None
    assert report.holdout.promotion.promote is False
    assert list(tmp_path.glob("*/report.json"))
    assert list(tmp_path.glob("*/report.md"))
    markdown = next(tmp_path.glob("*/report.md")).read_text(encoding="utf-8")
    assert "DO NOT PROMOTE" in markdown
    assert "Simple Agent remains the default" in markdown


def test_verifier_reduces_constructed_investigator_failures() -> None:
    deltas = [
        compare_failure_pair(_score_built(flawed), _score_built(corrected))
        for flawed, corrected in all_failure_pairs()
    ]
    reduced = {name for item in deltas for name in item.reduced}
    assert "wrong_root_cause" in reduced
    assert "missing_evidence" in reduced
    by_kind = {item.kind: item for item in deltas}
    assert by_kind["wrong_root_cause"].investigator_accepted_wrong
    assert by_kind["wrong_root_cause"].verifier_accepted_wrong is False
    assert by_kind["missing_evidence"].investigator_accepted_missing_evidence
    assert by_kind["missing_evidence"].verifier_accepted_missing_evidence is False
    assert by_kind["unsupported_conclusion"].investigator_accepted_wrong
    assert by_kind["unsupported_conclusion"].verifier_accepted_wrong is False


def test_offline_verifier_condition_matches_single_agent_accuracy() -> None:
    from benchmarks.datasets.variants import load_variants

    variants = load_variants(split="eval")
    single = [_score_built(item) for item in build_condition("single_agent", variants)]
    verifier = [_score_built(item) for item in build_condition("verifier", variants)]
    assert len(single) == len(verifier) == 16
    assert all(card.raw.root_cause_score == 1.0 for card in single)
    assert all(card.raw.root_cause_score == 1.0 for card in verifier)
    assert all(not accepted_wrong(card) for card in verifier)
    assert all(not accepted_missing_evidence(card) for card in verifier)
    assert sum(card.raw.llm_turns for card in verifier) > sum(card.raw.llm_turns for card in single)
