from mcp_servers.lab.schemas import INCOMPATIBLE_AZURE_EXAMPLE, LAB_TOOL_SCHEMAS
from mcp_servers.phase2_schemas import phase2_input_schemas

from opspilot.holmes.compatibility import evaluate_catalog, validate_tool_schema_for_azure


def test_every_phase2_tool_schema_is_azure_compatible() -> None:
    for name, schema in phase2_input_schemas().items():
        report = validate_tool_schema_for_azure(name, schema)
        assert report.compatible is True, (name, report.issues)


def test_lab_and_phase2_catalog_isolates_a_single_bad_tool() -> None:
    schemas = {tool["name"]: tool["input_schema"] for tool in LAB_TOOL_SCHEMAS}
    schemas.update(phase2_input_schemas())
    schemas["broken_dynamic_tool"] = INCOMPATIBLE_AZURE_EXAMPLE
    report = evaluate_catalog(schemas)
    assert "broken_dynamic_tool" in report.isolated_incompatible_tools
    assert "query_service_metrics" in report.compatible_tools
    assert "search_runbooks" in report.compatible_tools
    assert "lab_status" in report.compatible_tools
    assert report.catalog_usable is True
    assert all(issue.tool_name == "broken_dynamic_tool" for issue in report.issues)


def test_oneof_anyof_ref_are_rejected_by_the_suite() -> None:
    cases = {
        "uses_oneof": {"type": "object", "properties": {"x": {"oneOf": [{"type": "string"}]}}},
        "uses_anyof": {
            "type": "object",
            "properties": {"x": {"anyOf": [{"type": "string"}, {"type": "null"}]}},
        },
        "uses_ref": {"type": "object", "properties": {"x": {"$ref": "#/$defs/X"}}},
        "object_without_properties": {"type": "object"},
    }
    for name, schema in cases.items():
        report = validate_tool_schema_for_azure(name, schema)
        assert report.compatible is False, name


def test_fastmcp_generated_schemas_are_azure_compatible() -> None:
    from mcp_servers.common.fastmcp_schemas import fastmcp_input_schemas
    from mcp_servers.deployments.server import mcp as deployments_mcp
    from mcp_servers.observability.server import mcp as observability_mcp
    from mcp_servers.runbooks.server import mcp as runbooks_mcp

    generated = {}
    generated.update(fastmcp_input_schemas(observability_mcp))
    generated.update(fastmcp_input_schemas(deployments_mcp))
    generated.update(fastmcp_input_schemas(runbooks_mcp))
    expected = set(phase2_input_schemas())
    assert expected <= set(generated)
    for name in expected:
        report = validate_tool_schema_for_azure(name, generated[name])
        assert report.compatible is True, (name, report.issues)
