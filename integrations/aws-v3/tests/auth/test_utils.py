import pytest
from unittest.mock import MagicMock
from aws.auth.utils import (
    AWSSessionError,
    CredentialsProviderError,
    normalize_arn_list,
    extract_account_from_arn,
)


class TestAWSSessionError:
    """Test AWSSessionError exception."""

    def test_awssession_error_creation(self) -> None:
        """Test AWSSessionError can be created with a message."""
        error = AWSSessionError("Test error message")
        assert str(error) == "Test error message"


class TestCredentialsProviderError:
    """Test CredentialsProviderError exception."""

    def test_credentials_provider_error_creation(self) -> None:
        """Test CredentialsProviderError can be created with a message."""
        error = CredentialsProviderError("Test credentials error")
        assert str(error) == "Test credentials error"


class TestNormalizeArnList:
    """Test normalize_arn_list function."""

    def test_normalize_arn_list_with_string(self) -> None:
        """Test normalize_arn_list with a single string ARN."""
        arn_input = "arn:aws:iam::123456789012:role/test-role"
        result = normalize_arn_list(arn_input)
        assert result == ["arn:aws:iam::123456789012:role/test-role"]

    def test_normalize_arn_list_with_list(self) -> None:
        """Test normalize_arn_list with a list of ARNs."""
        arn_input = [
            "arn:aws:iam::123456789012:role/test-role-1",
            "arn:aws:iam::987654321098:role/test-role-2",
        ]
        result = normalize_arn_list(arn_input)
        assert result == [
            "arn:aws:iam::123456789012:role/test-role-1",
            "arn:aws:iam::987654321098:role/test-role-2",
        ]

    def test_normalize_arn_list_with_whitespace(self) -> None:
        """Test normalize_arn_list handles whitespace correctly."""
        arn_input = [
            "  arn:aws:iam::123456789012:role/test-role-1  ",
            "arn:aws:iam::987654321098:role/test-role-2",
        ]
        result = normalize_arn_list(arn_input)
        assert result == [
            "arn:aws:iam::123456789012:role/test-role-1",
            "arn:aws:iam::987654321098:role/test-role-2",
        ]

    def test_normalize_arn_list_with_none(self) -> None:
        """Test normalize_arn_list with None input."""
        result = normalize_arn_list(None)
        assert result == []

    def test_normalize_arn_list_with_empty_list(self) -> None:
        """Test normalize_arn_list with empty list."""
        result = normalize_arn_list([])
        assert result == []

    def test_normalize_arn_list_with_empty_string(self) -> None:
        """Test normalize_arn_list with empty string."""
        result = normalize_arn_list("")
        assert result == []

    def test_normalize_arn_list_with_mixed_types(self) -> None:
        """Test normalize_arn_list with mixed types in list."""
        arn_input = [
            "arn:aws:iam::123456789012:role/test-role-1",
            None,
            "",
            "  ",
            123,  # Non-string type
            "arn:aws:iam::987654321098:role/test-role-2",
        ]
        result = normalize_arn_list(arn_input)  # type: ignore[arg-type]
        assert result == [
            "arn:aws:iam::123456789012:role/test-role-1",
            "arn:aws:iam::987654321098:role/test-role-2",
        ]


class TestExtractAccountFromArn:
    """Test extract_account_from_arn function."""

    def test_extract_account_from_valid_arn(self, mock_arn_parser: MagicMock) -> None:
        """Test extract_account_from_arn with valid ARN."""
        result = extract_account_from_arn(
            "arn:aws:iam::123456789012:role/test-role", arn_parser=mock_arn_parser
        )
        assert result == "123456789012"
        mock_arn_parser.parse_arn.assert_called_once_with(
            "arn:aws:iam::123456789012:role/test-role"
        )

    def test_extract_account_from_arn_with_custom_parser(
        self, mock_arn_parser: MagicMock
    ) -> None:
        """Test extract_account_from_arn with custom parser."""
        result = extract_account_from_arn(
            "arn:aws:iam::123456789012:role/test-role", arn_parser=mock_arn_parser
        )
        assert result == "123456789012"
        mock_arn_parser.parse_arn.assert_called_once_with(
            "arn:aws:iam::123456789012:role/test-role"
        )

    def test_extract_account_from_arn_parser_error(self) -> None:
        """Test extract_account_from_arn when parser raises an error."""
        mock_parser = MagicMock()
        mock_parser.parse_arn.side_effect = ValueError("Invalid ARN")

        with pytest.raises(ValueError, match="Invalid ARN"):
            extract_account_from_arn("invalid-arn", arn_parser=mock_parser)

    def test_extract_account_from_arn_different_services(
        self, mock_arn_parser: MagicMock
    ) -> None:
        """Test extract_account_from_arn with different AWS services."""
        test_cases = [
            "arn:aws:s3:::my-bucket",
            "arn:aws:lambda:us-west-2:123456789012:function:my-function",
            "arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0",
        ]

        for arn in test_cases:
            result = extract_account_from_arn(arn, arn_parser=mock_arn_parser)
            assert result == "123456789012"
            mock_arn_parser.parse_arn.assert_called_with(arn)
