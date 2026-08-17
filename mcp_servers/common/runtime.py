from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from dataclasses import dataclass
from typing import Any

from mcp_servers.common.artifacts import ArtifactStore
from mcp_servers.common.budget import apply_budget
from mcp_servers.common.errors import BackendError, structured_error
from mcp_servers.contracts import tool_by_name


@dataclass
class ToolRuntime:
    timeout_seconds: int
    max_result_bytes: int
    artifacts: ArtifactStore

    @classmethod
    def from_catalog(cls, tool: str, artifacts: ArtifactStore | None = None) -> ToolRuntime:
        contract = tool_by_name(tool)
        return cls(
            timeout_seconds=contract["timeout_seconds"],
            max_result_bytes=contract["max_result_bytes"],
            artifacts=artifacts or ArtifactStore(),
        )


def run_with_timeout[T](fn: Callable[[], T], timeout_seconds: float) -> T:
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fn)
        try:
            return future.result(timeout=timeout_seconds)
        except FuturesTimeout as exc:
            raise TimeoutError(f"tool exceeded {timeout_seconds}s") from exc


def invoke_tool(
    tool: str,
    handler: Callable[[], dict[str, Any]],
    runtime: ToolRuntime,
    *,
    params: dict[str, Any],
    time_range: dict[str, str] | None = None,
) -> dict[str, Any]:
    try:
        payload = run_with_timeout(handler, runtime.timeout_seconds)
    except TimeoutError:
        return structured_error(
            tool,
            error_type="timeout",
            message=f"{tool} exceeded {runtime.timeout_seconds}s",
            retryable=True,
            suggested_fix="narrow the time range or retry",
            params=params,
            time_range=time_range,
        )
    except BackendError as exc:
        return structured_error(
            tool,
            error_type="backend",
            message=str(exc),
            retryable=exc.retryable,
            suggested_fix=exc.suggested_fix,
            params=params,
            time_range=time_range,
        )
    except ValueError as exc:
        return structured_error(
            tool,
            error_type="validation",
            message=str(exc),
            retryable=True,
            suggested_fix="correct typed parameters, time range, or limit",
            params=params,
            time_range=time_range,
        )
    if payload.get("ok") is False:
        return payload
    return apply_budget(
        tool,
        payload,
        max_result_bytes=runtime.max_result_bytes,
        store=runtime.artifacts,
        time_range=time_range,
        params=params,
    )
