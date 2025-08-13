from typing import Any, cast
import pytest
from unittest.mock import AsyncMock, patch

from checkmarx_one.auths.token_auth import TokenAuthenticator
from checkmarx_one.auths.oauth import OAuthAuthenticator
from checkmarx_one.auths.auth_factory import CheckmarxAuthenticatorFactory
from checkmarx_one.exceptions import CheckmarxAuthenticationError


class TestCheckmarxAuthenticator:
    """Test cases for CheckmarxAuthenticator class."""

    @pytest.fixture
    def api_key_authenticator(self) -> TokenAuthenticator:
        """Create a TokenAuthenticator instance with API key."""
        with patch("port_ocean.utils.http_async_client", AsyncMock()):
            return TokenAuthenticator(
                iam_url="https://iam.checkmarx.net",
                tenant="test-tenant",
                api_key="test-api-key",
            )

    @pytest.fixture
    def oauth_authenticator(self) -> OAuthAuthenticator:
        """Create an OAuthAuthenticator instance with OAuth credentials."""
        with patch("port_ocean.utils.http_async_client", AsyncMock()):
            return OAuthAuthenticator(
                iam_url="https://iam.checkmarx.net",
                tenant="test-tenant",
                client_id="test-client-id",
                client_secret="test-client-secret",
            )

    @pytest.fixture
    def mock_token_response(self) -> dict[str, Any]:
        """Create a mock token response."""
        return {
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "expires_in": 1800,
        }

    def test_init_with_api_key(self, api_key_authenticator: TokenAuthenticator) -> None:
        """Test initialization with API key authentication."""
        assert api_key_authenticator.iam_url == "https://iam.checkmarx.net"
        assert api_key_authenticator.tenant == "test-tenant"
        assert api_key_authenticator.api_key == "test-api-key"

    def test_init_with_oauth(self, oauth_authenticator: OAuthAuthenticator) -> None:
        """Test initialization with OAuth authentication."""
        assert oauth_authenticator.iam_url == "https://iam.checkmarx.net"
        assert oauth_authenticator.tenant == "test-tenant"
        assert oauth_authenticator.client_id == "test-client-id"
        assert oauth_authenticator.client_secret == "test-client-secret"

    def test_init_with_both_credentials(self) -> None:
        """Test initialization with both API key and OAuth credentials."""
        with patch("port_ocean.utils.http_async_client", AsyncMock()):
            authenticator = CheckmarxAuthenticatorFactory.create_authenticator(
                iam_url="https://iam.checkmarx.net",
                tenant="test-tenant",
                api_key="test-api-key",
                client_id="test-client-id",
                client_secret="test-client-secret",
            )

            # Should use API key authentication (preferred)
            assert isinstance(authenticator, TokenAuthenticator)
            assert authenticator.api_key == "test-api-key"

    def test_init_with_no_credentials(self) -> None:
        """Test initialization with no credentials raises error."""
        with pytest.raises(CheckmarxAuthenticationError) as exc_info:
            CheckmarxAuthenticatorFactory.create_authenticator(
                iam_url="https://iam.checkmarx.net", tenant="test-tenant"
            )

        assert "No valid authentication method provided" in str(exc_info.value)

    def test_init_with_partial_oauth_credentials(self) -> None:
        """Test initialization with partial OAuth credentials raises error."""
        with pytest.raises(CheckmarxAuthenticationError) as exc_info:
            CheckmarxAuthenticatorFactory.create_authenticator(
                iam_url="https://iam.checkmarx.net",
                tenant="test-tenant",
                client_id="test-client-id",
                # Missing client_secret
            )

        assert "No valid authentication method provided" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_authenticate_with_api_key(
        self,
        api_key_authenticator: TokenAuthenticator,
        mock_token_response: dict[str, Any],
    ) -> None:
        """Test authentication delegation with API key."""
        with patch.object(
            api_key_authenticator,
            "_authenticate",
            AsyncMock(return_value=mock_token_response),
        ):
            result = await api_key_authenticator._authenticate()

            assert result == mock_token_response
            mocked_auth = cast(Any, api_key_authenticator._authenticate)
            mocked_auth.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_authenticate_with_oauth(
        self,
        oauth_authenticator: OAuthAuthenticator,
        mock_token_response: dict[str, Any],
    ) -> None:
        """Test authentication delegation with OAuth."""
        with patch.object(
            oauth_authenticator,
            "_authenticate",
            AsyncMock(return_value=mock_token_response),
        ):
            result = await oauth_authenticator._authenticate()

            assert result == mock_token_response
            mocked_auth = cast(Any, oauth_authenticator._authenticate)
            mocked_auth.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_auth_headers_with_api_key(
        self, api_key_authenticator: TokenAuthenticator
    ) -> None:
        """Test get_auth_headers delegation with API key."""
        expected_headers = {
            "Authorization": "Bearer test-token",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        with patch.object(
            api_key_authenticator,
            "get_auth_headers",
            AsyncMock(return_value=expected_headers),
        ):
            result = await api_key_authenticator.get_auth_headers()

            assert result == expected_headers
            mocked_headers = cast(Any, api_key_authenticator.get_auth_headers)
            mocked_headers.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_auth_headers_with_oauth(
        self, oauth_authenticator: OAuthAuthenticator
    ) -> None:
        """Test get_auth_headers delegation with OAuth."""
        expected_headers = {
            "Authorization": "Bearer test-token",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        with patch.object(
            oauth_authenticator,
            "get_auth_headers",
            AsyncMock(return_value=expected_headers),
        ):
            result = await oauth_authenticator.get_auth_headers()

            assert result == expected_headers
            mocked_headers = cast(Any, oauth_authenticator.get_auth_headers)
            mocked_headers.assert_called_once()

    @pytest.mark.asyncio
    async def test_authenticate_propagates_exception(
        self, api_key_authenticator: TokenAuthenticator
    ) -> None:
        """Test that authentication exceptions are properly propagated."""
        with patch.object(
            api_key_authenticator,
            "_authenticate",
            AsyncMock(side_effect=CheckmarxAuthenticationError("Auth failed")),
        ):
            with pytest.raises(CheckmarxAuthenticationError) as exc_info:
                await api_key_authenticator._authenticate()

            assert "Auth failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_auth_headers_propagates_exception(
        self, api_key_authenticator: TokenAuthenticator
    ) -> None:
        """Test that get_auth_headers exceptions are properly propagated."""
        with patch.object(
            api_key_authenticator,
            "get_auth_headers",
            AsyncMock(side_effect=CheckmarxAuthenticationError("Headers failed")),
        ):
            with pytest.raises(CheckmarxAuthenticationError) as exc_info:
                await api_key_authenticator.get_auth_headers()

            assert "Headers failed" in str(exc_info.value)

    def test_attributes_copied_from_underlying_authenticator(
        self, api_key_authenticator: TokenAuthenticator
    ) -> None:
        """Test that attributes are properly copied from the underlying authenticator."""
        # The underlying authenticator should have the same core attributes
        assert api_key_authenticator.iam_url == "https://iam.checkmarx.net"
        assert api_key_authenticator.tenant == "test-tenant"
        assert api_key_authenticator.api_key == "test-api-key"

    def test_attributes_copied_from_oauth_authenticator(
        self, oauth_authenticator: OAuthAuthenticator
    ) -> None:
        """Test that attributes are properly copied from the OAuth authenticator."""
        # The underlying authenticator should have the same core attributes
        assert oauth_authenticator.iam_url == "https://iam.checkmarx.net"
        assert oauth_authenticator.tenant == "test-tenant"
        assert oauth_authenticator.client_id == "test-client-id"
        assert oauth_authenticator.client_secret == "test-client-secret"
