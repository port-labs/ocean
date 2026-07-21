"""Relative lookback helpers for integration selectors.

Returns UTC datetimes; format with ``to_rfc3339`` when an API wants a string.

Keep vendor-specific behavior local (start-of-day/month snaps, ``30d`` strings,
search prefixes like ``>=...``, window partitioning, API clamps).
"""

from datetime import datetime, timedelta, timezone
from typing import Literal

from dateutil.relativedelta import relativedelta

Rfc3339Timespec = Literal["seconds", "microseconds"]


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def days_ago(days: int, *, now: datetime | None = None) -> datetime:
    """UTC datetime ``days`` ago (negative ``days`` = in the future)."""
    current = _as_utc(now) if now is not None else datetime.now(timezone.utc)
    return current - timedelta(days=days)


def months_ago(months: int, *, now: datetime | None = None) -> datetime:
    """UTC datetime ``months`` calendar months ago (negative = in the future)."""
    current = _as_utc(now) if now is not None else datetime.now(timezone.utc)
    return current - relativedelta(months=months)


def to_rfc3339(
    value: datetime,
    *,
    timespec: Rfc3339Timespec = "seconds",
) -> str:
    """Format a datetime as RFC3339 UTC ending in ``Z``."""
    return _as_utc(value).isoformat(timespec=timespec).replace("+00:00", "Z")
