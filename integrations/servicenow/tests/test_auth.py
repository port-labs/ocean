import pytest
import base64
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from auth.basic_authenticator import BasicAuthenticator
from auth.oauth_authenticator import (
    OAuthClientCredentialsAuthenticator,
    ServiceNowToken,
)
from .conftest import TEST_INTEGRATION_CONFIG
from datetime import datetime, timezone, timedelta


class TestBasicAuthenticator:
    """Test suite for Basic Authentication."""

    @pytest.mark.asyncio
    async def test_get_headers(self) -> None:
        """Test Basic Auth header generation."""
        authenticator = BasicAuthenticator(
            username=TEST_INTEGRATION_CONFIG["servicenow_username"],
            password=TEST_INTEGRATION_CONFIG["servicenow_password"],
        )

        headers = await authenticator.get_headers()

        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")
        assert "Content-Type" in headers
        assert headers["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_get_headers_encoding(self) -> None:
        """Test that Basic Auth encoding is correct."""
        authenticator = BasicAuthenticator(username="test_user", password="test_pass")
        headers = await authenticator.get_headers()
        auth_value = headers["Authorization"].replace("Basic ", "")
        decoded = base64.b64decode(auth_value).decode("ascii")
        assert decoded == "test_user:test_pass"


class TestOAuthClientCredentialsAuthenticator:
    """Test suite for OAuth Client Credentials Authentication."""

    @pytest.mark.asyncio
    async def test_get_headers_with_valid_token(
        self, oauth_authenticator: OAuthClientCredentialsAuthenticator
    ) -> None:
        """Test getting headers with a valid cached token."""
        mock_token = ServiceNowToken(
            access_token="test_access_token",
            expires_in=3600,
            token_type="Bearer",
        )
        oauth_authenticator.cached_token = mock_token

        with patch("auth.oauth_authenticator.datetime") as mock_datetime:
            mock_now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = mock_now
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

            headers = await oauth_authenticator.get_headers()

            assert headers["Authorization"] == "Bearer test_access_token"
            assert headers["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_fetch_token_success(
        self, oauth_authenticator: OAuthClientCredentialsAuthenticator
    ) -> None:
        """Test successful token fetch."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "new_access_token",
            "expires_in": 1800,
            "token_type": "Bearer",
        }
        mock_response.raise_for_status.return_value = None

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch(
            "auth.oauth_authenticator.OAuthClientCredentialsAuthenticator._http_client",
            new_callable=lambda: property(lambda self: mock_client),
        ):
            token = await oauth_authenticator._fetch_token()

            assert token.access_token == "new_access_token"
            assert token.expires_in == 1800
            assert token.token_type == "Bearer"
            assert not token.is_expired

    @pytest.mark.asyncio
    async def test_fetch_token_error(
        self, oauth_authenticator: OAuthClientCredentialsAuthenticator
    ) -> None:
        """Test token fetch error handling."""
        error_response = MagicMock()
        error_response.status_code = 401
        error_response.text = "Invalid credentials"
        error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=error_response
        )

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=error_response)

        with patch(
            "auth.oauth_authenticator.OAuthClientCredentialsAuthenticator._http_client",
            new_callable=lambda: property(lambda self: mock_client),
        ):
            with pytest.raises(httpx.HTTPStatusError):
                await oauth_authenticator._fetch_token()

    @pytest.mark.asyncio
    async def test_get_valid_token_refreshes_expired_token(
        self, oauth_authenticator: OAuthClientCredentialsAuthenticator
    ) -> None:
        """Test that expired tokens are refreshed."""
        expired_time = datetime.now(timezone.utc) - timedelta(hours=1)
        expired_token = ServiceNowToken(
            access_token="expired_token",
            expires_in=1800,
            token_type="Bearer",
        )
        expired_token._created_at = expired_time
        oauth_authenticator.cached_token = expired_token

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "new_refreshed_token",
            "expires_in": 1800,
            "token_type": "Bearer",
        }
        mock_response.raise_for_status.return_value = None

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch(
            "auth.oauth_authenticator.OAuthClientCredentialsAuthenticator._http_client",
            new_callable=lambda: property(lambda self: mock_client),
        ):
            token = await oauth_authenticator._get_valid_token()

            assert token.access_token == "new_refreshed_token"
            assert (
                oauth_authenticator.cached_token.access_token == "new_refreshed_token"
            )

    def test_get_basic_auth_header(self) -> None:
        """Test Basic Auth header generation for OAuth token request."""
        authenticator = OAuthClientCredentialsAuthenticator(
            servicenow_url="https://test.service-now.com",
            client_id="test_client_id",
            client_secret="test_client_secret",
        )

        auth_header = authenticator._get_basic_auth_header()
        assert auth_header.startswith("Basic ")
        encoded = auth_header.replace("Basic ", "")
        decoded = base64.b64decode(encoded).decode("utf-8")
        assert decoded == "test_client_id:test_client_secret"

    def test_token_is_expired(self) -> None:
        """Test token expiration check."""

        expired_time = datetime.now(timezone.utc) - timedelta(hours=1)
        expired_token = ServiceNowToken(
            access_token="token",
            expires_in=1800,
            token_type="Bearer",
        )
        expired_token._created_at = expired_time
        assert expired_token.is_expired

        valid_token = ServiceNowToken(
            access_token="token",
            expires_in=3600,
            token_type="Bearer",
        )
        assert not valid_token.is_expired

    @pytest.mark.asyncio
    async def test_token_lock_prevents_race_condition(
        self, oauth_authenticator: OAuthClientCredentialsAuthenticator
    ) -> None:
        """Test that token lock prevents multiple simultaneous token fetches."""
        call_count = 0

        async def mock_fetch_token() -> ServiceNowToken:
            nonlocal call_count
            call_count += 1
            return ServiceNowToken(
                access_token=f"token_{call_count}",
                expires_in=1800,
                token_type="Bearer",
            )

        oauth_authenticator._fetch_token = mock_fetch_token

        import asyncio

        tasks = [oauth_authenticator._get_valid_token() for _ in range(5)]
        tokens = await asyncio.gather(*tasks)

        assert all(token.access_token == tokens[0].access_token for token in tokens)
        assert call_count == 1
