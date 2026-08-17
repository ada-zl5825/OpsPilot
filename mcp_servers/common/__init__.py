"""Shared MCP runtime: typed errors, budgets, time ranges, and Azure schemas."""

from mcp_servers.common.artifacts import ArtifactStore
from mcp_servers.common.errors import structured_error
from mcp_servers.common.null_args import drop_null_arguments, install_null_arg_coercion
from mcp_servers.common.runtime import ToolRuntime, invoke_tool
from mcp_servers.common.schemas import azure_input_schema
from mcp_servers.common.time_range import TimeWindow, parse_time_range

__all__ = [
    "ArtifactStore",
    "TimeWindow",
    "ToolRuntime",
    "azure_input_schema",
    "drop_null_arguments",
    "install_null_arg_coercion",
    "invoke_tool",
    "parse_time_range",
    "structured_error",
]
