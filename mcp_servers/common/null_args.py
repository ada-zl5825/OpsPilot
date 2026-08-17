from __future__ import annotations

from typing import Any

_INSTALLED_MCP_IDS: set[int] = set()


def drop_null_arguments(params: dict[str, Any] | None) -> dict[str, Any]:
    """Drop JSON nulls so optional fields use schema defaults.

    Azure / gpt-4o often sends ``null`` for unused optional tool arguments.
    FastMCP Pydantic models type those fields as ``str`` (not ``str | None``)
    so the advertised schema stays Azure-safe. Removing the key is equivalent
    to omitting the argument.
    """
    if not params:
        return {}
    return {key: value for key, value in params.items() if value is not None}


def install_null_arg_coercion(mcp: Any) -> Any:
    """Strip null tool arguments before FastMCP validates the call."""
    marker = id(mcp)
    if marker in _INSTALLED_MCP_IDS:
        return mcp
    manager = getattr(mcp, "_tool_manager", None)
    if manager is None:
        return mcp
    original = manager.call_tool

    async def call_tool(
        name: str,
        arguments: dict[str, Any],
        context: Any = None,
        convert_result: bool = False,
    ) -> Any:
        return await original(
            name,
            drop_null_arguments(arguments),
            context=context,
            convert_result=convert_result,
        )

    manager.call_tool = call_tool
    _INSTALLED_MCP_IDS.add(marker)
    return mcp
