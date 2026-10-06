from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

import port_ocean.utils.relative_time as relative_time
from port_ocean.utils.relative_time import days_ago, months_ago, to_rfc3339

FROZEN_NOW = datetime(2026, 7, 21, 12, 30, 45, 123456, tzinfo=timezone.utc)


def _freeze_clock(monkeypatch: pytest.MonkeyPatch, frozen: datetime) -> None:
    monkeypatch.setattr(
        relative_time,
        "datetime",
        SimpleNamespace(now=lambda tz=None: frozen),
    )


@pytest.fixture
def freeze_now(monkeypatch: pytest.MonkeyPatch) -> datetime:
    _freeze_clock(monkeypatch, FROZEN_NOW)
    return FROZEN_NOW


def test_days_ago(freeze_now: datetime) -> None:
    assert days_ago(7) == datetime(2026, 7, 14, 12, 30, 45, 123456, tzinfo=timezone.utc)


def test_days_ago_negative_is_future(freeze_now: datetime) -> None:
    assert days_ago(-3) == datetime(
        2026, 7, 24, 12, 30, 45, 123456, tzinfo=timezone.utc
    )


def test_months_ago_calendar(monkeypatch: pytest.MonkeyPatch) -> None:
    _freeze_clock(monkeypatch, datetime(2026, 1, 31, 12, 0, 0, tzinfo=timezone.utc))
    assert months_ago(1) == datetime(2025, 12, 31, 12, 0, 0, tzinfo=timezone.utc)


def test_to_rfc3339_seconds() -> None:
    assert to_rfc3339(FROZEN_NOW) == "2026-07-21T12:30:45Z"


def test_to_rfc3339_microseconds() -> None:
    assert to_rfc3339(FROZEN_NOW, timespec="microseconds") == (
        "2026-07-21T12:30:45.123456Z"
    )


def test_to_rfc3339_normalizes_offset_timezone() -> None:
    offset = timezone(timedelta(hours=2))
    local = datetime(2026, 7, 21, 14, 30, 45, tzinfo=offset)
    assert to_rfc3339(local) == "2026-07-21T12:30:45Z"


def test_to_rfc3339_treats_naive_as_utc() -> None:
    naive = datetime(2026, 7, 21, 12, 30, 45)
    assert to_rfc3339(naive) == "2026-07-21T12:30:45Z"
