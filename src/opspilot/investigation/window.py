from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pydantic import BaseModel

WINDOW_SLACK_SECONDS = 30
MIN_WINDOW_SECONDS = 60


class InvestigationWindow(BaseModel):
    """Control-plane investigation clock. Not a root-cause hint."""

    start: str
    end: str


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso8601(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def window_from_onset(injected_at: str, *, now: datetime | None = None) -> InvestigationWindow:
    onset = parse_iso8601(injected_at)
    end = now or datetime.now(UTC)
    start = onset - timedelta(seconds=WINDOW_SLACK_SECONDS)
    if (end - start).total_seconds() < MIN_WINDOW_SECONDS:
        start = end - timedelta(seconds=MIN_WINDOW_SECONDS)
    return InvestigationWindow(start=_iso(start), end=_iso(end))
