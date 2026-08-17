from mcp_servers.common.fastmcp_schemas import fastmcp_input_schemas
from mcp_servers.contracts import agent_visible_tools
from mcp_servers.remediation.server import mcp as remediation_mcp


def test_agent_catalog_excludes_execute_and_rollback() -> None:
    names = {tool["name"] for tool in agent_visible_tools()}
    assert "execute_approved_proposal" not in names
    assert "rollback_execution" not in names
    registered = set(fastmcp_input_schemas(remediation_mcp))
    assert "execute_approved_proposal" not in registered
    assert "rollback_execution" not in registered
