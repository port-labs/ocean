from datetime import datetime, timedelta, timezone
import re

from checkmarx_one.utils import days_ago_to_rfc3339


class TestDaysAgoToRfc3339:
    def test_days_ago_to_rfc3339_format(self) -> None:
        """Test that the function returns a valid RFC3339 formatted string."""
        result = days_ago_to_rfc3339(7)

        # Check that the result matches RFC3339 format with microseconds and Z suffix
        # Format: YYYY-MM-DDTHH:MM:SS.ffffffZ
        rfc3339_pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$"
        assert re.match(
            rfc3339_pattern, result
        ), f"Result {result} does not match RFC3339 format"

    def test_days_ago_to_rfc3339_zero_days(self) -> None:
        """Test conversion of 0 days ago (current time)."""
        result = days_ago_to_rfc3339(0)

        # Parse the result
        result_dt = datetime.fromisoformat(result.replace("Z", "+00:00"))
        current_time = datetime.now(timezone.utc)

        # Should be within a few seconds of current time
        time_diff = abs((current_time - result_dt).total_seconds())
        assert time_diff < 5, f"Time difference {time_diff} seconds is too large"

    def test_days_ago_to_rfc3339_one_day(self) -> None:
        """Test conversion of 1 day ago."""
        result = days_ago_to_rfc3339(1)

        # Parse the result
        result_dt = datetime.fromisoformat(result.replace("Z", "+00:00"))
        expected_dt = datetime.now(timezone.utc) - timedelta(days=1)

        # Should be within a few seconds of expected time
        time_diff = abs((expected_dt - result_dt).total_seconds())
        assert time_diff < 5, f"Time difference {time_diff} seconds is too large"

    def test_days_ago_to_rfc3339_seven_days(self) -> None:
        """Test conversion of 7 days ago."""
        result = days_ago_to_rfc3339(7)

        # Parse the result
        result_dt = datetime.fromisoformat(result.replace("Z", "+00:00"))
        expected_dt = datetime.now(timezone.utc) - timedelta(days=7)

        # Should be within a few seconds of expected time
        time_diff = abs((expected_dt - result_dt).total_seconds())
        assert time_diff < 5, f"Time difference {time_diff} seconds is too large"

    def test_days_ago_to_rfc3339_ninety_days(self) -> None:
        """Test conversion of 90 days ago."""
        result = days_ago_to_rfc3339(90)

        # Parse the result
        result_dt = datetime.fromisoformat(result.replace("Z", "+00:00"))
        expected_dt = datetime.now(timezone.utc) - timedelta(days=90)

        # Should be within a few seconds of expected time
        time_diff = abs((expected_dt - result_dt).total_seconds())
        assert time_diff < 5, f"Time difference {time_diff} seconds is too large"

    def test_days_ago_to_rfc3339_returns_utc_time(self) -> None:
        """Test that the function returns UTC time with Z suffix."""
        result = days_ago_to_rfc3339(5)

        # Check that result ends with Z (indicating UTC/Zulu time)
        assert result.endswith("Z"), "Result should end with 'Z' for UTC time"

        # Parse and verify it's UTC
        result_dt = datetime.fromisoformat(result.replace("Z", "+00:00"))
        assert result_dt.tzinfo == timezone.utc, "Result should be in UTC timezone"

    def test_days_ago_to_rfc3339_microseconds_precision(self) -> None:
        """Test that the function includes microseconds precision."""
        result = days_ago_to_rfc3339(10)

        # Check that result contains microseconds (6 digits after the decimal point)
        assert "." in result, "Result should contain decimal point for microseconds"

        # Extract microseconds part
        microseconds_part = result.split(".")[-1].replace("Z", "")
        assert (
            len(microseconds_part) == 6
        ), f"Microseconds part should have 6 digits, got {len(microseconds_part)}"

    def test_days_ago_to_rfc3339_consistency(self) -> None:
        """Test that multiple calls return consistent results (within a short time)."""
        result1 = days_ago_to_rfc3339(30)
        result2 = days_ago_to_rfc3339(30)

        # Parse both results
        dt1 = datetime.fromisoformat(result1.replace("Z", "+00:00"))
        dt2 = datetime.fromisoformat(result2.replace("Z", "+00:00"))

        # Should be within a few seconds of each other
        time_diff = abs((dt1 - dt2).total_seconds())
        assert (
            time_diff < 2
        ), f"Results should be consistent within 2 seconds, got {time_diff}"

    def test_days_ago_to_rfc3339_positive_days(self) -> None:
        """Test that the function works with various positive day values."""
        test_cases = [1, 7, 14, 30, 60, 90]

        for days in test_cases:
            result = days_ago_to_rfc3339(days)

            # Verify format
            rfc3339_pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$"
            assert re.match(
                rfc3339_pattern, result
            ), f"Result for {days} days does not match RFC3339 format"

            # Verify date is in the past
            result_dt = datetime.fromisoformat(result.replace("Z", "+00:00"))
            assert result_dt < datetime.now(
                timezone.utc
            ), f"Result for {days} days should be in the past"

    def test_days_ago_to_rfc3339_large_days(self) -> None:
        """Test that the function handles large day values."""
        result = days_ago_to_rfc3339(365)

        # Parse the result
        result_dt = datetime.fromisoformat(result.replace("Z", "+00:00"))
        expected_dt = datetime.now(timezone.utc) - timedelta(days=365)

        # Should be within a few seconds of expected time
        time_diff = abs((expected_dt - result_dt).total_seconds())
        assert time_diff < 5, f"Time difference {time_diff} seconds is too large"
