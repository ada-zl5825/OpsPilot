from opspilot.holmes.compatibility import validate_tool_schema_for_azure


def test_plain_object_schema_is_compatible() -> None:
    schema = {
        "type": "object",
        "properties": {
            "service": {"type": "string"},
            "limit": {"type": "integer"},
        },
        "required": ["service"],
    }
    report = validate_tool_schema_for_azure("query_service_logs", schema)
    assert report.compatible is True


def test_oneof_is_reported() -> None:
    schema = {
        "type": "object",
        "properties": {
            "target": {"oneOf": [{"type": "string"}, {"type": "integer"}]},
        },
    }
    report = validate_tool_schema_for_azure("bad_tool", schema)
    assert report.compatible is False
    assert report.issues[0].tool_name == "bad_tool"
