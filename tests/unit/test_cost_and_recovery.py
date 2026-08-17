from opspilot.domain.incidents import RecoveryCheck, TokenUsage
from opspilot.telemetry.cost import estimate_cost
from opspilot.verification.recovery import verify_recovery


def test_estimate_cost() -> None:
    cost = estimate_cost(TokenUsage(input_tokens=1000, output_tokens=1000, total_tokens=2000))
    assert cost > 0


def test_recovery_all_must_match() -> None:
    checks = [
        RecoveryCheck(
            check_id="c1",
            description="error rate",
            metric_or_endpoint="checkout_5xx",
            success_criteria="<0.01",
        )
    ]
    results = verify_recovery(checks, {"c1": "<0.01"})
    assert results[0].passed is True
    failed = verify_recovery(checks, {"c1": "0.2"})
    assert failed[0].passed is False
