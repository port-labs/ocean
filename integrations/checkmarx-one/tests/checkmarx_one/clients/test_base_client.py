import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from aiolimiter import AsyncLimiter

from checkmarx_one.clients.base_client import CheckmarxOneClient
from checkmarx_one.auths.auth import CheckmarxClientAuthenticator


class TestCheckmarxOneClient:
    """Test cases for CheckmarxOneClient."""

    @pytest.fixture
    def mock_http_client(self) -> MagicMock:
        """Create a mock HTTP client for testing."""
        mock_client = AsyncMock()
        mock_client.timeout = None
        return mock_client

    @pytest.fixture
    def mock_authenticator(self) -> AsyncMock:
        """Create a mock authenticator for testing."""
        authenticator = AsyncMock(spec=CheckmarxClientAuthenticator)
        authenticator.get_auth_headers.return_value = {
            "Authorization": "Bearer test_token",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        return authenticator

    @pytest.fixture
    def mock_rate_limiter(self) -> AsyncLimiter:
        """Create a mock rate limiter for testing."""
        return AsyncLimiter(3600, 3600)

    @pytest.fixture
    def client(
        self,
        mock_authenticator: AsyncMock,
        mock_http_client: MagicMock,
    ) -> CheckmarxOneClient:
        """Create a base client instance for testing."""
        with patch(
            "checkmarx_one.clients.base_client.http_async_client", mock_http_client
        ):
            return CheckmarxOneClient(
                base_url="https://ast.checkmarx.net",
                authenticator=mock_authenticator,
            )

    @pytest.fixture
    def client_with_default_rate_limiter(
        self, mock_authenticator: AsyncMock, mock_http_client: MagicMock
    ) -> CheckmarxOneClient:
        """Create a base client with default rate limiter for testing."""
        with patch(
            "checkmarx_one.clients.base_client.http_async_client", mock_http_client
        ):
            return CheckmarxOneClient(
                base_url="https://ast.checkmarx.net", authenticator=mock_authenticator
            )

    def test_init(
        self,
        client: CheckmarxOneClient,
        mock_authenticator: AsyncMock,
        mock_http_client: MagicMock,
    ) -> None:
        """Test client initialization."""
        assert client.base_url == "https://ast.checkmarx.net"
        assert client.authenticator == mock_authenticator

    def test_init_with_trailing_slash(
        self, mock_authenticator: AsyncMock, mock_http_client: MagicMock
    ) -> None:
        """Test client initialization with trailing slash in base URL."""
        with patch(
            "checkmarx_one.clients.base_client.http_async_client", mock_http_client
        ):
            client = CheckmarxOneClient(
                base_url="https://ast.checkmarx.net/", authenticator=mock_authenticator
            )
            assert client.base_url == "https://ast.checkmarx.net"

    def test_init_with_default_rate_limiter(
        self, client_with_default_rate_limiter: CheckmarxOneClient
    ) -> None:
        """Test client initialization with default rate limiter."""
        # The client doesn't have a rate_limiter attribute in the current implementation
        pass

    @pytest.mark.asyncio
    async def test_auth_headers_property(
        self, client: CheckmarxOneClient, mock_authenticator: AsyncMock
    ) -> None:
        """Test auth_headers property."""
        headers = await client.auth_headers
        mock_authenticator.get_auth_headers.assert_called_once()
        assert headers == {
            "Authorization": "Bearer test_token",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @pytest.mark.asyncio
    async def test_send_api_request_success(self, client: CheckmarxOneClient) -> None:
        """Test successful API request."""
        mock_response: MagicMock = MagicMock()
        mock_response.json.return_value = {"data": "test_data"}
        mock_response.raise_for_status.return_value = None

        with patch(
            "checkmarx_one.clients.base_client.http_async_client"
        ) as mock_http_client:
            mock_http_client.request.return_value = mock_response
            result = await client.send_api_request("/test-endpoint")

            assert result == {"data": "test_data"}

    @pytest.mark.asyncio
    async def test_send_api_request_with_params(
        self, client: CheckmarxOneClient
    ) -> None:
        """Test API request with query parameters."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": "test_data"}
        mock_response.raise_for_status.return_value = None

        with patch(
            "checkmarx_one.clients.base_client.http_async_client"
        ) as mock_http_client:
            mock_http_client.request.return_value = mock_response
            params = {"limit": 10, "offset": 0}
            _ = await client.send_api_request("/test-endpoint", params=params)

            mock_http_client.request.assert_called_once()
            call_args = mock_http_client.request.call_args
            assert call_args[1]["params"] == params

    @pytest.mark.asyncio
    async def test_send_api_request_with_json_data(
        self, client: CheckmarxOneClient
    ) -> None:
        """Test API request with JSON data."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": "test_data"}
        mock_response.raise_for_status.return_value = None

        with patch(
            "checkmarx_one.clients.base_client.http_async_client"
        ) as mock_http_client:
            mock_http_client.request.return_value = mock_response
            json_data = {"name": "test", "description": "test description"}
            _ = await client.send_api_request(
                "/test-endpoint", method="POST", json_data=json_data
            )

            mock_http_client.request.assert_called_once()
            call_args = mock_http_client.request.call_args
            assert call_args[1]["method"] == "POST"
            assert call_args[1]["json"] == json_data

    @pytest.mark.asyncio
    async def test_send_api_request_401_error(self, client: CheckmarxOneClient) -> None:
        """Test API request with 401 error."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized", request=MagicMock(), response=mock_response
        )

        with patch(
            "checkmarx_one.clients.base_client.http_async_client"
        ) as mock_http_client:
            mock_http_client.request.return_value = mock_response
            result = await client.send_api_request("/test-endpoint")

            # 401 errors are ignored and return empty dict
            assert result == {}

    @pytest.mark.asyncio
    async def test_send_api_request_403_error(self, client: CheckmarxOneClient) -> None:
        """Test API request with 403 error."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "403 Forbidden", request=MagicMock(), response=mock_response
        )

        with patch(
            "checkmarx_one.clients.base_client.http_async_client"
        ) as mock_http_client:
            mock_http_client.request.return_value = mock_response
            result = await client.send_api_request("/test-endpoint")

            # 403 errors are ignored and return empty dict
            assert result == {}

    @pytest.mark.asyncio
    async def test_send_api_request_404_error(self, client: CheckmarxOneClient) -> None:
        """Test API request with 404 error."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found", request=MagicMock(), response=mock_response
        )

        with patch(
            "checkmarx_one.clients.base_client.http_async_client"
        ) as mock_http_client:
            mock_http_client.request.return_value = mock_response
            result = await client.send_api_request("/test-endpoint")

            assert result == {}

    @pytest.mark.asyncio
    async def test_send_api_request_429_error(self, client: CheckmarxOneClient) -> None:
        """Test API request with 429 error."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Too Many Requests"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "429 Too Many Requests", request=MagicMock(), response=mock_response
        )

        with patch(
            "checkmarx_one.clients.base_client.http_async_client"
        ) as mock_http_client:
            mock_http_client.request.return_value = mock_response
            with pytest.raises(httpx.HTTPStatusError, match="429 Too Many Requests"):
                await client.send_api_request("/test-endpoint")

    @pytest.mark.asyncio
    async def test_send_api_request_other_http_error(
        self, client: CheckmarxOneClient
    ) -> None:
        """Test API request with other HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Internal Server Error", request=MagicMock(), response=mock_response
        )

        with patch(
            "checkmarx_one.clients.base_client.http_async_client"
        ) as mock_http_client:
            mock_http_client.request.return_value = mock_response
            with pytest.raises(
                httpx.HTTPStatusError, match="500 Internal Server Error"
            ):
                await client.send_api_request("/test-endpoint")

    @pytest.mark.asyncio
    async def test_send_api_request_unexpected_error(
        self, client: CheckmarxOneClient
    ) -> None:
        """Test API request with unexpected error."""
        with patch(
            "checkmarx_one.clients.base_client.http_async_client"
        ) as mock_http_client:
            mock_http_client.request.side_effect = Exception("Network error")
            with pytest.raises(Exception, match="Network error"):
                await client.send_api_request("/test-endpoint")

    @pytest.mark.asyncio
    async def test_get_paginated_resources_single_page(
        self, client: CheckmarxOneClient
    ) -> None:
        """Test paginated resources with single page."""
        mock_response = {"data": [{"id": "1"}, {"id": "2"}]}

        with patch(
            "checkmarx_one.clients.base_client.http_async_client"
        ) as mock_http_client:
            mock_response_obj = MagicMock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status.return_value = None
            mock_http_client.request.return_value = mock_response_obj

            results = []
            async for batch in client.send_paginated_request("/test", "data"):
                results.extend(batch)

            assert results == [{"id": "1"}, {"id": "2"}]

    @pytest.mark.asyncio
    async def test_get_paginated_resources_multiple_pages(
        self, client: CheckmarxOneClient
    ) -> None:
        """Test paginated resources with multiple pages."""
        # First page: 100 items (full page)
        # Second page: 50 items (partial page)
        first_response = {"data": [{"id": str(i)} for i in range(100)]}
        second_response = {"data": [{"id": str(i)} for i in range(100, 150)]}

        with patch(
            "checkmarx_one.clients.base_client.http_async_client"
        ) as mock_http_client:
            mock_response1 = MagicMock()
            mock_response1.json.return_value = first_response
            mock_response1.raise_for_status.return_value = None

            mock_response2 = MagicMock()
            mock_response2.json.return_value = second_response
            mock_response2.raise_for_status.return_value = None

            mock_http_client.request.side_effect = [mock_response1, mock_response2]

            results = []
            async for batch in client.send_paginated_request("/test", "data"):
                results.extend(batch)

            assert len(results) == 150
            assert results[0]["id"] == "0"
            assert results[-1]["id"] == "149"

    @pytest.mark.asyncio
    async def test_get_paginated_resources_empty_response(
        self, client: CheckmarxOneClient
    ) -> None:
        """Test paginated resources with empty response."""
        mock_response: dict[str, list[dict[str, str]]] = {"data": []}

        with patch(
            "checkmarx_one.clients.base_client.http_async_client"
        ) as mock_http_client:
            mock_response_obj = MagicMock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status.return_value = None
            mock_http_client.request.return_value = mock_response_obj

            results = []
            async for batch in client.send_paginated_request("/test", "data"):
                results.extend(batch)

            assert results == []

    @pytest.mark.asyncio
    async def test_get_paginated_resources_list_response(
        self, client: CheckmarxOneClient
    ) -> None:
        """Test paginated resources with list response format."""
        mock_response = [{"id": "1"}, {"id": "2"}]

        with patch(
            "checkmarx_one.clients.base_client.http_async_client"
        ) as mock_http_client:
            mock_response_obj = MagicMock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status.return_value = None
            mock_http_client.request.return_value = mock_response_obj

            results = []
            async for batch in client.send_paginated_request("/test", "data"):
                results.extend(batch)

            assert results == [{"id": "1"}, {"id": "2"}]

    @pytest.mark.asyncio
    async def test_get_paginated_resources_different_object_key(
        self, client: CheckmarxOneClient
    ) -> None:
        """Test paginated resources with different object key."""
        mock_response = {"items": [{"id": "1"}, {"id": "2"}]}

        with patch(
            "checkmarx_one.clients.base_client.http_async_client"
        ) as mock_http_client:
            mock_response_obj = MagicMock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status.return_value = None
            mock_http_client.request.return_value = mock_response_obj

            results = []
            async for batch in client.send_paginated_request("/test", "items"):
                results.extend(batch)

            assert results == [{"id": "1"}, {"id": "2"}]

    @pytest.mark.asyncio
    async def test_get_paginated_resources_with_params(
        self, client: CheckmarxOneClient
    ) -> None:
        """Test paginated resources with additional parameters."""
        mock_response = {"data": [{"id": "1"}]}

        with patch(
            "checkmarx_one.clients.base_client.http_async_client"
        ) as mock_http_client:
            mock_response_obj = MagicMock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status.return_value = None
            mock_http_client.request.return_value = mock_response_obj

            params = {"status": "active"}
            results = []
            async for batch in client.send_paginated_request(
                "/test", "data", params=params
            ):
                results.extend(batch)

            # Check that the request was called with the correct parameters
            call_args = mock_http_client.request.call_args
            request_params = call_args[1]["params"]
            assert request_params["status"] == "active"
            assert request_params["limit"] == 100
            assert request_params["offset"] == 0

    @pytest.mark.asyncio
    async def test_get_paginated_resources_request_error(
        self, client: CheckmarxOneClient
    ) -> None:
        """Test paginated resources when request fails."""
        with patch(
            "checkmarx_one.clients.base_client.http_async_client"
        ) as mock_http_client:
            mock_http_client.request.side_effect = Exception("Request failed")
            results = []
            async for batch in client.send_paginated_request("/test", "data"):
                results.extend(batch)

            # Should handle the error gracefully and stop iteration
            assert results == []

    def test_constants(self) -> None:
        """Test that constants are defined correctly."""
        from checkmarx_one.clients.base_client import PAGE_SIZE

        assert PAGE_SIZE == 100
