import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import HTTPStatusError, Response
from loguru import logger

from token_auth import TokenAuthenticator
from exceptions import CheckmarxAuthenticationError


class TestTokenAuthenticator:
    """Test cases for TokenAuthenticator class."""

    @pytest.fixture
    def token_authenticator(self) -> TokenAuthenticator:
        """Create a TokenAuthenticator instance for testing."""
        with patch('base_auth.http_async_client', AsyncMock()):
            return TokenAuthenticator(
                iam_url="https://iam.checkmarx.net",
                tenant="test-tenant",
                api_key="test-api-key"
            )

    @pytest.fixture
    def mock_http_client(self) -> AsyncMock:
        """Create a mock HTTP client."""
        return AsyncMock()

    @pytest.fixture
    def mock_response(self) -> MagicMock:
        """Create a mock response with token data."""
        mock_response = MagicMock(spec=Response)
        mock_response.json.return_value = {
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "expires_in": 1800,
            "token_type": "Bearer"
        }
        mock_response.raise_for_status.return_value = None
        return mock_response

    def test_init(self, token_authenticator: TokenAuthenticator) -> None:
        """Test TokenAuthenticator initialization."""
        assert token_authenticator.iam_url == "https://iam.checkmarx.net"
        assert token_authenticator.tenant == "test-tenant"
        assert token_authenticator.api_key == "test-api-key"
        assert token_authenticator.auth_url == "https://iam.checkmarx.net/auth/realms/test-tenant/protocol/openid-connect/token"

    @pytest.mark.asyncio
    async def test_authenticate_success(self, token_authenticator: TokenAuthenticator, mock_response: MagicMock) -> None:
        """Test successful authentication."""
        with patch.object(token_authenticator, 'http_client', AsyncMock()) as mock_client:
            mock_client.post.return_value = mock_response

            result = await token_authenticator._authenticate()

            # Verify the result
            assert result == {
                "access_token": "test-access-token",
                "refresh_token": "test-refresh-token",
                "expires_in": 1800,
                "token_type": "Bearer"
            }

            # Verify the HTTP call
            mock_client.post.assert_called_once_with(
                token_authenticator.auth_url,
                data={
                    "grant_type": "refresh_token",
                    "client_id": "ast-app",
                    "refresh_token": "test-api-key",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

    @pytest.mark.asyncio
    async def test_authenticate_http_error(self, token_authenticator: TokenAuthenticator) -> None:
        """Test authentication with HTTP error."""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.raise_for_status.side_effect = HTTPStatusError(
            "401 Unauthorized", request=MagicMock(), response=mock_response
        )

        with patch.object(token_authenticator, 'http_client', AsyncMock()) as mock_client:
            mock_client.post.return_value = mock_response

            with pytest.raises(CheckmarxAuthenticationError) as exc_info:
                await token_authenticator._authenticate()

            assert "API key authentication failed: Unauthorized" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_authenticate_network_error(self, token_authenticator: TokenAuthenticator) -> None:
        """Test authentication with network error."""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 500
        mock_response.text = "Network error"
        mock_response.raise_for_status.side_effect = HTTPStatusError(
            "500 Network error", request=MagicMock(), response=mock_response
        )

        with patch.object(token_authenticator, 'http_client', AsyncMock()) as mock_client:
            mock_client.post.return_value = mock_response

            with pytest.raises(CheckmarxAuthenticationError) as exc_info:
                await token_authenticator._authenticate()

            assert "API key authentication failed: Network error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_authenticate_invalid_response(self, token_authenticator: TokenAuthenticator) -> None:
        """Test authentication with invalid response format."""
        mock_response = MagicMock(spec=Response)
        mock_response.json.return_value = {"error": "invalid_grant"}
        mock_response.raise_for_status.return_value = None

        with patch.object(token_authenticator, 'http_client', AsyncMock()) as mock_client:
            mock_client.post.return_value = mock_response

            result = await token_authenticator._authenticate()

            # Should still return the response even if it contains an error
            assert result == {"error": "invalid_grant"}

    @pytest.mark.asyncio
    async def test_authenticate_empty_response(self, token_authenticator: TokenAuthenticator) -> None:
        """Test authentication with empty response."""
        mock_response = MagicMock(spec=Response)
        mock_response.json.return_value = {}
        mock_response.raise_for_status.return_value = None

        with patch.object(token_authenticator, 'http_client', AsyncMock()) as mock_client:
            mock_client.post.return_value = mock_response

            result = await token_authenticator._authenticate()

            assert result == {}

    @pytest.mark.asyncio
    async def test_authenticate_with_different_api_key(self) -> None:
        """Test authentication with different API key."""
        with patch('base_auth.http_async_client', AsyncMock()):
            authenticator = TokenAuthenticator(
                iam_url="https://custom.iam.checkmarx.net",
                tenant="custom-tenant",
                api_key="custom-api-key"
            )

        mock_response = MagicMock(spec=Response)
        mock_response.json.return_value = {"access_token": "custom-token"}
        mock_response.raise_for_status.return_value = None

        with patch.object(authenticator, 'http_client', AsyncMock()) as mock_client:
            mock_client.post.return_value = mock_response

            result = await authenticator._authenticate()

            assert result == {"access_token": "custom-token"}
            mock_client.post.assert_called_once_with(
                "https://custom.iam.checkmarx.net/auth/realms/custom-tenant/protocol/openid-connect/token",
                data={
                    "grant_type": "refresh_token",
                    "client_id": "ast-app",
                    "refresh_token": "custom-api-key",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

    @pytest.mark.asyncio
    async def test_authenticate_logs_debug_message(self, token_authenticator: TokenAuthenticator, mock_response: MagicMock) -> None:
        """Test that debug message is logged during authentication."""
        with patch.object(token_authenticator, 'http_client', AsyncMock()) as mock_client:
            mock_client.post.return_value = mock_response

            with patch.object(logger, 'debug') as mock_logger:
                await token_authenticator._authenticate()

                mock_logger.assert_called_with("Authenticating with API key")

    @pytest.mark.asyncio
    async def test_authenticate_logs_error_on_failure(self, token_authenticator: TokenAuthenticator) -> None:
        """Test that error is logged on authentication failure."""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_response.raise_for_status.side_effect = HTTPStatusError(
            "400 Bad Request", request=MagicMock(), response=mock_response
        )

        with patch.object(token_authenticator, 'http_client', AsyncMock()) as mock_client:
            mock_client.post.return_value = mock_response

            with patch.object(logger, 'error') as mock_logger:
                with pytest.raises(CheckmarxAuthenticationError):
                    await token_authenticator._authenticate()

                mock_logger.assert_called_with(
                    "API key authentication failed: 400 - Bad Request"
                )
