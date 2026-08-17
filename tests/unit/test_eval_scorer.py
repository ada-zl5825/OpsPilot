from opspilot.eval.constants import COMPOSITE_WEIGHTS
from opspilot.eval.metrics import normalize_cause, root_cause_scores, score_root_cause
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
    extra = score_root_cause("checkout_database_connection_pool_exhausted extra", item)
    assert extra.exact == 0.0
    assert extra.score >= 0.8
    _, miss = root_cause_scores("unrelated_inventory_stockout", item)
    assert miss == 0.0
    assert normalize_cause("Checkout-Database Connection Pool Exhausted") == (
        "checkout_database_connection_pool_exhausted"
    )


def test_live_s01_connection_wait_is_not_a_false_zero() -> None:
    item = scenario_by_id("S01")
    breakdown = score_root_cause(
        "Checkout service is experiencing elevated error rates due to "
        "database connection wait times exceeding request deadlines.",
        item,
    )
    assert breakdown.exact == 0.0
    assert breakdown.localization == 1.0
    assert breakdown.identification == 1.0
    assert breakdown.reason >= 0.5
    assert breakdown.score >= 0.8


def test_live_s02_db_narrative_stays_zero() -> None:
    item = scenario_by_id("S02")
    breakdown = score_root_cause(
        "Checkout service latency increased due to database connection "
        "wait times exceeding request deadlines.",
        item,
    )
    assert breakdown.localization == 0.0
    assert breakdown.identification == 0.0
    assert breakdown.score == 0.0


def test_live_s03_release_with_db_attractor_gets_partial() -> None:
    item = scenario_by_id("S03")
    breakdown = score_root_cause(
        "The checkout service errors increased after the release of version "
        "1.4.2 at 14:44 UTC. Logs show repeated 'order total computation failed' "
        "and 'database connection wait exceeded request deadline' errors.",
        item,
    )
    assert breakdown.localization == 1.0
    assert breakdown.identification == 0.5
    assert breakdown.reason >= 0.5
    assert breakdown.score >= 0.7


def test_live_s04_db_collapse_stays_zero() -> None:
    item = scenario_by_id("S04")
    breakdown = score_root_cause(
        "Checkout service is experiencing database connection issues, leading "
        "to order computation failures and downstream request timeouts.",
        item,
    )
    assert breakdown.localization == 0.0
    assert breakdown.identification == 0.0
    assert breakdown.score == 0.0
