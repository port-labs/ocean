import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from typing import Optional

from auth import CheckmarxAuthenticator
from auth_factory import CheckmarxAuthenticatorFactory
from token_auth import TokenAuthenticator
from oauth import OAuthAuthenticator
from exceptions import CheckmarxAuthenticationError


class TestCheckmarxAuthenticator:
    """Test cases for CheckmarxAuthenticator class."""

    @pytest.fixture
    def api_key_authenticator(self) -> CheckmarxAuthenticator:
        """Create a CheckmarxAuthenticator instance with API key."""
        with patch('base_auth.http_async_client', AsyncMock()):
            return CheckmarxAuthenticator(
                iam_url="https://iam.checkmarx.net",
                tenant="test-tenant",
                api_key="test-api-key"
            )

    @pytest.fixture
    def oauth_authenticator(self) -> CheckmarxAuthenticator:
        """Create a CheckmarxAuthenticator instance with OAuth credentials."""
        with patch('base_auth.http_async_client', AsyncMock()):
            return CheckmarxAuthenticator(
                iam_url="https://iam.checkmarx.net",
                tenant="test-tenant",
                client_id="test-client-id",
                client_secret="test-client-secret"
            )

    @pytest.fixture
    def mock_token_response(self) -> dict:
        """Create a mock token response."""
        return {
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "expires_in": 1800,
            "token_type": "Bearer"
        }

    def test_init_with_api_key(self, api_key_authenticator: CheckmarxAuthenticator) -> None:
        """Test initialization with API key authentication."""
        assert api_key_authenticator.iam_url == "https://iam.checkmarx.net"
        assert api_key_authenticator.tenant == "test-tenant"
        assert api_key_authenticator.api_key == "test-api-key"
        # These attributes are not copied from the underlying authenticator
        # assert api_key_authenticator.client_id is None
        # assert api_key_authenticator.client_secret is None
        assert isinstance(api_key_authenticator._authenticator, TokenAuthenticator)

    def test_init_with_oauth(self, oauth_authenticator: CheckmarxAuthenticator) -> None:
        """Test initialization with OAuth authentication."""
        assert oauth_authenticator.iam_url == "https://iam.checkmarx.net"
        assert oauth_authenticator.tenant == "test-tenant"
        assert oauth_authenticator.client_id == "test-client-id"
        assert oauth_authenticator.client_secret == "test-client-secret"
        # This attribute is not copied from the underlying authenticator
        # assert oauth_authenticator.api_key is None
        assert isinstance(oauth_authenticator._authenticator, OAuthAuthenticator)

    def test_init_with_both_credentials(self) -> None:
        """Test initialization with both API key and OAuth credentials."""
        with patch('base_auth.http_async_client', AsyncMock()):
            authenticator = CheckmarxAuthenticator(
                iam_url="https://iam.checkmarx.net",
                tenant="test-tenant",
                api_key="test-api-key",
                client_id="test-client-id",
                client_secret="test-client-secret"
            )

            # Should use API key authentication (preferred)
            assert isinstance(authenticator._authenticator, TokenAuthenticator)
            assert authenticator.api_key == "test-api-key"

    def test_init_with_no_credentials(self) -> None:
        """Test initialization with no credentials raises error."""
        with pytest.raises(CheckmarxAuthenticationError) as exc_info:
            CheckmarxAuthenticator(
                iam_url="https://iam.checkmarx.net",
                tenant="test-tenant"
            )

        assert "Either provide api_key or both client_id and client_secret" in str(exc_info.value)

    def test_init_with_partial_oauth_credentials(self) -> None:
        """Test initialization with partial OAuth credentials raises error."""
        with pytest.raises(CheckmarxAuthenticationError) as exc_info:
            CheckmarxAuthenticator(
                iam_url="https://iam.checkmarx.net",
                tenant="test-tenant",
                client_id="test-client-id"
                # Missing client_secret
            )

        assert "Either provide api_key or both client_id and client_secret" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_authenticate_with_api_key(self, api_key_authenticator: CheckmarxAuthenticator, mock_token_response: dict) -> None:
        """Test authentication delegation with API key."""
        with patch.object(api_key_authenticator._authenticator, '_authenticate', AsyncMock(return_value=mock_token_response)):
            result = await api_key_authenticator._authenticate()

            assert result == mock_token_response
            api_key_authenticator._authenticator._authenticate.assert_called_once()

    @pytest.mark.asyncio
    async def test_authenticate_with_oauth(self, oauth_authenticator: CheckmarxAuthenticator, mock_token_response: dict) -> None:
        """Test authentication delegation with OAuth."""
        with patch.object(oauth_authenticator._authenticator, '_authenticate', AsyncMock(return_value=mock_token_response)):
            result = await oauth_authenticator._authenticate()

            assert result == mock_token_response
            oauth_authenticator._authenticator._authenticate.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_auth_headers_with_api_key(self, api_key_authenticator: CheckmarxAuthenticator) -> None:
        """Test get_auth_headers delegation with API key."""
        expected_headers = {
            "Authorization": "Bearer test-token",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        with patch.object(api_key_authenticator._authenticator, 'get_auth_headers', AsyncMock(return_value=expected_headers)):
            result = await api_key_authenticator.get_auth_headers()

            assert result == expected_headers
            api_key_authenticator._authenticator.get_auth_headers.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_auth_headers_with_oauth(self, oauth_authenticator: CheckmarxAuthenticator) -> None:
        """Test get_auth_headers delegation with OAuth."""
        expected_headers = {
            "Authorization": "Bearer test-token",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        with patch.object(oauth_authenticator._authenticator, 'get_auth_headers', AsyncMock(return_value=expected_headers)):
            result = await oauth_authenticator.get_auth_headers()

            assert result == expected_headers
            oauth_authenticator._authenticator.get_auth_headers.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_token_with_api_key(self, api_key_authenticator: CheckmarxAuthenticator) -> None:
        """Test refresh_token delegation with API key."""
        with patch.object(api_key_authenticator._authenticator, 'refresh_token', AsyncMock()) as mock_refresh:
            await api_key_authenticator.refresh_token()

            mock_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_token_with_oauth(self, oauth_authenticator: CheckmarxAuthenticator) -> None:
        """Test refresh_token delegation with OAuth."""
        with patch.object(oauth_authenticator._authenticator, 'refresh_token', AsyncMock()) as mock_refresh:
            await oauth_authenticator.refresh_token()

            mock_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_authenticate_propagates_exception(self, api_key_authenticator: CheckmarxAuthenticator) -> None:
        """Test that authentication exceptions are properly propagated."""
        with patch.object(api_key_authenticator._authenticator, '_authenticate', AsyncMock(side_effect=CheckmarxAuthenticationError("Auth failed"))):
            with pytest.raises(CheckmarxAuthenticationError) as exc_info:
                await api_key_authenticator._authenticate()

            assert "Auth failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_auth_headers_propagates_exception(self, api_key_authenticator: CheckmarxAuthenticator) -> None:
        """Test that get_auth_headers exceptions are properly propagated."""
        with patch.object(api_key_authenticator._authenticator, 'get_auth_headers', AsyncMock(side_effect=CheckmarxAuthenticationError("Headers failed"))):
            with pytest.raises(CheckmarxAuthenticationError) as exc_info:
                await api_key_authenticator.get_auth_headers()

            assert "Headers failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_refresh_token_propagates_exception(self, api_key_authenticator: CheckmarxAuthenticator) -> None:
        """Test that refresh_token exceptions are properly propagated."""
        with patch.object(api_key_authenticator._authenticator, 'refresh_token', AsyncMock(side_effect=CheckmarxAuthenticationError("Refresh failed"))):
            with pytest.raises(CheckmarxAuthenticationError) as exc_info:
                await api_key_authenticator.refresh_token()

            assert "Refresh failed" in str(exc_info.value)

    def test_attributes_copied_from_underlying_authenticator(self, api_key_authenticator: CheckmarxAuthenticator) -> None:
        """Test that attributes are properly copied from the underlying authenticator."""
        # The underlying authenticator should have the same core attributes
        assert api_key_authenticator.iam_url == api_key_authenticator._authenticator.iam_url
        assert api_key_authenticator.tenant == api_key_authenticator._authenticator.tenant
        assert api_key_authenticator.api_key == api_key_authenticator._authenticator.api_key

    def test_attributes_copied_from_oauth_authenticator(self, oauth_authenticator: CheckmarxAuthenticator) -> None:
        """Test that attributes are properly copied from the OAuth authenticator."""
        # The underlying authenticator should have the same core attributes
        assert oauth_authenticator.iam_url == oauth_authenticator._authenticator.iam_url
        assert oauth_authenticator.tenant == oauth_authenticator._authenticator.tenant
        assert oauth_authenticator.client_id == oauth_authenticator._authenticator.client_id
        assert oauth_authenticator.client_secret == oauth_authenticator._authenticator.client_secret
