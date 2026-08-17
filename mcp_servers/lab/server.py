from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP
from tools import lab_echo as echo_impl
from tools import lab_mutate_probe as mutate_impl
from tools import lab_status as status_impl

mcp = FastMCP("opspilot-lab")


@mcp.tool()
def lab_status() -> dict[str, object]:
    """Read-only lab health. No arguments."""
    return status_impl()


@mcp.tool()
def lab_echo(message: str) -> dict[str, object]:
    """Echo a short message. Read-only MCP connectivity probe."""
    return echo_impl(message)


@mcp.tool()
def lab_mutate_probe(target: str) -> dict[str, object]:
    """Approval-gated probe. Refuses to mutate even if Holmes invokes it."""
    return mutate_impl(target)


if __name__ == "__main__":
    host = os.environ.get("OPSPILOT_LAB_HOST", "0.0.0.0")
    port = int(os.environ.get("OPSPILOT_LAB_PORT", "8000"))
    mcp.settings.host = host
    mcp.settings.port = port
    security = mcp.settings.transport_security
    if security is not None:
        security.enable_dns_rebinding_protection = False
    mcp.run(transport="streamable-http")
