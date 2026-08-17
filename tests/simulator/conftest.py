from __future__ import annotations

import os

import pytest
from simulator.harness.client import LabClient


def lab_stack_up() -> bool:
    client = LabClient()
    try:
        return client.controller_healthy()
    finally:
        client.close()


@pytest.fixture(scope="session")
def require_lab() -> None:
    if not lab_stack_up():
        if os.environ.get("OPSPILOT_REQUIRE_LAB") == "1":
            raise RuntimeError("lab stack is required but controller is not healthy")
        pytest.skip("lab stack is not running")
