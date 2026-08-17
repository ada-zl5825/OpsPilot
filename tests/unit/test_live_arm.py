from __future__ import annotations

from typing import Any

import httpx
import pytest

from benchmarks.live import _arm_lab


class FakeLab:
    def __init__(self, *, quiet_after: int = 1, injected_at: str = "2026-08-17T15:00:00Z") -> None:
        self.calls: list[str] = []
        self._quiet_checks = 0
        self.quiet_after = quiet_after
        self.injected_at = injected_at

    def reset_all(self) -> dict[str, Any]:
        self.calls.append("reset_all")
        return {"reset": True}

    def prior_incident_quiet(self) -> bool:
        self._quiet_checks += 1
        self.calls.append("quiet_check")
        return self._quiet_checks >= self.quiet_after

    def wait_until(self, predicate: Any, timeout_sec: float, interval: float = 0.0) -> bool:
        for _ in range(int(timeout_sec) + 1):
            if predicate():
                return True
        return False

    def inject(self, scenario_id: str) -> dict[str, Any]:
        self.calls.append(f"inject:{scenario_id}")
        return {"injected": True, "injected_at": self.injected_at}

    def place_order(self, timeout: float = 8.0) -> httpx.Response:
        self.calls.append("place_order")
        return httpx.Response(200)

    def prometheus_has_recent_checkout_traffic(self) -> bool:
        return True

    def loki_has_recent_service_logs(self, service: str = "checkout") -> bool:
        return True


def test_arm_lab_waits_for_quiet_before_inject() -> None:
    lab = FakeLab(quiet_after=2)
    window = _arm_lab(lab, "S02")
    assert lab.calls[:4] == ["reset_all", "quiet_check", "quiet_check", "inject:S02"]
    assert window.start == "2026-08-17T14:59:55Z"


def test_arm_lab_fails_if_lab_stays_noisy() -> None:
    lab = FakeLab(quiet_after=10_000)
    with pytest.raises(RuntimeError, match="did not go quiet"):
        _arm_lab(lab, "S02")
    assert "inject:S02" not in lab.calls
