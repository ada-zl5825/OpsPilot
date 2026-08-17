from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

MIN_WINDOW_SECONDS = 60
MAX_WINDOW_SECONDS = 6 * 60 * 60
FUTURE_SLACK = timedelta(minutes=5)
RECENT_END_SNAP_SECONDS = 120
ACTIVE_CLIP_SLACK_SECONDS = 5


@dataclass(frozen=True)
class TimeWindow:
    start: datetime
    end: datetime
    end_extended: bool = False
    start_clipped: bool = False

    @property
    def duration_seconds(self) -> float:
        return (self.end - self.start).total_seconds()

    def as_dict(self) -> dict[str, str]:
        return {"start": _iso(self.start), "end": _iso(self.end)}

    def prometheus_step(self) -> str:
        if self.duration_seconds >= 3 * 60 * 60:
            return "5m"
        if self.duration_seconds >= 30 * 60:
            return "1m"
        if self.duration_seconds >= 5 * 60:
            return "15s"
        return "10s"

    def rate_window(self) -> str:
        if self.duration_seconds >= 30 * 60:
            return "5m"
        if self.duration_seconds >= 5 * 60:
            return "1m"
        return "30s"


def parse_iso8601(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("invalid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def parse_time_range(start: str, end: str) -> TimeWindow:
    window = TimeWindow(start=parse_iso8601(start), end=parse_iso8601(end))
    if window.end <= window.start:
        raise ValueError("end must be after start")
    if window.duration_seconds < MIN_WINDOW_SECONDS:
        raise ValueError(f"time range must be at least {MIN_WINDOW_SECONDS} seconds")
    if window.duration_seconds > MAX_WINDOW_SECONDS:
        raise ValueError(f"time range must be at most {MAX_WINDOW_SECONDS} seconds")
    now = datetime.now(UTC)
    if window.end > now + FUTURE_SLACK:
        raise ValueError("end cannot be more than 5 minutes in the future")
    gap = (now - window.end).total_seconds()
    if 0 < gap <= RECENT_END_SNAP_SECONDS:
        return TimeWindow(start=window.start, end=now, end_extended=True)
    return window


def clip_to_active_incident(
    window: TimeWindow,
    *,
    not_before: datetime | None = None,
) -> TimeWindow:
    floor = not_before if not_before is not None else fetch_active_not_before()
    if floor is None:
        return window
    floor = floor - timedelta(seconds=ACTIVE_CLIP_SLACK_SECONDS)
    if window.start >= floor:
        return window
    start = floor
    if window.end <= start:
        start = window.end - timedelta(seconds=MIN_WINDOW_SECONDS)
    return TimeWindow(
        start=start,
        end=window.end,
        end_extended=window.end_extended,
        start_clipped=True,
    )


def fetch_active_not_before() -> datetime | None:
    url = os.environ.get("LAB_CONTROLLER_URL", "").rstrip("/")
    if not url:
        return None
    try:
        response = httpx.get(f"{url}/v1/active", timeout=0.4)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError, TypeError):
        return None
    if not isinstance(payload, dict) or not payload.get("active"):
        return None
    raw = payload.get("injected_at")
    if not raw:
        return None
    try:
        return parse_iso8601(str(raw))
    except ValueError:
        return None


def apply_window_flags(payload: dict[str, Any], window: TimeWindow) -> dict[str, Any]:
    if window.end_extended:
        payload["end_extended"] = True
    if window.start_clipped:
        payload["start_clipped"] = True
        if not payload.get("suggested_fix"):
            payload["suggested_fix"] = (
                "start was raised to the active incident onset; "
                "rows before that belong to another incident"
            )
    return payload


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
