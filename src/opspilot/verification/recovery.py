from __future__ import annotations

from pydantic import BaseModel, Field

from opspilot.domain.incidents import RecoveryCheck
from opspilot.executor.cluster import WorkloadSnapshot
from opspilot.verification.checks import CheckResult, evaluate_check


class RecoveryReport(BaseModel):
    passed: bool
    checks: list[CheckResult] = Field(default_factory=list)
    snapshot: WorkloadSnapshot | None = None


def verify_recovery(
    checks: list[RecoveryCheck],
    observations: dict[str, str],
) -> list[CheckResult]:
    return [evaluate_check(check, observations.get(check.check_id, "")) for check in checks]


def verify_snapshot(snapshot: WorkloadSnapshot, *, max_latency_ms: int = 1500) -> RecoveryReport:
    checks = [
        CheckResult(
            check_id="ready",
            passed=snapshot.ready,
            detail="workload ready" if snapshot.ready else "workload not ready",
        ),
        CheckResult(
            check_id="healthy",
            passed=snapshot.healthy and snapshot.status_code < 400,
            detail=f"status={snapshot.status_code}",
        ),
        CheckResult(
            check_id="latency",
            passed=snapshot.latency_ms <= max_latency_ms,
            detail=f"latency_ms={snapshot.latency_ms}",
        ),
    ]
    return RecoveryReport(
        passed=all(item.passed for item in checks),
        checks=checks,
        snapshot=snapshot,
    )
