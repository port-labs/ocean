import time
from datetime import datetime
from freezegun import freeze_time

from utils import (
    get_start_of_the_day_in_seconds_x_day_back,
    generate_time_windows_from_interval_days,
)


def test_get_start_of_the_day_in_seconds_x_day_back() -> None:
    # Freeze time to a known date for consistent testing
    with freeze_time("2024-03-15 14:30:00"):
        # Test same day (0 days back)
        result = get_start_of_the_day_in_seconds_x_day_back(0)
        expected = int(datetime(2024, 3, 15, 0, 0, 0).timestamp())
        assert result == expected

        # Test previous day
        result = get_start_of_the_day_in_seconds_x_day_back(1)
        expected = int(datetime(2024, 3, 14, 0, 0, 0).timestamp())
        assert result == expected

        # Test month boundary
        result = get_start_of_the_day_in_seconds_x_day_back(15)
        expected = int(datetime(2024, 2, 29, 0, 0, 0).timestamp())
        assert result == expected

        # Test year boundary
        result = get_start_of_the_day_in_seconds_x_day_back(75)
        expected = int(datetime(2023, 12, 31, 0, 0, 0).timestamp())
        assert result == expected


def test_generate_time_windows_from_interval_days() -> None:
    current_time = int(time.time())
    day_in_seconds = 24 * 60 * 60

    # Test with 1-day interval
    start_timestamp = current_time - (3 * day_in_seconds)  # 3 days ago
    result = generate_time_windows_from_interval_days(1, start_timestamp)

    assert len(result) == 3
    for i, (start, end) in enumerate(result[:-1]):
        assert end - start == day_in_seconds
        assert start == start_timestamp + (i * day_in_seconds)

    # Last interval should end at current time
    assert result[-1][1] == current_time

    # Test with 2-day interval
    start_timestamp = current_time - (6 * day_in_seconds)  # 6 days ago
    result = generate_time_windows_from_interval_days(2, start_timestamp)

    assert len(result) == 3
    for i, (start, end) in enumerate(result[:-1]):
        assert end - start == 2 * day_in_seconds
        assert start == start_timestamp + (i * 2 * day_in_seconds)

    # Last interval should end at current time
    assert result[-1][1] == current_time
