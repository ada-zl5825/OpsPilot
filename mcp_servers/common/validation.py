from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from mcp_servers.common.errors import structured_error
from mcp_servers.common.null_args import drop_null_arguments
from mcp_servers.common.time_range import TimeWindow, parse_time_range


def parse_model(model_type: type[Any], params: dict[str, Any]) -> Any:
    return model_type.model_validate(drop_null_arguments(params))


def validation_failure(
    tool: str,
    exc: Exception,
    params: dict[str, Any],
    time_range: dict[str, str] | None = None,
) -> dict[str, Any]:
    message = _message(exc)
    return structured_error(
        tool,
        error_type="validation",
        message=message,
        retryable=True,
        suggested_fix="use enum values, a valid ISO-8601 window, and an in-range limit",
        params=params,
        time_range=time_range,
    )


def window_or_error(
    tool: str,
    start: str,
    end: str,
    params: dict[str, Any],
) -> TimeWindow | dict[str, Any]:
    try:
        return parse_time_range(start, end)
    except ValueError as exc:
        return validation_failure(tool, exc, params, {"start": start, "end": end})


def _message(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        first = exc.errors()[0]
        loc = ".".join(str(part) for part in first.get("loc", ()))
        msg = str(first.get("msg", exc))
        return f"{loc}: {msg}"[:240] if loc else msg[:240]
    return str(exc)[:240]
