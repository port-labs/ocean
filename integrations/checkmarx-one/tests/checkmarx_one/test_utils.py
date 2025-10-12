import pytest
from enum import StrEnum
from datetime import datetime, timedelta, timezone
import re

from checkmarx_one.utils import ObjectKind, days_ago_to_rfc3339


class TestObjectKind:
    def test_object_kind_is_str_enum(self) -> None:
        """Test that ObjectKind inherits from StrEnum."""
        assert issubclass(ObjectKind, StrEnum)
        assert isinstance(ObjectKind.PROJECT, str)
        assert isinstance(ObjectKind.SCAN, str)
        assert isinstance(ObjectKind.API_SEC, str)
        assert isinstance(ObjectKind.SAST, str)
        assert isinstance(ObjectKind.KICS, str)

    def test_project_kind_value(self) -> None:
        """Test PROJECT enum value."""
        assert ObjectKind.PROJECT == "project"
        assert str(ObjectKind.PROJECT) == "project"

    def test_scan_kind_value(self) -> None:
        """Test SCAN enum value."""
        assert ObjectKind.SCAN == "scan"
        assert str(ObjectKind.SCAN) == "scan"

    def test_enum_members(self) -> None:
        """Test that enum has expected members."""
        expected_members = {
            "PROJECT",
            "SCAN",
            "API_SEC",
            "SAST",
            "KICS",
            "DAST_SCAN_ENVIRONMENT",
            "DAST_SCAN",
            "DAST_SCAN_RESULT",
        }
        actual_members = set(ObjectKind.__members__.keys())
        assert actual_members == expected_members

    def test_enum_values(self) -> None:
        """Test that enum has expected values."""
        expected_values = {
            "project",
            "scan",
            "api-security",
            "sast",
            "kics",
            "dast-scan-environment",
            "dast-scan",
            "dast-scan-result",
        }
        actual_values = {member.value for member in ObjectKind}
        assert actual_values == expected_values

    def test_string_comparison(self) -> None:
        """Test that enum members can be compared to strings."""
        assert ObjectKind.PROJECT == "project"
        assert ObjectKind.SCAN == "scan"
        assert ObjectKind.PROJECT != "scan"
        assert ObjectKind.SCAN != "project"

    def test_enum_iteration(self) -> None:
        """Test iterating over enum members."""
        members = list(ObjectKind)
        assert len(members) == 8
        assert ObjectKind.PROJECT in members
        assert ObjectKind.SCAN in members
        assert ObjectKind.API_SEC in members
        assert ObjectKind.SAST in members
        assert ObjectKind.KICS in members
        assert ObjectKind.DAST_SCAN_ENVIRONMENT in members
        assert ObjectKind.DAST_SCAN in members
        assert ObjectKind.DAST_SCAN_RESULT in members

    def test_enum_membership(self) -> None:
        """Test checking membership in enum."""
        assert "project" in ObjectKind._value2member_map_
        assert "scan" in ObjectKind._value2member_map_
        assert "api-security" in ObjectKind._value2member_map_
        assert "invalid" not in ObjectKind._value2member_map_

    def test_enum_from_value(self) -> None:
        """Test creating enum instances from values."""
        project_from_value = ObjectKind("project")
        scan_from_value = ObjectKind("scan")

        assert project_from_value == ObjectKind.PROJECT
        assert scan_from_value == ObjectKind.SCAN

    def test_enum_invalid_value_raises_error(self) -> None:
        """Test that invalid values raise ValueError."""
        with pytest.raises(ValueError):
            ObjectKind("invalid_kind")

    def test_enum_repr(self) -> None:
        """Test enum string representation."""
        assert repr(ObjectKind.PROJECT) == "<ObjectKind.PROJECT: 'project'>"
        assert repr(ObjectKind.SCAN) == "<ObjectKind.SCAN: 'scan'>"

    def test_enum_case_sensitivity(self) -> None:
        """Test that enum values are case sensitive."""
        assert ObjectKind.PROJECT != "PROJECT"
        assert ObjectKind.SCAN != "SCAN"

        with pytest.raises(ValueError):
            ObjectKind("PROJECT")

        with pytest.raises(ValueError):
            ObjectKind("SCAN")

    def test_dast_scan_environment_kind_value(self) -> None:
        """Test DAST_SCAN_ENVIRONMENT enum value."""
        assert ObjectKind.DAST_SCAN_ENVIRONMENT == "dast-scan-environment"
        assert str(ObjectKind.DAST_SCAN_ENVIRONMENT) == "dast-scan-environment"

    def test_dast_scan_kind_value(self) -> None:
        """Test DAST_SCAN enum value."""
        assert ObjectKind.DAST_SCAN == "dast-scan"
        assert str(ObjectKind.DAST_SCAN) == "dast-scan"

    def test_dast_scan_result_kind_value(self) -> None:
        """Test DAST_SCAN_RESULT enum value."""
        assert ObjectKind.DAST_SCAN_RESULT == "dast-scan-result"
        assert str(ObjectKind.DAST_SCAN_RESULT) == "dast-scan-result"

    def test_enum_uniqueness(self) -> None:
        """Test that enum values are unique."""
        values = [member.value for member in ObjectKind]
        assert len(values) == len(set(values))

    def test_enum_docstring(self) -> None:
        """Test that enum has a docstring."""
        assert ObjectKind.__doc__ == "Enum for Checkmarx One resource kinds."

    def test_enum_immutability(self) -> None:
        """Test that enum members are immutable."""
        # Enum values are read-only
        project_enum = ObjectKind.PROJECT
        assert project_enum.value == "project"

        # Can't modify the enum value property
        try:
            project_enum.value = "modified"  # type: ignore[misc]
            assert False, "Should not be able to modify enum value"
        except AttributeError:
            pass  # Expected behavior

        # Original value unchanged
        assert project_enum.value == "project"


class TestDaysAgoToRfc3339:
    def test_days_ago_to_rfc3339_format(self) -> None:
        """Test that the function returns a valid RFC3339 formatted string."""
        result = days_ago_to_rfc3339(7)
        
        # Check that the result matches RFC3339 format with microseconds and Z suffix
        # Format: YYYY-MM-DDTHH:MM:SS.ffffffZ
        rfc3339_pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$"
        assert re.match(rfc3339_pattern, result), f"Result {result} does not match RFC3339 format"

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
        assert len(microseconds_part) == 6, f"Microseconds part should have 6 digits, got {len(microseconds_part)}"

    def test_days_ago_to_rfc3339_consistency(self) -> None:
        """Test that multiple calls return consistent results (within a short time)."""
        result1 = days_ago_to_rfc3339(30)
        result2 = days_ago_to_rfc3339(30)
        
        # Parse both results
        dt1 = datetime.fromisoformat(result1.replace("Z", "+00:00"))
        dt2 = datetime.fromisoformat(result2.replace("Z", "+00:00"))
        
        # Should be within a few seconds of each other
        time_diff = abs((dt1 - dt2).total_seconds())
        assert time_diff < 2, f"Results should be consistent within 2 seconds, got {time_diff}"

    def test_days_ago_to_rfc3339_positive_days(self) -> None:
        """Test that the function works with various positive day values."""
        test_cases = [1, 7, 14, 30, 60, 90]
        
        for days in test_cases:
            result = days_ago_to_rfc3339(days)
            
            # Verify format
            rfc3339_pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$"
            assert re.match(rfc3339_pattern, result), f"Result for {days} days does not match RFC3339 format"
            
            # Verify date is in the past
            result_dt = datetime.fromisoformat(result.replace("Z", "+00:00"))
            assert result_dt < datetime.now(timezone.utc), f"Result for {days} days should be in the past"

    def test_days_ago_to_rfc3339_large_days(self) -> None:
        """Test that the function handles large day values."""
        result = days_ago_to_rfc3339(365)
        
        # Parse the result
        result_dt = datetime.fromisoformat(result.replace("Z", "+00:00"))
        expected_dt = datetime.now(timezone.utc) - timedelta(days=365)
        
        # Should be within a few seconds of expected time
        time_diff = abs((expected_dt - result_dt).total_seconds())
        assert time_diff < 5, f"Time difference {time_diff} seconds is too large"
