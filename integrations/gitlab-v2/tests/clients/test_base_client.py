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

    async def test_send_api_request_403(self, client: HTTPBaseClient) -> None:
        """Test API request with 403 Forbidden response"""
        # Arrange
        method = "GET"
        path = "projects/secret"
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Forbidden", request=MagicMock(), response=MagicMock(status_code=403)
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

    async def test_send_api_request_401_no_refresh(
        self, client: HTTPBaseClient
    ) -> None:
        """Test API request with 401 Unauthorized response when token refresh fails"""
        # Arrange
        method = "GET"
        path = "projects/private"
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=MagicMock(status_code=401)
        )

        with (
            patch.object(
                client._client, "request", AsyncMock(return_value=mock_response)
            ) as mock_request,
            patch.object(
                client, "_refresh_token", AsyncMock(return_value=False)
            ) as mock_refresh,
        ):
            # Act & Assert
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await client.send_api_request(method, path)

            assert exc_info.value.response.status_code == 401
            mock_request.assert_called_once_with(
                method=method,
                url=f"{client.base_url}/{path}",
                headers=client._headers,
                params=None,
                json=None,
            )
            mock_refresh.assert_called_once()

    async def test_send_api_request_401_with_successful_refresh(
        self, client: HTTPBaseClient
    ) -> None:
        """Test API request with 401 that succeeds after token refresh"""
        # Arrange
        method = "GET"
        path = "projects/private"

        # First response fails with 401
        mock_401_response = MagicMock()
        mock_401_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=MagicMock(status_code=401)
        )

        # Second response succeeds
        mock_success_response = MagicMock()
        mock_success_response.json.return_value = {"id": 1, "name": "Private Project"}
        mock_success_response.raise_for_status = MagicMock()

        with (
            patch.object(
                client._client,
                "request",
                AsyncMock(side_effect=[mock_401_response, mock_success_response]),
            ) as mock_request,
            patch.object(
                client, "_refresh_token", AsyncMock(return_value=True)
            ) as mock_refresh,
        ):
            # Act
            result = await client.send_api_request(method, path)

            # Assert
            assert result == {"id": 1, "name": "Private Project"}
            assert mock_request.call_count == 2
            mock_refresh.assert_called_once()

    async def test_refresh_token_success(self, client: HTTPBaseClient) -> None:
        """Test successful token refresh"""
        # Arrange
        with patch.object(
            client._auth_client, "get_refreshed_token", return_value="new-token"
        ) as mock_get_token:
            # Act
            result = await client._refresh_token()

            # Assert
            assert result is True
            assert client.token == "new-token"
            assert client._auth_client.token == "new-token"
            mock_get_token.assert_called_once()

    async def test_refresh_token_failure(self, client: HTTPBaseClient) -> None:
        """Test token refresh failure"""
        # Arrange
        original_token = client.token

        with patch.object(
            client._auth_client,
            "get_refreshed_token",
            side_effect=ValueError("Token not available"),
        ) as mock_get_token:
            # Act
            result = await client._refresh_token()

            # Assert
            assert result is False
            assert client.token == original_token  # Token should remain unchanged
            assert client._auth_client.token == original_token
            mock_get_token.assert_called_once()
