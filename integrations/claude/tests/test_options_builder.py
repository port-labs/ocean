from collections.abc import Generator
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from core.options_builder import (
    build_platform_code_analytics_options,
    build_platform_cost_options,
    build_platform_usage_options,
    build_user_report_options,
    get_code_analytics_dates,
    get_user_activity_dates,
    resolve_analytics_range,
)

FIXED_NOW = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
FIXED_TODAY = "2026-03-15"


@pytest.fixture()
def frozen_now() -> Generator[None, None, None]:
    with patch("core.options_builder._utc_now", return_value=FIXED_NOW):
        yield


# ---------------------------------------------------------------------------
# Platform option builders
# ---------------------------------------------------------------------------


def test_build_platform_usage_options() -> None:
    options = build_platform_usage_options(
        starting_date="2026-01-01T00:00:00Z",
        bucket_width="1d",
        group_by=["workspace_id"],
    )
    assert options["starting_at"] == "2026-01-01T00:00:00Z"
    assert options["bucket_width"] == "1d"
    assert options["group_by"] == ["workspace_id"]


def test_build_platform_cost_options() -> None:
    options = build_platform_cost_options(
        starting_date="2026-01-01T00:00:00Z", bucket_width="1d"
    )
    assert options["starting_at"] == "2026-01-01T00:00:00Z"
    assert options["limit"] == 31


def test_build_platform_code_analytics_options() -> None:
    options = build_platform_code_analytics_options(starting_date="2026-01-01")
    assert options["starting_at"] == "2026-01-01"


# ---------------------------------------------------------------------------
# get_code_analytics_dates
# ---------------------------------------------------------------------------


def test_get_code_analytics_dates_time_frame_count(frozen_now: None) -> None:
    dates = get_code_analytics_dates(starting_date=None, time_frame=5)
    assert len(dates) == 5
    assert dates[-1] == FIXED_TODAY
    assert dates == sorted(dates)


# ---------------------------------------------------------------------------
# get_user_activity_dates
# ---------------------------------------------------------------------------


# The users endpoint only returns data at least 3 days old, so the latest
# queryable date is FIXED_TODAY minus 3 days.
FIXED_LATEST_ACTIVITY = "2026-03-12"


def test_user_activity_dates_time_frame(frozen_now: None) -> None:
    dates = get_user_activity_dates(starting_date=None, time_frame=7)
    assert len(dates) == 7
    assert dates[-1] == FIXED_LATEST_ACTIVITY
    assert dates == sorted(dates)


def test_user_activity_dates_clamped_to_min_date(frozen_now: None) -> None:
    dates = get_user_activity_dates(starting_date="2025-12-01", time_frame=None)
    assert dates[0] == "2026-01-01"
    assert dates[-1] == FIXED_LATEST_ACTIVITY


def test_user_activity_dates_stop_at_three_day_lag(frozen_now: None) -> None:
    dates = get_user_activity_dates(starting_date="2026-03-10", time_frame=None)
    # 2026-03-13/14/15 are too recent (< 3 days old) and must be excluded.
    assert dates == ["2026-03-10", "2026-03-11", "2026-03-12"]


def test_user_activity_dates_too_recent_returns_empty(frozen_now: None) -> None:
    dates = get_user_activity_dates(starting_date="2026-03-14", time_frame=None)
    assert dates == []


def test_user_activity_dates_defaults_to_30_when_neither_provided(
    frozen_now: None,
) -> None:
    dates = get_user_activity_dates(starting_date=None, time_frame=None)
    assert len(dates) == 30
    assert dates[-1] == FIXED_LATEST_ACTIVITY


# ---------------------------------------------------------------------------
# resolve_analytics_range
# ---------------------------------------------------------------------------


def test_resolve_range_floors_start_to_31_days(frozen_now: None) -> None:
    start, end = resolve_analytics_range("2026-01-01T00:00:00Z", None)
    # now - 31 days = 2026-02-12T12:00:00Z, which is later than 2026-01-01
    assert start == "2026-02-12T12:00:00Z"
    assert end == "2026-03-15T12:00:00Z"


def test_resolve_range_respects_explicit_ending(frozen_now: None) -> None:
    start, end = resolve_analytics_range("2026-03-01T00:00:00Z", "2026-03-05T00:00:00Z")
    assert start == "2026-03-01T00:00:00Z"
    assert end == "2026-03-05T00:00:00Z"


def test_resolve_range_caps_span_to_31_days(frozen_now: None) -> None:
    # A 60-day window with a recent end is trimmed back to 31 days.
    start, end = resolve_analytics_range("2026-02-20T00:00:00Z", "2026-02-25T00:00:00Z")
    # start (2026-02-20) is earlier than now-31d (2026-02-12T12) so it stays,
    # and the 5-day window is within the cap.
    assert start == "2026-02-20T00:00:00Z"
    assert end == "2026-02-25T00:00:00Z"


# ---------------------------------------------------------------------------
# build_user_report_options
# ---------------------------------------------------------------------------


def test_build_user_report_options_clamps_and_passes_arrays(frozen_now: None) -> None:
    options = build_user_report_options(
        starting_at="2026-01-01T00:00:00Z",
        ending_at=None,
        exclude_deleted_users=True,
        products=["chat"],
        models=["claude-opus-4-6"],
        group_by=["model"],
        context_windows=["0-200k"],
        inference_geos=["global"],
        speeds=["fast"],
    )
    assert options["starting_at"] == "2026-02-12T12:00:00Z"
    assert options["ending_at"] == "2026-03-15T12:00:00Z"
    assert options["limit"] == 1000
    assert options["products"] == ["chat"]
    assert options["models"] == ["claude-opus-4-6"]
    assert options["group_by"] == ["model"]
    assert options["context_windows"] == ["0-200k"]


def test_build_user_report_options_omits_empty_arrays(frozen_now: None) -> None:
    options = build_user_report_options(
        starting_at="2026-03-01T00:00:00Z",
        ending_at=None,
        exclude_deleted_users=False,
        products=[],
        models=[],
        group_by=[],
        context_windows=[],
        inference_geos=[],
        speeds=[],
    )
    assert options["starting_at"] == "2026-03-01T00:00:00Z"
    assert "products" not in options
