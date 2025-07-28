import pytest
from typing import Any
from aws.auth.utils import (
    normalize_arn_list,
)
from tests.conftest import AWS_TEST_ROLE_ARN_2


class TestNormalizeArnList:
    """Test normalize_arn_list function."""

    def test_single_string_arn(self, role_arn: str) -> None:
        """Test normalize_arn_list with a single string ARN."""
        # Arrange
        arn_input = role_arn

        # Act
        result = normalize_arn_list(arn_input)

        # Assert
        assert result == [role_arn]

    def test_list_of_arns(self, role_arn: str) -> None:
        """Test normalize_arn_list with a list of ARNs."""
        # Arrange
        arn_input = [
            role_arn,
            AWS_TEST_ROLE_ARN_2,
        ]

        # Act
        result = normalize_arn_list(arn_input)

        # Assert
        assert result == [
            role_arn,
            AWS_TEST_ROLE_ARN_2,
        ]

    def test_handles_whitespace(self, role_arn: str) -> None:
        """Test normalize_arn_list strips whitespace."""
        # Arrange
        arn_input = [
            f"  {role_arn}  ",
            AWS_TEST_ROLE_ARN_2,
        ]

        # Act
        result = normalize_arn_list(arn_input)

        # Assert
        assert result == [
            role_arn,
            AWS_TEST_ROLE_ARN_2,
        ]

    @pytest.mark.parametrize("empty_input", [None, [], ""])
    def test_handles_empty_inputs(self, empty_input: Any) -> None:
        """Test normalize_arn_list handles empty inputs."""
        # Act
        result = normalize_arn_list(empty_input)

        # Assert
        assert result == []

    def test_filters_invalid_entries(self, role_arn: str) -> None:
        """Test normalize_arn_list filters out invalid entries."""
        # Arrange
        arn_input = [
            role_arn,
            None,
            "",
            "  ",
            123,
            AWS_TEST_ROLE_ARN_2,
        ]

        # Act
        result = normalize_arn_list(arn_input)  # type: ignore[arg-type]

        # Assert
        assert result == [
            role_arn,
            AWS_TEST_ROLE_ARN_2,
        ]
