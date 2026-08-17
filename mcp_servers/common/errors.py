from __future__ import annotations

from typing import Any

from mcp_servers.common.redaction import safe_params

ERROR_TYPES = frozenset({"validation", "timeout", "backend", "not_found", "size_limit"})


def structured_error(
    tool: str,
    *,
    error_type: str,
    message: str,
    retryable: bool,
    suggested_fix: str,
    params: dict[str, Any] | None = None,
    time_range: dict[str, str] | None = None,
) -> dict[str, Any]:
    if error_type not in ERROR_TYPES:
        raise ValueError(f"unknown error_type: {error_type}")
    return {
        "ok": False,
        "tool": tool,
        "safe_params": safe_params(params or {}),
        "time_range": time_range,
        "error_type": error_type,
        "message": message,
        "retryable": retryable,
        "suggested_fix": suggested_fix,
    }


class BackendError(Exception):
    def __init__(self, message: str, *, retryable: bool = True, suggested_fix: str = "") -> None:
        super().__init__(message)
        self.retryable = retryable
        self.suggested_fix = suggested_fix or "retry after the backend recovers"


class ToolTimeoutError(Exception):
    pass
