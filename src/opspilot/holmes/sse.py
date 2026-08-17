from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field


class HolmesSseEvent(BaseModel):
    event: str
    data: dict[str, Any] = Field(default_factory=dict)


def parse_sse_buffer(buffer: str) -> tuple[list[HolmesSseEvent], str]:
    """Split complete SSE frames from a streaming buffer. Remainder is returned."""
    events: list[HolmesSseEvent] = []
    parts = buffer.split("\n\n")
    remainder = parts.pop() if parts else ""
    for block in parts:
        parsed = _parse_block(block)
        if parsed is not None:
            events.append(parsed)
    return events, remainder


def parse_sse_text(text: str) -> list[HolmesSseEvent]:
    events, remainder = parse_sse_buffer(text)
    if remainder.strip():
        parsed = _parse_block(remainder)
        if parsed is not None:
            events.append(parsed)
    return events


def _parse_block(block: str) -> HolmesSseEvent | None:
    event_name = "message"
    data_lines: list[str] = []
    for raw_line in block.splitlines():
        line = raw_line.rstrip("\r")
        if not line or line.startswith(":"):
            continue
        if line.startswith("event:"):
            event_name = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    if not data_lines:
        return None
    payload = "\n".join(data_lines)
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        data = {"raw": payload}
    if not isinstance(data, dict):
        data = {"value": data}
    return HolmesSseEvent(event=event_name, data=data)
