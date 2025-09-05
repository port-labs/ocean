import pytest
from enum import StrEnum

from checkmarx_one.utils import ObjectKind


class TestObjectKind:
    def test_object_kind_is_str_enum(self) -> None:
        """Test that ObjectKind inherits from StrEnum."""
        assert issubclass(ObjectKind, StrEnum)
        assert isinstance(ObjectKind.PROJECT, str)
        assert isinstance(ObjectKind.SCAN, str)

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
        }
        actual_members = set(ObjectKind.__members__.keys())
        assert actual_members == expected_members

    def test_enum_values(self) -> None:
        """Test that enum has expected values."""
        expected_values = {
            "project",
            "scan",
            "api-security",
        }
        actual_values = set(member.value for member in ObjectKind)
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
        assert len(members) == 3
        assert ObjectKind.PROJECT in members
        assert ObjectKind.SCAN in members
        assert ObjectKind.API_SEC in members

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
