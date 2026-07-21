"""Relative lookback helpers for integration selectors.

Returns UTC datetimes; format with ``to_rfc3339`` when an API wants a string.

Keep vendor-specific behavior local (start-of-day/month snaps, ``30d`` strings,
search prefixes like ``>=...``, window partitioning, API clamps).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

from dateutil.relativedelta import relativedelta

Rfc3339Timespec = Literal["seconds", "microseconds"]


def days_ago(days: int, *, now: datetime | None = None) -> datetime:
    """UTC datetime ``days`` ago (negative ``days`` = in the future)."""
    current = now or datetime.now(timezone.utc)
    return current - timedelta(days=days)


def months_ago(months: int, *, now: datetime | None = None) -> datetime:
    """UTC datetime ``months`` calendar months ago (negative = in the future)."""
    current = now or datetime.now(timezone.utc)
    return current - relativedelta(months=months)


def to_rfc3339(
    value: datetime,
    *,
    timespec: Rfc3339Timespec = "seconds",
) -> str:
    """Format a datetime as RFC3339 UTC ending in ``Z``."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat(timespec=timespec).replace("+00:00", "Z")
