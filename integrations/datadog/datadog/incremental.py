"""Incremental sync helpers for Datadog."""

from datetime import datetime


def windows_ending_after(
    windows: list[tuple[int, int]], cursor: datetime
) -> list[tuple[int, int]]:
    """Keep the time windows that end after *cursor*: the current window, plus any
    window that closed since *cursor*, so it gets its final values."""
    cursor_ts = int(cursor.timestamp())
    return [(from_ts, to_ts) for from_ts, to_ts in windows if to_ts > cursor_ts]
