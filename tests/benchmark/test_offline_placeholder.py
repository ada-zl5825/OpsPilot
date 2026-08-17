from mcp_servers.contracts import mutate_tools


def test_offline_gate_keeps_mutate_tools_hidden() -> None:
    assert all(not tool["agent_visible"] for tool in mutate_tools())
