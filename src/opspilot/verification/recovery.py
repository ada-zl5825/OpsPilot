from __future__ import annotations

from opspilot.domain.incidents import RecoveryCheck
from opspilot.verification.checks import CheckResult, evaluate_check


def verify_recovery(
    checks: list[RecoveryCheck],
    observations: dict[str, str],
) -> list[CheckResult]:
    return [evaluate_check(check, observations.get(check.check_id, "")) for check in checks]
