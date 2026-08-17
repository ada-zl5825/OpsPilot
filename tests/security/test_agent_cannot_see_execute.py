from mcp_servers.contracts import agent_visible_tools


def test_agent_catalog_excludes_execute_and_rollback() -> None:
    names = {tool["name"] for tool in agent_visible_tools()}
    assert "execute_approved_proposal" not in names
    assert "rollback_execution" not in names
