from collections.abc import Generator
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from core.options_builder import (
    build_cost_options,
    build_usage_options,
    build_user_activity_options,
    get_daily_dates,
)

FIXED_UTC = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
FIXED_DATE = "2026-01-01"


@pytest.fixture()
def frozen_utc() -> Generator[None, None, None]:
    with patch("core.options_builder.datetime") as mock_dt:
        mock_dt.now.return_value = FIXED_UTC
        yield


# ---------------------------------------------------------------------------
# build_usage_options
# ---------------------------------------------------------------------------


def test_build_usage_options_passes_starting_date() -> None:
    options = build_usage_options(
        starting_date="2026-01-01T00:00:00Z", bucket_width="1d", group_by=[]
    )
    assert options["starting_at"] == "2026-01-01T00:00:00Z"


# ---------------------------------------------------------------------------
# build_cost_options
# ---------------------------------------------------------------------------


def test_build_cost_options_passes_starting_date() -> None:
    options = build_cost_options(
        starting_date="2026-01-01T00:00:00Z", bucket_width="1d"
    )
    assert options["starting_at"] == "2026-01-01T00:00:00Z"


def test_build_cost_options_passes_group_by() -> None:
    options = build_cost_options(
        starting_date="2026-01-01T00:00:00Z",
        bucket_width="1d",
        group_by=["cost_type"],
    )
    assert options["group_by"] == ["cost_type"]


# ---------------------------------------------------------------------------
# build_user_activity_options
# ---------------------------------------------------------------------------


def test_build_user_activity_options_passes_date() -> None:
    options = build_user_activity_options(date="2026-01-01")
    assert options["date"] == "2026-01-01"


# ---------------------------------------------------------------------------
# get_daily_dates — timeFrame
# ---------------------------------------------------------------------------


def test_get_daily_dates_time_frame_count(frozen_utc: None) -> None:
    dates = get_daily_dates(starting_date=None, time_frame=5)
    assert len(dates) == 5


def test_get_daily_dates_time_frame_ends_on_today(frozen_utc: None) -> None:
    dates = get_daily_dates(starting_date=None, time_frame=5)
    assert dates[-1] == FIXED_DATE


def test_get_daily_dates_time_frame_is_chronological(frozen_utc: None) -> None:
    dates = get_daily_dates(starting_date=None, time_frame=5)
    assert dates == sorted(dates)


def test_get_daily_dates_time_frame_1_returns_today(frozen_utc: None) -> None:
    dates = get_daily_dates(starting_date=None, time_frame=1)
    assert dates == [FIXED_DATE]


# ---------------------------------------------------------------------------
# get_daily_dates — startingDate
# ---------------------------------------------------------------------------


def test_get_daily_dates_starting_date_includes_today(
    frozen_utc: None,
) -> None:
    dates = get_daily_dates(starting_date="2025-12-30", time_frame=None)
    assert dates[-1] == FIXED_DATE


def test_get_daily_dates_starting_date_includes_start(
    frozen_utc: None,
) -> None:
    dates = get_daily_dates(starting_date="2025-12-30", time_frame=None)
    assert dates[0] == "2025-12-30"


def test_get_daily_dates_starting_date_is_chronological(
    frozen_utc: None,
) -> None:
    dates = get_daily_dates(starting_date="2025-12-29", time_frame=None)
    assert dates == sorted(dates)


def test_get_daily_dates_starting_date_correct_count(
    frozen_utc: None,
) -> None:
    # 2025-12-30 → 2026-01-01 inclusive = 3 days
    dates = get_daily_dates(starting_date="2025-12-30", time_frame=None)
    assert len(dates) == 3


def test_get_daily_dates_starting_today_returns_single_day(
    frozen_utc: None,
) -> None:
    dates = get_daily_dates(starting_date=FIXED_DATE, time_frame=None)
    assert dates == [FIXED_DATE]


def test_get_daily_dates_future_starting_date_returns_empty(
    frozen_utc: None,
) -> None:
    from datetime import timedelta

    future = (FIXED_UTC + timedelta(days=30)).date().isoformat()
    dates = get_daily_dates(starting_date=future, time_frame=None)
    assert dates == []


# ---------------------------------------------------------------------------
# UTC correctness
# ---------------------------------------------------------------------------


def test_get_daily_dates_uses_utc_clock() -> None:
    with patch("core.options_builder.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 1, 1, 1, 30, 0, tzinfo=timezone.utc)
        dates = get_daily_dates(starting_date=None, time_frame=1)

    assert dates == ["2026-01-01"]
    mock_dt.now.assert_called_once_with(timezone.utc)
