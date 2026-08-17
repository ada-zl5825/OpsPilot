from opspilot.eval.constants import COMPOSITE_WEIGHTS
from opspilot.eval.metrics import normalize_cause, root_cause_scores
from opspilot.eval.models import HardFail, RawMetrics
from opspilot.eval.scorer import composite_score
from opspilot.lab.scenarios import scenario_by_id


def test_composite_weights_sum_to_one() -> None:
    assert abs(sum(COMPOSITE_WEIGHTS.values()) - 1.0) < 1e-9


def test_composite_is_zero_when_hard_fail_present() -> None:
    raw = RawMetrics(
        root_cause_score=1.0,
        evidence_coverage=1.0,
        tool_efficiency=1.0,
        recovery_success=1.0,
        failure_recovery=1.0,
        escalation_accuracy=1.0,
    )
    assert composite_score(raw, []) == 1.0
    assert composite_score(raw, [HardFail.UNSAFE_ACTION]) == 0.0
    assert composite_score(raw, [HardFail.UNAPPROVED_WRITE]) == 0.0


def test_root_cause_exact_and_partial() -> None:
    item = scenario_by_id("S01")
    exact, score = root_cause_scores(item.ground_truth_root_causes[0], item)
    assert exact == 1.0
    assert score == 1.0
    _, partial = root_cause_scores("checkout_database_connection_pool_exhausted extra", item)
    assert partial == 0.5
    _, miss = root_cause_scores("unrelated_inventory_stockout", item)
    assert miss == 0.0
    assert normalize_cause("Checkout-Database Connection Pool Exhausted") == (
        "checkout_database_connection_pool_exhausted"
    )
