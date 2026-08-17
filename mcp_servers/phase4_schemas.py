from __future__ import annotations

from typing import Any

from mcp_servers.remediation.schemas import REMEDIATION_INPUT_SCHEMAS

PHASE4_INPUT_SCHEMAS: dict[str, dict[str, Any]] = dict(REMEDIATION_INPUT_SCHEMAS)


def phase4_input_schemas() -> dict[str, dict[str, Any]]:
    return dict(PHASE4_INPUT_SCHEMAS)
