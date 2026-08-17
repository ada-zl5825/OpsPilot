from __future__ import annotations

import json
from typing import Any

from mcp_servers.common.artifacts import ArtifactStore
from mcp_servers.common.errors import structured_error
from mcp_servers.common.redaction import redact_mapping


def payload_bytes(payload: Any) -> int:
    return len(json.dumps(payload, default=str, separators=(",", ":")).encode("utf-8"))


_LIST_KEYS = (
    "points",
    "entries",
    "traces",
    "deployments",
    "runbooks",
    "failures",
    "files",
)


def apply_budget(
    tool: str,
    payload: dict[str, Any],
    *,
    max_result_bytes: int,
    store: ArtifactStore,
    time_range: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    redacted = redact_mapping(payload)
    if not isinstance(redacted, dict):
        redacted = {"value": redacted}
    size = payload_bytes(redacted)
    if size <= max_result_bytes:
        redacted.setdefault("ok", True)
        redacted.setdefault("tool", tool)
        redacted.setdefault("truncated", False)
        redacted.setdefault("artifact_ref", None)
        redacted["result_bytes"] = size
        return redacted

    artifact_ref = store.spill(tool, redacted)
    for keep in (3, 1, 0):
        candidate = _truncate(redacted, keep=keep)
        candidate["ok"] = True
        candidate["tool"] = tool
        candidate["truncated"] = True
        candidate["artifact_ref"] = artifact_ref
        candidate["result_bytes"] = payload_bytes(candidate)
        if candidate["result_bytes"] <= max_result_bytes:
            return candidate
    stub = {
        "ok": True,
        "tool": tool,
        "truncated": True,
        "artifact_ref": artifact_ref,
        "time_range": time_range,
        "message": "full result spilled to artifact",
    }
    stub["result_bytes"] = payload_bytes(stub)
    if stub["result_bytes"] <= max_result_bytes:
        return stub
    return structured_error(
        tool,
        error_type="size_limit",
        message="result exceeded max_result_bytes after truncation",
        retryable=True,
        suggested_fix="narrow the time range or lower limit",
        params=params,
        time_range=time_range,
    ) | {"artifact_ref": artifact_ref}


def _truncate(payload: dict[str, Any], keep: int = 3) -> dict[str, Any]:
    trimmed = dict(payload)
    for key in _LIST_KEYS:
        value = trimmed.get(key)
        if isinstance(value, list) and value:
            trimmed[key] = value[:keep]
            trimmed[f"{key}_omitted"] = max(0, len(value) - keep)
    data = trimmed.get("data")
    if isinstance(data, dict):
        trimmed["data"] = _truncate(data, keep=keep)
    return trimmed
