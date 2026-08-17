from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP


def run_streamable_http(mcp: FastMCP, default_port: int) -> None:
    host = os.environ.get("OPSPILOT_MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("OPSPILOT_MCP_PORT", str(default_port)))
    mcp.settings.host = host
    mcp.settings.port = port
    security = mcp.settings.transport_security
    if security is not None:
        security.enable_dns_rebinding_protection = False
    mcp.run(transport="streamable-http")
