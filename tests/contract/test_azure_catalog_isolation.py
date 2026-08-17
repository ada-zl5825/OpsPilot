from mcp_servers.lab.schemas import INCOMPATIBLE_AZURE_EXAMPLE, LAB_TOOL_SCHEMAS

from opspilot.holmes.compatibility import evaluate_catalog, validate_tool_schema_for_azure


def test_lab_tools_are_azure_compatible() -> None:
    for tool in LAB_TOOL_SCHEMAS:
        report = validate_tool_schema_for_azure(tool["name"], tool["input_schema"])
        assert report.compatible is True, report.issues


def test_incompatible_tool_is_isolated_from_catalog() -> None:
    schemas = {tool["name"]: tool["input_schema"] for tool in LAB_TOOL_SCHEMAS}
    schemas["broken_dynamic_tool"] = INCOMPATIBLE_AZURE_EXAMPLE
    report = evaluate_catalog(schemas)
    assert "broken_dynamic_tool" in report.isolated_incompatible_tools
    assert "lab_status" in report.compatible_tools
    assert "lab_echo" in report.compatible_tools
    assert report.catalog_usable is True
