from datetime import UTC, datetime

from opspilot.investigation.window import window_from_onset


def test_window_from_onset_starts_near_inject_not_ten_minutes_earlier() -> None:
    now = datetime(2026, 8, 17, 14, 44, 0, tzinfo=UTC)
    window = window_from_onset("2026-08-17T14:43:20Z", now=now)
    assert window.start == "2026-08-17T14:42:50Z"
    assert window.end == "2026-08-17T14:44:00Z"
