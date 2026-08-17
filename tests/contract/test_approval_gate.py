from mcp_servers.lab.schemas import LAB_TOOL_SCHEMAS
from mcp_servers.lab.tools import lab_mutate_probe


def test_mutate_probe_requires_approval_in_contract() -> None:
    probe = next(tool for tool in LAB_TOOL_SCHEMAS if tool["name"] == "lab_mutate_probe")
    assert probe["requires_approval"] is True
    assert probe["permission"] == "mutate"


def test_mutate_probe_never_executes_write() -> None:
    result = lab_mutate_probe("checkout")
    assert result["ok"] is False
    assert result["error_type"] == "approval_required"
    assert result["safe_params"]["target"] == "checkout"
