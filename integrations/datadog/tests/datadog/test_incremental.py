from datetime import datetime, timezone

from datadog.incremental import windows_ending_after

SINCE = datetime(2026, 11, 5, 10, 0, tzinfo=timezone.utc)


def test_windows_ending_after_keeps_open_and_just_closed_windows() -> None:
    since_ts = int(SINCE.timestamp())
    windows = [
        (since_ts - 200, since_ts - 100),  # closed before since
        (since_ts - 100, since_ts),  # ends exactly at since
        (since_ts - 50, since_ts + 50),  # closed after since
        (since_ts + 50, since_ts + 150),  # still open
    ]

    assert windows_ending_after(windows, SINCE) == windows[2:]
