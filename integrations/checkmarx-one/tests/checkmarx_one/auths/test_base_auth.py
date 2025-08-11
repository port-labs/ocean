import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any, Dict

from checkmarx_one.auths.base_auth import BaseCheckmarxAuthenticator
from checkmarx_one.exceptions import CheckmarxAuthenticationError


class MockAuthenticator(BaseCheckmarxAuthenticator):
    """Mock implementation of BaseCheckmarxAuthenticator for testing."""

    async def _authenticate(self) -> Dict[str, Any]:
        """Mock authentication method."""
        return {
            "access_token": "mock_access_token",
            "refresh_token": "mock_refresh_token",
            "expires_in": 1800,
        }


class TestBaseCheckmarxAuthenticator:
    """Test cases for BaseCheckmarxAuthenticator."""

    @pytest.fixture
    def mock_http_client(self) -> MagicMock:
        """Create a mock HTTP client for testing."""
        mock_client = AsyncMock()
        mock_client.timeout = None
        return mock_client

    @pytest.fixture
    def authenticator(self, mock_http_client: MagicMock) -> MockAuthenticator:
        """Create a mock authenticator instance for testing."""
        with patch("port_ocean.utils.http_async_client", mock_http_client):
            return MockAuthenticator(
                iam_url="https://iam.checkmarx.net", tenant="test-tenant"
            )

    @pytest.fixture
    def token_response(self) -> Dict[str, Any]:
        """Sample token response for testing."""
        return {
            "access_token": "test_access_token_123",
            "refresh_token": "test_refresh_token_456",
            "expires_in": 1800,
        }

    def test_init(
        self, authenticator: MockAuthenticator, mock_http_client: MagicMock
    ) -> None:
        """Test authenticator initialization."""
        assert authenticator.iam_url == "https://iam.checkmarx.net"
        assert authenticator.tenant == "test-tenant"
        assert authenticator._access_token is None
        assert authenticator._refresh_token is None
        assert authenticator._token_expires_at is None

    def test_auth_url_property(self, authenticator: MockAuthenticator) -> None:
        """Test auth_url property construction."""
        expected_url = "https://iam.checkmarx.net/auth/realms/test-tenant/protocol/openid-connect/token"
        assert authenticator.auth_url == expected_url

    def test_auth_url_with_trailing_slash(self, mock_http_client: MagicMock) -> None:
        """Test auth_url property handles trailing slashes correctly."""
        with patch("port_ocean.utils.http_async_client", mock_http_client):
            authenticator = MockAuthenticator(
                iam_url="https://iam.checkmarx.net/", tenant="test-tenant"
            )
            expected_url = "https://iam.checkmarx.net/auth/realms/test-tenant/protocol/openid-connect/token"
            assert authenticator.auth_url == expected_url

    def test_is_token_expired_no_token(self, authenticator: MockAuthenticator) -> None:
        """Test is_token_expired when no token exists."""
        assert authenticator.is_token_expired is True

    def test_is_token_expired_valid_token(
        self, authenticator: MockAuthenticator
    ) -> None:
        """Test is_token_expired when token is valid."""
        # Set token to expire in 2 minutes (120 seconds)
        authenticator._token_expires_at = time.time() + 120
        assert authenticator.is_token_expired is False

    def test_is_token_expired_expired_token(
        self, authenticator: MockAuthenticator
    ) -> None:
        """Test is_token_expired when token is expired."""
        # Set token to expire 2 minutes ago
        authenticator._token_expires_at = time.time() - 120
        assert authenticator.is_token_expired is True

    def test_is_token_expired_near_expiry(
        self, authenticator: MockAuthenticator
    ) -> None:
        """Test is_token_expired when token is near expiry (within 60 second buffer)."""
        # Set token to expire in 30 seconds (within 60 second buffer)
        authenticator._token_expires_at = time.time() + 30
        assert authenticator.is_token_expired is True

    @pytest.mark.asyncio
    async def test_refresh_access_token_success(
        self, authenticator: MockAuthenticator, token_response: Dict[str, Any]
    ) -> None:
        """Test successful token refresh."""
        with patch.object(authenticator, "_authenticate", return_value=token_response):
            await authenticator._refresh_access_token()

            assert authenticator._access_token == "test_access_token_123"
            assert authenticator._refresh_token == "test_refresh_token_456"
            assert authenticator._token_expires_at is not None
            assert authenticator._token_expires_at > time.time()

    @pytest.mark.asyncio
    async def test_refresh_access_token_without_refresh_token(
        self, authenticator: MockAuthenticator
    ) -> None:
        """Test token refresh when response doesn't include refresh token."""
        token_response = {
            "access_token": "test_access_token_123",
            "expires_in": 1800,
        }

        with patch.object(authenticator, "_authenticate", return_value=token_response):
            await authenticator._refresh_access_token()

            assert authenticator._access_token == "test_access_token_123"
            assert authenticator._refresh_token is None
            assert authenticator._token_expires_at is not None

    @pytest.mark.asyncio
    async def test_refresh_access_token_with_default_expiry(
        self, authenticator: MockAuthenticator
    ) -> None:
        """Test token refresh with default expiry time."""
        token_response = {
            "access_token": "test_access_token_123",
        }

        with patch.object(authenticator, "_authenticate", return_value=token_response):
            await authenticator._refresh_access_token()

            assert authenticator._access_token == "test_access_token_123"
            # Should use default 1800 seconds (30 minutes)
            expected_expiry = time.time() + 1800
            gotten = authenticator._token_expires_at or 0
            result: float = gotten - expected_expiry
            assert abs(result) < 1

    @pytest.mark.asyncio
    async def test_refresh_access_token_authentication_error(
        self, authenticator: MockAuthenticator
    ) -> None:
        """Test token refresh when authentication fails."""
        with patch.object(
            authenticator, "_authenticate", side_effect=Exception("Auth failed")
        ):
            with pytest.raises(
                CheckmarxAuthenticationError, match="Token refresh failed: Auth failed"
            ):
                await authenticator._refresh_access_token()

    @pytest.mark.asyncio
    async def test_get_access_token_no_token(
        self, authenticator: MockAuthenticator, token_response: Dict[str, Any]
    ) -> None:
        """Test getting access token when no token exists."""
        with patch.object(authenticator, "_authenticate", return_value=token_response):
            result = await authenticator._get_access_token()

            assert result == "test_access_token_123"

    @pytest.mark.asyncio
    async def test_get_access_token_expired_token(
        self, authenticator: MockAuthenticator, token_response: Dict[str, Any]
    ) -> None:
        """Test getting access token when token is expired."""
        authenticator._access_token = "old_token"
        authenticator._token_expires_at = time.time() - 60  # Expired

        with patch.object(authenticator, "_authenticate", return_value=token_response):
            result = await authenticator._get_access_token()

            assert result == "test_access_token_123"

    @pytest.mark.asyncio
    async def test_get_access_token_valid_token(
        self, authenticator: MockAuthenticator
    ) -> None:
        """Test getting access token when token is valid."""
        authenticator._access_token = "valid_token"
        authenticator._token_expires_at = time.time() + 120  # Valid for 2 minutes

        with patch.object(authenticator, "_refresh_access_token") as mock_refresh:
            result = await authenticator._get_access_token()

            mock_refresh.assert_not_called()
            assert result == "valid_token"

    @pytest.mark.asyncio
    async def test_get_auth_headers_success(
        self, authenticator: MockAuthenticator, token_response: Dict[str, Any]
    ) -> None:
        """Test getting authentication headers successfully."""
        with patch.object(authenticator, "_authenticate", return_value=token_response):
            headers = await authenticator.get_auth_headers()

            assert headers == {
                "Authorization": "Bearer test_access_token_123",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }

    @pytest.mark.asyncio
    async def test_get_auth_headers_no_token(
        self, authenticator: MockAuthenticator
    ) -> None:
        """Test getting authentication headers when no token is available."""
        with patch.object(
            authenticator, "_authenticate", side_effect=Exception("Auth failed")
        ):
            with pytest.raises(
                CheckmarxAuthenticationError, match="Token refresh failed: Auth failed"
            ):
                await authenticator.get_auth_headers()

    def test_abstract_method_implementation(self, mock_http_client: MagicMock) -> None:
        """Test that abstract method is properly defined."""
        # This should not raise an error since MockAuthenticator implements _authenticate
        with patch("port_ocean.utils.http_async_client", mock_http_client):
            authenticator = MockAuthenticator(
                iam_url="https://iam.checkmarx.net", tenant="test-tenant"
            )
            assert hasattr(authenticator, "_authenticate")
            assert callable(authenticator._authenticate)
