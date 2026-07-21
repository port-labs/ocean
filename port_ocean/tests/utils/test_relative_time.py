from datetime import datetime, timedelta, timezone

from dateutil.relativedelta import relativedelta

from port_ocean.utils.relative_time import days_ago, months_ago, to_rfc3339

FROZEN_NOW = datetime(2026, 7, 21, 12, 30, 45, 123456, tzinfo=timezone.utc)


def test_days_ago() -> None:
    assert days_ago(7, now=FROZEN_NOW) == FROZEN_NOW - timedelta(days=7)


def test_days_ago_negative_is_future() -> None:
    assert days_ago(-3, now=FROZEN_NOW) == FROZEN_NOW + timedelta(days=3)


def test_months_ago_calendar() -> None:
    end_of_jan = datetime(2026, 1, 31, 12, 0, 0, tzinfo=timezone.utc)
    assert months_ago(1, now=end_of_jan) == datetime(
        2025, 12, 31, 12, 0, 0, tzinfo=timezone.utc
    )


def test_months_ago_negative_is_future() -> None:
    assert months_ago(-2, now=FROZEN_NOW) == FROZEN_NOW + relativedelta(months=2)


def test_to_rfc3339_seconds() -> None:
    assert to_rfc3339(FROZEN_NOW) == "2026-07-21T12:30:45Z"


def test_to_rfc3339_microseconds() -> None:
    assert to_rfc3339(FROZEN_NOW, timespec="microseconds") == (
        "2026-07-21T12:30:45.123456Z"
    )
