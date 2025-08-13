import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import HTTPStatusError, Response
from loguru import logger

from checkmarx_one.auths.oauth import OAuthAuthenticator
from checkmarx_one.exceptions import CheckmarxAuthenticationError


class TestOAuthAuthenticator:
    """Test cases for OAuthAuthenticator class."""

    @pytest.fixture
    def oauth_authenticator(self) -> OAuthAuthenticator:
        """Create an OAuthAuthenticator instance for testing."""
        with patch("checkmarx_one.auths.base_auth.http_async_client", AsyncMock()):
            return OAuthAuthenticator(
                iam_url="https://iam.checkmarx.net",
                tenant="test-tenant",
                client_id="test-client-id",
                client_secret="test-client-secret",
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
            "token_type": "Bearer",
        }
        mock_response.raise_for_status.return_value = None
        return mock_response

    def test_init(self, oauth_authenticator: OAuthAuthenticator) -> None:
        """Test OAuthAuthenticator initialization."""
        assert oauth_authenticator.iam_url == "https://iam.checkmarx.net"
        assert oauth_authenticator.tenant == "test-tenant"
        assert oauth_authenticator.client_id == "test-client-id"
        assert oauth_authenticator.client_secret == "test-client-secret"
        assert (
            oauth_authenticator.auth_url
            == "https://iam.checkmarx.net/auth/realms/test-tenant/protocol/openid-connect/token"
        )

    @pytest.mark.asyncio
    async def test_authenticate_success(
        self, oauth_authenticator: OAuthAuthenticator, mock_response: MagicMock
    ) -> None:
        """Test successful OAuth authentication."""
        with patch.object(
            oauth_authenticator, "http_client", AsyncMock()
        ) as mock_client:
            mock_client.post.return_value = mock_response

            result = await oauth_authenticator._authenticate()

            # Verify the result
            assert result == {
                "access_token": "test-access-token",
                "refresh_token": "test-refresh-token",
                "expires_in": 1800,
            }

            # Verify the HTTP call
            mock_client.post.assert_called_once_with(
                oauth_authenticator.auth_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": "test-client-id",
                    "client_secret": "test-client-secret",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

    @pytest.mark.asyncio
    async def test_authenticate_http_error(
        self, oauth_authenticator: OAuthAuthenticator
    ) -> None:
        """Test OAuth authentication with HTTP error."""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.raise_for_status.side_effect = HTTPStatusError(
            "401 Unauthorized", request=MagicMock(), response=mock_response
        )

        with patch.object(
            oauth_authenticator, "http_client", AsyncMock()
        ) as mock_client:
            mock_client.post.return_value = mock_response

            with pytest.raises(CheckmarxAuthenticationError) as exc_info:
                await oauth_authenticator._authenticate()

            assert "OAuth authentication failed: Unauthorized" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_authenticate_network_error(
        self, oauth_authenticator: OAuthAuthenticator
    ) -> None:
        """Test OAuth authentication with network error."""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 500
        mock_response.text = "Network error"
        mock_response.raise_for_status.side_effect = HTTPStatusError(
            "500 Network error", request=MagicMock(), response=mock_response
        )

        with patch.object(
            oauth_authenticator, "http_client", AsyncMock()
        ) as mock_client:
            mock_client.post.return_value = mock_response

            with pytest.raises(CheckmarxAuthenticationError) as exc_info:
                await oauth_authenticator._authenticate()

            assert "OAuth authentication failed: Network error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_authenticate_invalid_response(
        self, oauth_authenticator: OAuthAuthenticator
    ) -> None:
        """Test OAuth authentication with invalid response format."""
        mock_response = MagicMock(spec=Response)
        mock_response.json.return_value = {"error": "invalid_client"}
        mock_response.raise_for_status.return_value = None

        with patch.object(
            oauth_authenticator, "http_client", AsyncMock()
        ) as mock_client:
            mock_client.post.return_value = mock_response

            with pytest.raises(KeyError):
                await oauth_authenticator._authenticate()

    @pytest.mark.asyncio
    async def test_authenticate_empty_response(
        self, oauth_authenticator: OAuthAuthenticator
    ) -> None:
        """Test OAuth authentication with empty response."""
        mock_response = MagicMock(spec=Response)
        mock_response.json.return_value = {}
        mock_response.raise_for_status.return_value = None

        with patch.object(
            oauth_authenticator, "http_client", AsyncMock()
        ) as mock_client:
            mock_client.post.return_value = mock_response

            with pytest.raises(KeyError):
                await oauth_authenticator._authenticate()

    @pytest.mark.asyncio
    async def test_authenticate_with_different_credentials(self) -> None:
        """Test OAuth authentication with different credentials."""
        with patch("checkmarx_one.auths.base_auth.http_async_client", AsyncMock()):
            authenticator = OAuthAuthenticator(
                iam_url="https://custom.iam.checkmarx.net",
                tenant="custom-tenant",
                client_id="custom-client-id",
                client_secret="custom-client-secret",
            )

        mock_response = MagicMock(spec=Response)
        mock_response.json.return_value = {
            "access_token": "custom-token",
            "refresh_token": "custom-refresh",
            "expires_in": 3600,
        }
        mock_response.raise_for_status.return_value = None

        with patch.object(authenticator, "http_client", AsyncMock()) as mock_client:
            mock_client.post.return_value = mock_response

            result = await authenticator._authenticate()

            assert result == {
                "access_token": "custom-token",
                "refresh_token": "custom-refresh",
                "expires_in": 3600,
            }
            mock_client.post.assert_called_once_with(
                "https://custom.iam.checkmarx.net/auth/realms/custom-tenant/protocol/openid-connect/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": "custom-client-id",
                    "client_secret": "custom-client-secret",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

    @pytest.mark.asyncio
    async def test_authenticate_logs_debug_message(
        self, oauth_authenticator: OAuthAuthenticator, mock_response: MagicMock
    ) -> None:
        """Test that debug message is logged during OAuth authentication."""
        with patch.object(
            oauth_authenticator, "http_client", AsyncMock()
        ) as mock_client:
            mock_client.post.return_value = mock_response

            with patch.object(logger, "debug") as mock_logger:
                await oauth_authenticator._authenticate()

                mock_logger.assert_called_with(
                    "Authenticating with OAuth client: test-client-id"
                )

    @pytest.mark.asyncio
    async def test_authenticate_logs_error_on_failure(
        self, oauth_authenticator: OAuthAuthenticator
    ) -> None:
        """Test that error is logged on OAuth authentication failure."""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_response.raise_for_status.side_effect = HTTPStatusError(
            "400 Bad Request", request=MagicMock(), response=mock_response
        )

        with patch.object(
            oauth_authenticator, "http_client", AsyncMock()
        ) as mock_client:
            mock_client.post.return_value = mock_response

            with patch.object(logger, "error") as mock_logger:
                with pytest.raises(CheckmarxAuthenticationError):
                    await oauth_authenticator._authenticate()

                mock_logger.assert_called_with(
                    "OAuth authentication failed: 400 - Bad Request"
                )

    @pytest.mark.asyncio
    async def test_authenticate_with_special_characters_in_credentials(self) -> None:
        """Test OAuth authentication with special characters in credentials."""
        with patch("checkmarx_one.auths.base_auth.http_async_client", AsyncMock()):
            authenticator = OAuthAuthenticator(
                iam_url="https://iam.checkmarx.net",
                tenant="test-tenant",
                client_id="client@id",
                client_secret="secret@123!",
            )

        mock_response = MagicMock(spec=Response)
        mock_response.json.return_value = {
            "access_token": "special-token",
            "refresh_token": "special-refresh",
            "expires_in": 1800,
        }
        mock_response.raise_for_status.return_value = None

        with patch.object(authenticator, "http_client", AsyncMock()) as mock_client:
            mock_client.post.return_value = mock_response

            result = await authenticator._authenticate()

            assert result == {
                "access_token": "special-token",
                "refresh_token": "special-refresh",
                "expires_in": 1800,
            }
            mock_client.post.assert_called_once_with(
                "https://iam.checkmarx.net/auth/realms/test-tenant/protocol/openid-connect/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": "client@id",
                    "client_secret": "secret@123!",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
