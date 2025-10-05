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
class TestTokenRefreshIntegration:
    """Integration tests for token refresh functionality in HTTPBaseClient"""

    @pytest.fixture
    def client(self) -> HTTPBaseClient:
        """Initialize HTTPBaseClient with test configuration"""
        return HTTPBaseClient(
            "https://gitlab.example.com", "test-token", endpoint="api/v4"
        )

    async def test_token_refresh_integration_success(self, client: HTTPBaseClient) -> None:
        """Test complete token refresh flow when 401 occurs and refresh succeeds"""
        method = "GET"
        path = "projects"

        # First response fails with 401
        mock_401_response = MagicMock()
        mock_401_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=MagicMock(status_code=401)
        )

        # Second response succeeds after token refresh
        mock_success_response = MagicMock()
        mock_success_response.json.return_value = {"id": 1, "name": "Test Project"}
        mock_success_response.raise_for_status = MagicMock()

        with patch.object(
            client._client, "request", AsyncMock(side_effect=[mock_401_response, mock_success_response])
        ) as mock_request, patch.object(
            client._auth_client, "get_refreshed_token", return_value="refreshed-token"
        ) as mock_get_refreshed_token:
            # Act
            result = await client.send_api_request(method, path)

            # Assert
            assert result == {"id": 1, "name": "Test Project"}
            assert client.token == "refreshed-token"
            assert client._auth_client.token == "refreshed-token"
            assert mock_request.call_count == 2
            mock_get_refreshed_token.assert_called_once()

    async def test_token_refresh_integration_failure(self, client: HTTPBaseClient) -> None:
        """Test token refresh flow when 401 occurs but refresh fails"""
        method = "GET"
        path = "projects"

        mock_401_response = MagicMock()
        mock_401_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=MagicMock(status_code=401)
        )

        with patch.object(
            client._client, "request", AsyncMock(return_value=mock_401_response)
        ) as mock_request, patch.object(
            client._auth_client, "get_refreshed_token", side_effect=ValueError("External token not available")
        ) as mock_get_refreshed_token:
            # Act & Assert
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await client.send_api_request(method, path)

            assert exc_info.value.response.status_code == 401
            assert client.token == "test-token"  # Token should remain unchanged
            assert client._auth_client.token == "test-token"
            mock_request.assert_called_once()
            mock_get_refreshed_token.assert_called_once()

    async def test_token_refresh_retry_also_fails(self, client: HTTPBaseClient) -> None:
        """Test when token refresh succeeds but retry request also fails with 401"""
        method = "GET"
        path = "projects"

        # Both requests fail with 401
        mock_401_response = MagicMock()
        mock_401_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=MagicMock(status_code=401)
        )

        with patch.object(
            client._client, "request", AsyncMock(return_value=mock_401_response)
        ) as mock_request, patch.object(
            client._auth_client, "get_refreshed_token", return_value="refreshed-token"
        ) as mock_get_refreshed_token:
            # Act & Assert
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await client.send_api_request(method, path)

            assert exc_info.value.response.status_code == 401
            assert client.token == "refreshed-token"  # Token was updated
            assert client._auth_client.token == "refreshed-token"
            assert mock_request.call_count == 2  # Original + retry
            mock_get_refreshed_token.assert_called_once()

    async def test_no_token_refresh_for_non_401_errors(self, client: HTTPBaseClient) -> None:
        """Test that token refresh is not attempted for non-401 errors"""
        method = "GET"
        path = "projects"

        mock_500_response = MagicMock()
        mock_500_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error", request=MagicMock(), response=MagicMock(status_code=500)
        )

        with patch.object(
            client._client, "request", AsyncMock(return_value=mock_500_response)
        ) as mock_request, patch.object(
            client._auth_client, "get_refreshed_token"
        ) as mock_get_refreshed_token:
            # Act & Assert
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await client.send_api_request(method, path)

            assert exc_info.value.response.status_code == 500
            assert client.token == "test-token"  # Token should remain unchanged
            mock_request.assert_called_once()
            mock_get_refreshed_token.assert_not_called()  # Refresh should not be attempted

    async def test_successful_request_no_refresh_needed(self, client: HTTPBaseClient) -> None:
        """Test that successful requests don't trigger token refresh"""
        method = "GET"
        path = "projects"

        mock_success_response = MagicMock()
        mock_success_response.json.return_value = {"id": 1, "name": "Test Project"}
        mock_success_response.raise_for_status = MagicMock()

        with patch.object(
            client._client, "request", AsyncMock(return_value=mock_success_response)
        ) as mock_request, patch.object(
            client._auth_client, "get_refreshed_token"
        ) as mock_get_refreshed_token:
            # Act
            result = await client.send_api_request(method, path)

            # Assert
            assert result == {"id": 1, "name": "Test Project"}
            assert client.token == "test-token"  # Token should remain unchanged
            mock_request.assert_called_once()
            mock_get_refreshed_token.assert_not_called()  # Refresh should not be needed
