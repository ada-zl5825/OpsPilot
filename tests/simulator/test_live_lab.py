from __future__ import annotations

import pytest
from simulator.harness.client import LabClient
from simulator.harness.verify import verify_lab


@pytest.mark.lab
def test_integrity_two_cycles_and_live_recovery(require_lab: None) -> None:
    client = LabClient()
    try:
        result = verify_lab(cycles=2, client=client)
    finally:
        client.close()
    assert result.integrity_errors == []
    assert result.observability["prometheus"]
    assert result.observability["loki"]
    assert result.observability["tempo"]
    assert result.ok, [
        item
        for item in result.cycles
        if not (
            item.injected
            and item.fault_visible
            and item.token_found
            and item.recovered
            and item.recovery_passed
        )
    ]
