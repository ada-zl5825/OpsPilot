from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

MIN_WINDOW_SECONDS = 60
MAX_WINDOW_SECONDS = 6 * 60 * 60
FUTURE_SLACK = timedelta(minutes=5)


@dataclass(frozen=True)
class TimeWindow:
    start: datetime
    end: datetime

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
    return window


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
