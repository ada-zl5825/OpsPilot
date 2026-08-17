from benchmarks.datasets.variants import load_variants
from benchmarks.harness import _score_built
from benchmarks.trajectories import build_failure_fixture


def test_unsafe_and_unapproved_write_force_composite_zero() -> None:
    variant = load_variants(split="holdout")[0]
    for kind in ("unapproved_write", "unsafe_action", "secret_leak", "resolved_without_verify"):
        card = _score_built(build_failure_fixture(variant, kind))
        assert card.composite == 0.0, kind
        assert card.hard_fails, kind
