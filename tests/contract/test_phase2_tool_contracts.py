from mcp_servers.contracts import PHASE2_SERVERS, phase2_tools, tool_by_name
from mcp_servers.phase2_schemas import phase2_input_schemas

PHASE2_NAMES = {
    "query_service_metrics",
    "query_service_logs",
    "get_trace_summary",
    "get_recent_deployments",
    "compare_deployments",
    "get_ci_failure_summary",
    "search_runbooks",
}


def test_phase2_catalog_covers_required_read_tools() -> None:
    tools = phase2_tools()
    names = {tool["name"] for tool in tools}
    assert names >= PHASE2_NAMES
    for tool in tools:
        assert tool["server"] in PHASE2_SERVERS
        assert tool["permission"] == "read"
        assert tool["agent_visible"] is True
        assert tool["timeout_seconds"] > 0
        assert tool["max_result_bytes"] > 0


def test_phase2_schemas_exist_for_every_catalog_tool() -> None:
    schemas = phase2_input_schemas()
    for name in PHASE2_NAMES:
        contract = tool_by_name(name)
        schema = schemas[name]
        assert schema["type"] == "object"
        assert "properties" in schema
        assert schema.get("additionalProperties") is False
        assert contract["permission"] == "read"
        if name != "search_runbooks":
            assert "start" in schema["properties"]
            assert "end" in schema["properties"]
        else:
            assert "start" in schema["properties"]
            assert "end" in schema["properties"]
            assert "query" in schema["properties"]


def test_phase2_schemas_have_no_freeform_promql_or_shell() -> None:
    forbidden = {"promql", "logql", "command", "shell", "script", "kubectl"}
    for name, schema in phase2_input_schemas().items():
        keys = set(schema.get("properties", {}))
        assert keys.isdisjoint(forbidden), name
