from datetime import UTC, datetime, timedelta

from opspilot.investigation.window import WINDOW_SLACK_SECONDS, window_from_onset


def test_window_from_onset_starts_near_inject_not_ten_minutes_earlier() -> None:
    now = datetime(2026, 8, 17, 14, 44, 0, tzinfo=UTC)
    window = window_from_onset("2026-08-17T14:43:20Z", now=now)
    assert WINDOW_SLACK_SECONDS == 5
    assert window.start == "2026-08-17T14:43:15Z"
    assert window.end == "2026-08-17T14:44:15Z"


def test_window_from_onset_does_not_pull_start_before_onset_slack() -> None:
    now = datetime(2026, 8, 17, 14, 43, 25, tzinfo=UTC)
    window = window_from_onset("2026-08-17T14:43:20Z", now=now)
    onset = datetime(2026, 8, 17, 14, 43, 20, tzinfo=UTC)
    start = datetime.fromisoformat(window.start.replace("Z", "+00:00"))
    assert start == onset - timedelta(seconds=WINDOW_SLACK_SECONDS)
    assert start >= onset - timedelta(seconds=WINDOW_SLACK_SECONDS)
