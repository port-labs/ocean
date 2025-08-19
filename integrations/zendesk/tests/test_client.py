import pytest
from unittest.mock import Mock, AsyncMock, patch
import httpx

from zendesk.client import ZendeskClient, ZendeskBasicAuth, ZendeskBearerAuth


class TestZendeskAuth:
    """Test authentication classes."""

    def test_basic_auth_flow(self):
        """Test basic auth credential encoding."""
        auth = ZendeskBasicAuth("test@example.com", "api_token")
        request = httpx.Request("GET", "https://example.com")
        
        auth_request = next(auth.auth_flow(request))
        
        # Should encode email/token:api_token in base64
        assert "Authorization" in auth_request.headers
        assert auth_request.headers["Authorization"].startswith("Basic ")

    def test_bearer_auth_flow(self):
        """Test bearer auth token."""
        auth = ZendeskBearerAuth("oauth_token")
        request = httpx.Request("GET", "https://example.com")
        
        auth_request = next(auth.auth_flow(request))
        
        assert auth_request.headers["Authorization"] == "Bearer oauth_token"


class TestZendeskClient:
    """Test ZendeskClient functionality."""

    def test_client_initialization_with_api_token(self):
        """Test client initialization with API token."""
        client = ZendeskClient(
            subdomain="test",
            email="test@example.com",
            token="api_token"
        )
        
        assert client.subdomain == "test"
        assert client.base_url == "https://test.zendesk.com"
        assert client.api_url == "https://test.zendesk.com/api/v2"
        assert isinstance(client.auth, ZendeskBasicAuth)

    def test_client_initialization_with_oauth_token(self):
        """Test client initialization with OAuth token."""
        client = ZendeskClient(
            subdomain="test",
            oauth_token="oauth_token"
        )
        
        assert client.subdomain == "test"
        assert isinstance(client.auth, ZendeskBearerAuth)

    def test_client_initialization_without_credentials(self):
        """Test client initialization without proper credentials."""
        with pytest.raises(ValueError, match="Must provide either oauth_token or both email and token"):
            ZendeskClient(subdomain="test")

    @pytest.mark.asyncio
    async def test_test_connection_success(self):
        """Test successful connection test."""
        with patch("zendesk.client.http_async_client") as mock_client:
            mock_response = Mock()
            mock_response.json.return_value = {"user": {"id": 123}}
            mock_response.raise_for_status = Mock()
            
            mock_client.request = AsyncMock(return_value=mock_response)
            
            client = ZendeskClient(
                subdomain="test",
                email="test@example.com",
                token="api_token"
            )
            
            result = await client.test_connection()
            assert result is True

    @pytest.mark.asyncio
    async def test_test_connection_failure(self):
        """Test connection test failure."""
        with patch("zendesk.client.http_async_client") as mock_client:
            mock_client.request = AsyncMock(side_effect=httpx.RequestError("Connection failed"))
            
            client = ZendeskClient(
                subdomain="test",
                email="test@example.com",
                token="api_token"
            )
            
            result = await client.test_connection()
            assert result is False

    @pytest.mark.asyncio
    async def test_send_api_request_success(self):
        """Test successful API request."""
        with patch("zendesk.client.http_async_client") as mock_client:
            mock_response = Mock()
            mock_response.json.return_value = {"data": "test"}
            mock_response.raise_for_status = Mock()
            
            mock_client.request = AsyncMock(return_value=mock_response)
            
            client = ZendeskClient(
                subdomain="test",
                email="test@example.com",
                token="api_token"
            )
            
            result = await client._send_api_request("GET", "tickets.json")
            assert result == {"data": "test"}

    @pytest.mark.asyncio
    async def test_rate_limit_handling(self):
        """Test rate limit handling."""
        with patch("zendesk.client.http_async_client") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 429
            mock_response.headers = {"Retry-After": "60"}
            
            mock_client.request = AsyncMock(
                side_effect=httpx.HTTPStatusError("Rate limited", request=Mock(), response=mock_response)
            )
            
            client = ZendeskClient(
                subdomain="test",
                email="test@example.com",
                token="api_token"
            )
            
            with patch("asyncio.sleep") as mock_sleep:
                with pytest.raises(httpx.HTTPStatusError):
                    await client._send_api_request("GET", "tickets.json")
                
                # Should have called sleep with the retry-after value
                mock_sleep.assert_called_with(60)