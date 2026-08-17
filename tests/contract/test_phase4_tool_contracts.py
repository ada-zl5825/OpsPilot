from mcp_servers.contracts import (
    AGENT_REMEDIATION_TOOLS,
    HIDDEN_MUTATE_TOOLS,
    agent_visible_tools,
    mutate_tools,
    phase4_agent_tools,
    tool_by_name,
)
from mcp_servers.phase4_schemas import phase4_input_schemas


def test_phase4_agent_catalog_is_propose_and_read_only() -> None:
    tools = phase4_agent_tools()
    names = {tool["name"] for tool in tools}
    assert names == AGENT_REMEDIATION_TOOLS
    for tool in tools:
        assert tool["permission"] in {"read", "propose"}
        assert tool["agent_visible"] is True
        assert tool["timeout_seconds"] > 0
        assert tool["max_result_bytes"] > 0


def test_mutate_tools_stay_hidden() -> None:
    hidden = {tool["name"] for tool in mutate_tools()}
    assert hidden == HIDDEN_MUTATE_TOOLS
    visible = {tool["name"] for tool in agent_visible_tools()}
    assert visible.isdisjoint(HIDDEN_MUTATE_TOOLS)


def test_phase4_schemas_exist_and_forbid_shell() -> None:
    forbidden = {"promql", "logql", "command", "shell", "script", "kubectl", "argv"}
    schemas = phase4_input_schemas()
    for name in AGENT_REMEDIATION_TOOLS:
        contract = tool_by_name(name)
        schema = schemas[name]
        assert schema["type"] == "object"
        assert schema.get("additionalProperties") is False
        assert set(schema.get("properties", {})).isdisjoint(forbidden)
        assert contract["agent_visible"] is True
