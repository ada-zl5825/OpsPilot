from __future__ import annotations

from typing import Any

from mcp_servers.deployments.schemas import DEPLOYMENT_INPUT_SCHEMAS
from mcp_servers.observability.schemas import OBSERVABILITY_INPUT_SCHEMAS
from mcp_servers.runbooks.schemas import RUNBOOK_INPUT_SCHEMAS

PHASE2_INPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    **OBSERVABILITY_INPUT_SCHEMAS,
    **DEPLOYMENT_INPUT_SCHEMAS,
    **RUNBOOK_INPUT_SCHEMAS,
}


def phase2_input_schemas() -> dict[str, dict[str, Any]]:
    return dict(PHASE2_INPUT_SCHEMAS)
