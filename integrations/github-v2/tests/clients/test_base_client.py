import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from github.clients.base_client import HTTPBaseClient


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Initialize mock Ocean context for all tests"""
    try:
        mock_app = MagicMock()
        mock_app.config.integration.config = {
            "github_host": "https://api.github.com",
            "github_token": "test-token",
        }
        initialize_port_ocean_context(mock_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.mark.asyncio
class TestHTTPBaseClient:
    @pytest.fixture
    def client(self) -> HTTPBaseClient:
        """Initialize HTTPBaseClient with test configuration"""
        return HTTPBaseClient(
            "https://api.github.com", "test-token", endpoint="api/v4"
        )

    async def test_send_api_request_success(self, client: HTTPBaseClient) -> None:
        """Test successful API request"""
        # Arrange
        method = "GET"
        path = "repos/owner/repo"
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 1, "name": "Test Repo"}
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            client._client, "request", AsyncMock(return_value=mock_response)
        ) as mock_request:
            # Act
            result = await client.send_api_request(method, path)

            # Assert
            assert result == mock_response
            mock_request.assert_called_once_with(
                method=method,
                url=f"{client.base_url}/{path}",
                headers=client._headers,
                params=None,
                json=None,
            )

    async def test_send_api_request_rate_limit(self, client: HTTPBaseClient) -> None:
        """Test API request with rate limiting"""
        # Arrange
        method = "GET"
        path = "repos/owner/repo"

        # Create rate limit response
        rate_limit_response = MagicMock()
        rate_limit_response.status_code = 403
        rate_limit_response.headers = {
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(int(time.time()) + 1)
        }
        rate_limit_error = httpx.HTTPStatusError(
            "Rate limited",
            request=MagicMock(),
            response=rate_limit_response
        )
        rate_limit_response.raise_for_status.side_effect = rate_limit_error

        # Create success response
        success_response = MagicMock()
        success_response.json.return_value = {"id": 1, "name": "Test Repo"}
        success_response.status_code = 200
        success_response.raise_for_status = MagicMock()

        with patch.object(
            client._client,
            "request",
            AsyncMock(side_effect=[rate_limit_response, success_response])
        ) as mock_request:
            with patch("asyncio.sleep", AsyncMock()) as mock_sleep:
                # Act
                result = await client.send_api_request(method, path)

                # Assert
                assert result == success_response
                assert mock_request.call_count == 2
                mock_sleep.assert_called_once()

    async def test_send_api_request_404(self, client: HTTPBaseClient) -> None:
        """Test API request with 404 response"""
        # Arrange
        method = "GET"
        path = "repos/owner/nonexistent"
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=mock_response
        )

        with patch.object(
            client._client, "request", AsyncMock(return_value=mock_response)
        ) as mock_request:
            # Act
            result = await client.send_api_request(method, path)

            # Assert
            assert result == mock_response
            mock_request.assert_called_once()

    async def test_send_api_request_network_error(self, client: HTTPBaseClient) -> None:
        """Test API request with network error"""
        # Arrange
        method = "GET"
        path = "repos/owner/repo"
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.NetworkError("Connection error")

        with patch.object(
            client._client,
            "request",
            AsyncMock(return_value=mock_response),
        ) as mock_request:
            # Act & Assert
            import pytest
            with pytest.raises(httpx.NetworkError):
                await client.send_api_request(method, path)
            mock_request.assert_called_once()
