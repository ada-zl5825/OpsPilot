from __future__ import annotations

from typing import Any

from mcp_servers.common.runtime import ToolRuntime, invoke_tool
from mcp_servers.common.time_range import TimeWindow, parse_iso8601
from mcp_servers.common.validation import parse_model, validation_failure, window_or_error
from mcp_servers.runbooks.schemas import POLICY_NOTE, SearchRunbooksInput
from mcp_servers.runbooks.store import load_runbooks


def search_runbooks(
    params: dict[str, Any],
    *,
    runtime: ToolRuntime | None = None,
    catalog: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    tool = "search_runbooks"
    runtime = runtime or ToolRuntime.from_catalog(tool)
    try:
        parsed = parse_model(SearchRunbooksInput, params)
    except Exception as exc:
        return validation_failure(tool, exc, params)
    window = window_or_error(tool, parsed.start, parsed.end, params)
    if not isinstance(window, TimeWindow):
        return window
    records = catalog if catalog is not None else load_runbooks()

    def _run() -> dict[str, Any]:
        matches = [_present(item) for item in records if _matches(item, parsed, window)]
        return {
            "ok": True,
            "tool": tool,
            "query": parsed.query,
            "time_range": window.as_dict(),
            "returned": len(matches[: parsed.limit]),
            "untrusted_content": True,
            "cannot_override_policy": True,
            "permission_note": POLICY_NOTE,
            "runbooks": matches[: parsed.limit],
        }

    return invoke_tool(tool, _run, runtime, params=parsed.model_dump(), time_range=window.as_dict())


def _matches(item: dict[str, Any], parsed: SearchRunbooksInput, window: TimeWindow) -> bool:
    updated = parse_iso8601(str(item.get("updated_at")))
    if updated > window.end:
        return False
    services = item.get("services") or []
    if parsed.service != "all" and parsed.service not in services:
        return False
    haystack = " ".join(
        [
            str(item.get("id", "")),
            str(item.get("title", "")),
            " ".join(str(part) for part in item.get("applies_when", [])),
            " ".join(str(part) for part in item.get("diagnostic_steps", [])),
        ]
    ).lower()
    return all(token in haystack for token in parsed.query.lower().split())


def _present(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "title": item.get("title"),
        "applies_when": item.get("applies_when", []),
        "diagnostic_steps": item.get("diagnostic_steps", []),
        "proposed_fixes": item.get("proposed_fixes", []),
        "source": item.get("source"),
        "version": item.get("version"),
        "untrusted_content": True,
        "requires_approval_for_fixes": True,
    }
