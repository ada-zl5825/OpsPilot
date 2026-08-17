from mcp_servers.contracts import TOOL_CATALOG, agent_visible_tools, mutate_tools


def test_catalog_has_at_least_six_agent_tools() -> None:
    assert len(agent_visible_tools()) >= 6


def test_mutate_tools_are_not_agent_visible() -> None:
    for tool in mutate_tools():
        assert tool["agent_visible"] is False
        assert tool["name"] in {"execute_approved_proposal", "rollback_execution"}


def test_every_tool_has_timeout_and_size_limit() -> None:
    for tool in TOOL_CATALOG:
        assert tool["timeout_seconds"] > 0
        assert tool["max_result_bytes"] > 0
