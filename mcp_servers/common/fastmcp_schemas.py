from __future__ import annotations

from typing import Any


def fastmcp_input_schemas(mcp: Any) -> dict[str, dict[str, Any]]:
    """Best-effort export of FastMCP tool JSON schemas for Azure contract tests."""
    manager = getattr(mcp, "_tool_manager", None)
    tools = getattr(manager, "_tools", {}) if manager is not None else {}
    exported: dict[str, dict[str, Any]] = {}
    for name, tool in tools.items():
        schema = getattr(tool, "parameters", None)
        if not isinstance(schema, dict):
            fn_meta = getattr(tool, "fn_metadata", None)
            arg_model = getattr(fn_meta, "arg_model", None)
            if arg_model is not None:
                schema = arg_model.model_json_schema()
        if isinstance(schema, dict):
            exported[name] = schema
    return exported
