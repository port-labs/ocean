import pytest
from typing import Any
from aws.auth.utils import (
    AWSSessionError,
    CredentialsProviderError,
    normalize_arn_list,
)


class TestAWSSessionError:
    """Test AWSSessionError exception."""

    def test_creation_with_message(self) -> None:
        """Test AWSSessionError can be created with a message."""
        error = AWSSessionError("Test error message")
        assert str(error) == "Test error message"

    def test_inheritance(self) -> None:
        """Test AWSSessionError inherits from Exception."""
        error = AWSSessionError("Test error")
        assert isinstance(error, Exception)


class TestCredentialsProviderError:
    """Test CredentialsProviderError exception."""

    def test_creation_with_message(self) -> None:
        """Test CredentialsProviderError can be created with a message."""
        error = CredentialsProviderError("Test credentials error")
        assert str(error) == "Test credentials error"

    def test_inheritance(self) -> None:
        """Test CredentialsProviderError inherits from Exception."""
        error = CredentialsProviderError("Test error")
        assert isinstance(error, Exception)


class TestNormalizeArnList:
    """Test normalize_arn_list function."""

    def test_single_string_arn(self, role_arn: str) -> None:
        """Test normalize_arn_list with a single string ARN."""
        arn_input = role_arn
        result = normalize_arn_list(arn_input)
        assert result == [role_arn]

    def test_list_of_arns(self, role_arn: str) -> None:
        """Test normalize_arn_list with a list of ARNs."""
        arn_input = [
            role_arn,
            "arn:aws:iam::987654321098:role/test-role-2",
        ]
        result = normalize_arn_list(arn_input)
        assert result == [
            role_arn,
            "arn:aws:iam::987654321098:role/test-role-2",
        ]

    def test_handles_whitespace(self, role_arn: str) -> None:
        """Test normalize_arn_list strips whitespace."""
        arn_input = [
            f"  {role_arn}  ",
            "arn:aws:iam::987654321098:role/test-role-2",
        ]
        result = normalize_arn_list(arn_input)
        assert result == [
            role_arn,
            "arn:aws:iam::987654321098:role/test-role-2",
        ]

    @pytest.mark.parametrize("empty_input", [None, [], ""])
    def test_handles_empty_inputs(self, empty_input: Any) -> None:
        """Test normalize_arn_list handles empty inputs."""
        result = normalize_arn_list(empty_input)
        assert result == []

    def test_filters_invalid_entries(self, role_arn: str) -> None:
        """Test normalize_arn_list filters out invalid entries."""
        arn_input = [
            role_arn,
            None,
            "",
            "  ",
            123,  # Non-string type
            "arn:aws:iam::987654321098:role/test-role-2",
        ]
        result = normalize_arn_list(arn_input)  # type: ignore[arg-type]
        assert result == [
            role_arn,
            "arn:aws:iam::987654321098:role/test-role-2",
        ]
