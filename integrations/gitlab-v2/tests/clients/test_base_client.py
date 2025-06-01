from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from gitlab.clients.base_client import HTTPBaseClient


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Initialize mock Ocean context for all tests"""
    try:
        mock_app = MagicMock()
        mock_app.config.integration.config = {
            "gitlab_host": "https://gitlab.example.com",
            "gitlab_token": "test-token",
        }
        mock_app.cache_provider = AsyncMock()
        mock_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.mark.asyncio
class TestHTTPBaseClient:
    @pytest.fixture
    def client(self) -> HTTPBaseClient:
        """Initialize HTTPBaseClient with test configuration"""
        return HTTPBaseClient(
            "https://gitlab.example.com", "test-token", endpoint="api/v4"
        )

    async def test_send_api_request_success(self, client: HTTPBaseClient) -> None:
        """Test successful API request"""
        # Arrange
        method = "GET"
        path = "projects"
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 1, "name": "Test Project"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            client._client, "request", AsyncMock(return_value=mock_response)
        ) as mock_request:
            # Act
            result = await client.send_api_request(method, path)

            # Assert
            assert result == {"id": 1, "name": "Test Project"}
            mock_request.assert_called_once_with(
                method=method,
                url=f"{client.base_url}/{path}",
                headers=client._headers,
                params=None,
                json=None,
            )
            mock_response.raise_for_status.assert_called_once()

    async def test_send_api_request_with_params(self, client: HTTPBaseClient) -> None:
        """Test API request with query parameters"""
        # Arrange
        method = "GET"
        path = "projects"
        params = {"per_page": 10, "page": 1}
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 1, "name": "Test Project"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            client._client, "request", AsyncMock(return_value=mock_response)
        ) as mock_request:
            # Act
            result = await client.send_api_request(method, path, params=params)

            # Assert
            assert result == {"id": 1, "name": "Test Project"}
            mock_request.assert_called_once_with(
                method=method,
                url=f"{client.base_url}/{path}",
                headers=client._headers,
                params=params,
                json=None,
            )

    async def test_send_api_request_with_data(self, client: HTTPBaseClient) -> None:
        """Test API request with request body data"""
        # Arrange
        method = "POST"
        path = "projects"
        data = {"name": "New Project", "description": "Test Description"}
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 1, "name": "New Project"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            client._client, "request", AsyncMock(return_value=mock_response)
        ) as mock_request:
            # Act
            result = await client.send_api_request(method, path, data=data)

            # Assert
            assert result == {"id": 1, "name": "New Project"}
            mock_request.assert_called_once_with(
                method=method,
                url=f"{client.base_url}/{path}",
                headers=client._headers,
                params=None,
                json=data,
            )

    async def test_send_api_request_404(self, client: HTTPBaseClient) -> None:
        """Test API request with 404 response"""
        # Arrange
        method = "GET"
        path = "projects/999"
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=MagicMock(status_code=404)
        )

        with patch.object(
            client._client, "request", AsyncMock(return_value=mock_response)
        ) as mock_request:
            # Act
            result = await client.send_api_request(method, path)

            # Assert
            assert result == {}
            mock_request.assert_called_once_with(
                method=method,
                url=f"{client.base_url}/{path}",
                headers=client._headers,
                params=None,
                json=None,
            )

    async def test_send_api_request_other_error(self, client: HTTPBaseClient) -> None:
        """Test API request with other HTTP error"""
        # Arrange
        method = "GET"
        path = "projects"
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=MagicMock(status_code=500)
        )

        with patch.object(
            client._client, "request", AsyncMock(return_value=mock_response)
        ) as mock_request:
            # Act & Assert
            with pytest.raises(httpx.HTTPStatusError):
                await client.send_api_request(method, path)

            mock_request.assert_called_once_with(
                method=method,
                url=f"{client.base_url}/{path}",
                headers=client._headers,
                params=None,
                json=None,
            )

    async def test_send_api_request_network_error(self, client: HTTPBaseClient) -> None:
        """Test API request with network error"""
        # Arrange
        method = "GET"
        path = "projects"

        with patch.object(
            client._client,
            "request",
            AsyncMock(side_effect=httpx.NetworkError("Connection error")),
        ) as mock_request:
            # Act & Assert
            with pytest.raises(httpx.NetworkError):
                await client.send_api_request(method, path)

            mock_request.assert_called_once_with(
                method=method,
                url=f"{client.base_url}/{path}",
                headers=client._headers,
                params=None,
                json=None,
            )
