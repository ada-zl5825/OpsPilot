from uuid import uuid4

from mcp_servers.common.artifacts import ArtifactStore
from mcp_servers.common.fastmcp_schemas import fastmcp_input_schemas
from mcp_servers.common.runtime import ToolRuntime
from mcp_servers.contracts import tool_by_name
from mcp_servers.phase4_schemas import phase4_input_schemas
from mcp_servers.remediation.server import mcp as remediation_mcp
from mcp_servers.remediation.tools import propose_restart_workload

from opspilot.holmes.compatibility import validate_tool_schema_for_azure
from opspilot.remediation.service import ControlPlane


def test_fastmcp_server_omits_mutate_tools() -> None:
    generated = fastmcp_input_schemas(remediation_mcp)
    assert "execute_approved_proposal" not in generated
    assert "rollback_execution" not in generated
    for name in phase4_input_schemas():
        assert name in generated


def test_each_phase4_schema_is_azure_compatible() -> None:
    for name, schema in phase4_input_schemas().items():
        report = validate_tool_schema_for_azure(name, schema)
        assert report.compatible is True, (name, report.issues)
    for name, schema in fastmcp_input_schemas(remediation_mcp).items():
        report = validate_tool_schema_for_azure(name, schema)
        assert report.compatible is True, (name, report.issues)


def test_propose_enforces_catalog_timeout() -> None:
    contract = tool_by_name("propose_restart_workload")
    assert contract["timeout_seconds"] == 10
    plane = ControlPlane()
    result = propose_restart_workload(
        {
            "incident_run_id": str(uuid4()),
            "service": "checkout",
            "rationale": "restart after 5xx evidence",
            "expected_effect": "recover",
        },
        plane=plane,
        runtime=ToolRuntime(
            timeout_seconds=contract["timeout_seconds"],
            max_result_bytes=16384,
            artifacts=ArtifactStore(),
        ),
    )
    assert result["ok"] is True
    assert plane.write_count() == 0
