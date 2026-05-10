from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from core.options_builder import (
    build_code_analytics_options,
    build_cost_options,
    build_usage_options,
)

FIXED_UTC = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
FIXED_DATE = "2026-01-01"
FIXED_DATETIME = "2026-01-01T00:00:00Z"


@pytest.fixture()
def frozen_utc():
    with patch("core.options_builder.datetime") as mock_dt:
        mock_dt.now.return_value = FIXED_UTC
        yield


def test_build_usage_options_defaults_to_today_utc(frozen_utc):
    options = build_usage_options(starting_date=None, bucket_width="1d", group_by=[])
    assert options["starting_at"] == FIXED_DATETIME


def test_build_usage_options_respects_explicit_date(frozen_utc):
    options = build_usage_options(
        starting_date="2026-01-01T00:00:00Z", bucket_width="1d", group_by=[]
    )
    assert options["starting_at"] == "2026-01-01T00:00:00Z"


def test_build_cost_options_defaults_to_today_utc(frozen_utc):
    options = build_cost_options(starting_date=None, bucket_width="1d")
    assert options["starting_at"] == FIXED_DATETIME


def test_build_cost_options_respects_explicit_date(frozen_utc):
    options = build_cost_options(starting_date="2026-01-01T00:00:00Z", bucket_width="1d")
    assert options["starting_at"] == "2026-01-01T00:00:00Z"


def test_build_code_analytics_options_defaults_to_today_iso(frozen_utc):
    options = build_code_analytics_options(starting_date=None)
    assert options["starting_at"] == FIXED_DATE


def test_build_code_analytics_options_respects_explicit_date(frozen_utc):
    options = build_code_analytics_options(starting_date="2026-01-01")
    assert options["starting_at"] == "2026-01-01"


def test_default_date_derived_from_utc_not_local():
    """Date must come from UTC clock — host timezone must not influence the value."""
    with patch("core.options_builder.datetime") as mock_dt:
        # Simulate a host one day behind UTC (e.g. UTC-1 at 00:30 local = 01:30 UTC next day)
        mock_dt.now.return_value = datetime(2026, 1, 1, 1, 30, 0, tzinfo=timezone.utc)
        options = build_code_analytics_options(starting_date=None)

    assert options["starting_at"] == "2026-01-01"
    mock_dt.now.assert_called_once_with(timezone.utc)
