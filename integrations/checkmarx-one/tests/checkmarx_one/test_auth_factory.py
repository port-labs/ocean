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

    def test_create_authenticator_with_oauth(self) -> None:
        """Test creating authenticator with OAuth credentials."""
        with patch("port_ocean.utils.http_async_client", MagicMock()):
            with patch(
                "checkmarx_one.auths.auth_factory.OAuthAuthenticator"
            ) as mock_oauth_class:
                mock_authenticator = MagicMock()
                mock_oauth_class.return_value = mock_authenticator

                result = CheckmarxAuthenticatorFactory.create_authenticator(
                    iam_url="https://iam.checkmarx.net",
                    tenant="test-tenant",
                    client_id="test-client-id",
                    client_secret="test-client-secret",
                )

                assert result == mock_authenticator
                mock_oauth_class.assert_called_once_with(
                    "https://iam.checkmarx.net",
                    "test-tenant",
                    "test-client-id",
                    "test-client-secret",
                )

    def test_create_authenticator_with_both_credentials(self) -> None:
        """Test creating authenticator with both API key and OAuth credentials."""
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
                    client_id="test-client-id",
                    client_secret="test-client-secret",
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

        assert "No valid authentication method provided" in str(exc_info.value)

    def test_create_authenticator_with_partial_oauth_credentials(self) -> None:
        """Test creating authenticator with partial OAuth credentials raises error."""
        with pytest.raises(CheckmarxAuthenticationError) as exc_info:
            CheckmarxAuthenticatorFactory.create_authenticator(
                iam_url="https://iam.checkmarx.net",
                tenant="test-tenant",
                client_id="test-client-id",
                # Missing client_secret
            )

        assert "No valid authentication method provided" in str(exc_info.value)

    def test_create_authenticator_with_only_client_id(self) -> None:
        """Test creating authenticator with only client_id raises error."""
        with pytest.raises(CheckmarxAuthenticationError) as exc_info:
            CheckmarxAuthenticatorFactory.create_authenticator(
                iam_url="https://iam.checkmarx.net",
                tenant="test-tenant",
                client_id="test-client-id",
            )

        assert "No valid authentication method provided" in str(exc_info.value)

    def test_create_authenticator_with_only_client_secret(self) -> None:
        """Test creating authenticator with only client_secret raises error."""
        with pytest.raises(CheckmarxAuthenticationError) as exc_info:
            CheckmarxAuthenticatorFactory.create_authenticator(
                iam_url="https://iam.checkmarx.net",
                tenant="test-tenant",
                client_secret="test-client-secret",
            )

        assert "No valid authentication method provided" in str(exc_info.value)

    def test_create_authenticator_with_empty_strings(self) -> None:
        """Test creating authenticator with empty string credentials raises error."""
        with pytest.raises(CheckmarxAuthenticationError) as exc_info:
            CheckmarxAuthenticatorFactory.create_authenticator(
                iam_url="https://iam.checkmarx.net",
                tenant="test-tenant",
                api_key="",
                client_id="",
                client_secret="",
            )

        assert "No valid authentication method provided" in str(exc_info.value)

    def test_create_authenticator_with_none_values(self) -> None:
        """Test creating authenticator with None values raises error."""
        with pytest.raises(CheckmarxAuthenticationError) as exc_info:
            CheckmarxAuthenticatorFactory.create_authenticator(
                iam_url="https://iam.checkmarx.net",
                tenant="test-tenant",
                api_key=None,
                client_id=None,
                client_secret=None,
            )

        assert "No valid authentication method provided" in str(exc_info.value)

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
                    client_id="   ",
                    client_secret="   ",
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
        """Test creating authenticator with special characters in credentials."""
        with patch("port_ocean.utils.http_async_client", MagicMock()):
            with patch(
                "checkmarx_one.auths.auth_factory.OAuthAuthenticator"
            ) as mock_oauth_class:
                mock_authenticator = MagicMock()
                mock_oauth_class.return_value = mock_authenticator

                result = CheckmarxAuthenticatorFactory.create_authenticator(
                    iam_url="https://iam.checkmarx.net",
                    tenant="test-tenant",
                    client_id="client@id",
                    client_secret="secret@123!",
                )

                assert result == mock_authenticator
                mock_oauth_class.assert_called_once_with(
                    "https://iam.checkmarx.net",
                    "test-tenant",
                    "client@id",
                    "secret@123!",
                )

    def test_create_authenticator_prefers_api_key_over_oauth(self) -> None:
        """Test that API key is preferred over OAuth when both are provided."""
        with patch("port_ocean.utils.http_async_client", MagicMock()):
            with patch(
                "checkmarx_one.auths.auth_factory.TokenAuthenticator"
            ) as mock_token_class:
                mock_authenticator = MagicMock()
                mock_token_class.return_value = mock_authenticator

                with patch(
                    "checkmarx_one.auths.auth_factory.OAuthAuthenticator"
                ) as mock_oauth_class:
                    result = CheckmarxAuthenticatorFactory.create_authenticator(
                        iam_url="https://iam.checkmarx.net",
                        tenant="test-tenant",
                        api_key="test-api-key",
                        client_id="test-client-id",
                        client_secret="test-client-secret",
                    )

                    assert result == mock_authenticator
                    mock_token_class.assert_called_once()
                    mock_oauth_class.assert_not_called()

    def test_create_authenticator_oauth_when_no_api_key(self) -> None:
        """Test that OAuth is used when no API key is provided."""
        with patch("port_ocean.utils.http_async_client", MagicMock()):
            with patch(
                "checkmarx_one.auths.auth_factory.OAuthAuthenticator"
            ) as mock_oauth_class:
                mock_authenticator = MagicMock()
                mock_oauth_class.return_value = mock_authenticator

                with patch(
                    "checkmarx_one.auths.auth_factory.TokenAuthenticator"
                ) as mock_token_class:
                    result = CheckmarxAuthenticatorFactory.create_authenticator(
                        iam_url="https://iam.checkmarx.net",
                        tenant="test-tenant",
                        client_id="test-client-id",
                        client_secret="test-client-secret",
                    )

                    assert result == mock_authenticator
                    mock_oauth_class.assert_called_once()
                    mock_token_class.assert_not_called()
