from __future__ import annotations

from pydantic import BaseModel

from opspilot.domain.incidents import RecoveryCheck


class CheckResult(BaseModel):
    check_id: str
    passed: bool
    detail: str


def evaluate_check(check: RecoveryCheck, observed_value: str) -> CheckResult:
    passed = observed_value == check.success_criteria
    return CheckResult(
        check_id=check.check_id,
        passed=passed,
        detail="matched success criteria" if passed else "success criteria not met",
    )
