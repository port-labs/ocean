import pytest
from unittest.mock import patch, MagicMock

from checkmarx_one.auths.auth_factory import CheckmarxAuthenticatorFactory
from checkmarx_one.exceptions import CheckmarxAuthenticationError


class TestCheckmarxAuthenticatorFactory:
    """Test cases for CheckmarxAuthenticatorFactory class."""

    def test_create_authenticator_with_api_key(self) -> None:
        """Test creating authenticator with API key."""
        with patch("port_ocean.utils.http_async_client", MagicMock()):
            with patch(
                "checkmarx_one.auths.auth_factory.TokenAuthenticator"
            ) as mock_token_class:
                mock_authenticator = MagicMock()
                mock_token_class.return_value = mock_authenticator

                result = CheckmarxAuthenticatorFactory.create_authenticator(
                    iam_url="https://iam.checkmarx.net",
                    tenant="test-tenant",
                    api_key="test-api-key",
                )

                assert result == mock_authenticator
                mock_token_class.assert_called_once_with(
                    "https://iam.checkmarx.net", "test-tenant", "test-api-key"
                )

    def test_create_authenticator_with_no_credentials(self) -> None:
        """Test creating authenticator with no credentials raises error."""
        with pytest.raises(CheckmarxAuthenticationError) as exc_info:
            CheckmarxAuthenticatorFactory.create_authenticator(
                iam_url="https://iam.checkmarx.net", tenant="test-tenant"
            )

        assert "No valid API key provided" in str(exc_info.value)

    def test_create_authenticator_with_only_client_id(self) -> None:
        """Test creating authenticator with only client_id raises error."""
        with pytest.raises(CheckmarxAuthenticationError) as exc_info:
            CheckmarxAuthenticatorFactory.create_authenticator(
                iam_url="https://iam.checkmarx.net",
                tenant="test-tenant",
            )

        assert "No valid API key provided" in str(exc_info.value)

    def test_create_authenticator_with_empty_strings(self) -> None:
        """Test creating authenticator with empty string credentials raises error."""
        with pytest.raises(CheckmarxAuthenticationError) as exc_info:
            CheckmarxAuthenticatorFactory.create_authenticator(
                iam_url="https://iam.checkmarx.net",
                tenant="test-tenant",
                api_key="",
            )

        assert "No valid API key provided" in str(exc_info.value)

    def test_create_authenticator_with_none_values(self) -> None:
        """Test creating authenticator with None values raises error."""
        with pytest.raises(CheckmarxAuthenticationError) as exc_info:
            CheckmarxAuthenticatorFactory.create_authenticator(
                iam_url="https://iam.checkmarx.net",
                tenant="test-tenant",
                api_key=None,
            )

        assert "No valid API key provided" in str(exc_info.value)

    def test_create_authenticator_with_whitespace_only_credentials(self) -> None:
        """Test creating authenticator with whitespace-only credentials."""
        with patch("port_ocean.utils.http_async_client", MagicMock()):
            with patch(
                "checkmarx_one.auths.auth_factory.TokenAuthenticator"
            ) as mock_token_class:
                mock_authenticator = MagicMock()
                mock_token_class.return_value = mock_authenticator

                # Whitespace-only strings are considered valid by bool()
                result = CheckmarxAuthenticatorFactory.create_authenticator(
                    iam_url="https://iam.checkmarx.net",
                    tenant="test-tenant",
                    api_key="   ",
                )

                assert result == mock_authenticator
                mock_token_class.assert_called_once_with(
                    "https://iam.checkmarx.net", "test-tenant", "   "
                )

    def test_create_authenticator_with_different_urls(self) -> None:
        """Test creating authenticator with different IAM URLs."""
        with patch("port_ocean.utils.http_async_client", MagicMock()):
            with patch(
                "checkmarx_one.auths.auth_factory.TokenAuthenticator"
            ) as mock_token_class:
                mock_authenticator = MagicMock()
                mock_token_class.return_value = mock_authenticator

                result = CheckmarxAuthenticatorFactory.create_authenticator(
                    iam_url="https://custom.iam.checkmarx.net",
                    tenant="custom-tenant",
                    api_key="custom-api-key",
                )

                assert result == mock_authenticator
                mock_token_class.assert_called_once_with(
                    "https://custom.iam.checkmarx.net",
                    "custom-tenant",
                    "custom-api-key",
                )

    def test_create_authenticator_with_special_characters(self) -> None:
        """Test creating token authenticator with special characters in API key."""
        with patch("port_ocean.utils.http_async_client", MagicMock()):
            with patch(
                "checkmarx_one.auths.auth_factory.TokenAuthenticator"
            ) as mock_token_class:
                mock_authenticator = MagicMock()
                mock_token_class.return_value = mock_authenticator

                result = CheckmarxAuthenticatorFactory.create_authenticator(
                    iam_url="https://iam.checkmarx.net",
                    tenant="test-tenant",
                    api_key="secret@123!",
                )

                assert result == mock_authenticator
                mock_token_class.assert_called_once_with(
                    "https://iam.checkmarx.net",
                    "test-tenant",
                    "secret@123!",
                )

    def test_create_authenticator_raises_error_when_no_api_key(self) -> None:
        """Test that an error is raised when no API key is provided (only token auth supported)."""
        with patch("port_ocean.utils.http_async_client", MagicMock()):
            with pytest.raises(CheckmarxAuthenticationError) as exc_info:
                CheckmarxAuthenticatorFactory.create_authenticator(
                    iam_url="https://iam.checkmarx.net",
                    tenant="test-tenant",
                )
            assert "No valid API key provided" in str(exc_info.value)
