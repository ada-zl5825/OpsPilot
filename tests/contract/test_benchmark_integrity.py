from benchmarks.datasets.check_integrity import check_all, check_integrity
from benchmarks.datasets.variants import check_variant_integrity, load_variants

from opspilot.lab.scenarios import load_scenarios


def test_phase1_scenarios_still_isolated() -> None:
    assert check_integrity() == []
    assert {item.scenario_id for item in load_scenarios()} == {"S01", "S02", "S03", "S04"}


def test_phase5_variants_and_combined_integrity() -> None:
    assert check_variant_integrity() == []
    assert check_all() == []
    variants = load_variants()
    assert len(variants) >= 20
    assert any(item.split == "holdout" for item in variants)
    assert {item.variant_id for item in load_variants(split="eval")}.isdisjoint(
        {item.variant_id for item in load_variants(split="holdout")}
    )
