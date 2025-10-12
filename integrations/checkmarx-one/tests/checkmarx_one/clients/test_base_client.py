import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from checkmarx_one.clients.client import CheckmarxOneClient
from checkmarx_one.auths.token_auth import TokenAuthenticator


class TestCheckmarxOneClient:
    """Test cases for CheckmarxOneClient."""

    @pytest.fixture
    def mock_authenticator(self) -> AsyncMock:
        """Create a mock authenticator for testing."""
        authenticator = AsyncMock(spec=TokenAuthenticator)
        authenticator.get_auth_headers.return_value = {
            "Authorization": "Bearer test_token",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        return authenticator

    @pytest.fixture
    def client(self, mock_authenticator: AsyncMock) -> CheckmarxOneClient:
        """Create a CheckmarxOneClient instance for testing."""
        return CheckmarxOneClient(
            base_url="https://ast.checkmarx.net",
            authenticator=mock_authenticator,
        )

    def test_init(self, client: CheckmarxOneClient) -> None:
        """Test client initialization."""
        assert client.base_url == "https://ast.checkmarx.net"

    def test_init_with_trailing_slash(self, mock_authenticator: AsyncMock) -> None:
        """Test client initialization with trailing slash in base URL."""
        with patch("checkmarx_one.clients.client.http_async_client", AsyncMock()):
            client = CheckmarxOneClient(
                base_url="https://ast.checkmarx.net/",
                authenticator=mock_authenticator,
            )
            assert client.base_url == "https://ast.checkmarx.net"

    def test_init_with_default_rate_limiter(
        self, mock_authenticator: AsyncMock
    ) -> None:
        """Test client initialization with default rate limiter."""
        with patch("checkmarx_one.clients.client.http_async_client", AsyncMock()):
            client = CheckmarxOneClient(
                base_url="https://ast.checkmarx.net",
                authenticator=mock_authenticator,
            )
            assert client.base_url == "https://ast.checkmarx.net"

    @pytest.mark.asyncio
    async def test_auth_headers_property(
        self, client: CheckmarxOneClient, mock_authenticator: AsyncMock
    ) -> None:
        """Test auth_headers property."""
        headers = await client.auth_headers
        assert headers == {
            "Authorization": "Bearer test_token",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        mock_authenticator.get_auth_headers.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_api_request_success(self, client: CheckmarxOneClient) -> None:
        """Test successful API request."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": "test_data"}
        mock_response.raise_for_status.return_value = None

        with patch("checkmarx_one.clients.client.http_async_client") as mock_client:
            mock_client.request = AsyncMock(return_value=mock_response)
            result = await client.send_api_request("/test-endpoint")

            assert result == {"data": "test_data"}
            mock_client.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_api_request_with_params(
        self, client: CheckmarxOneClient
    ) -> None:
        """Test API request with parameters."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": "test_data"}
        mock_response.raise_for_status.return_value = None

        params = {"param1": "value1", "param2": "value2"}

        with patch("checkmarx_one.clients.client.http_async_client") as mock_client:
            mock_client.request = AsyncMock(return_value=mock_response)
            _ = await client.send_api_request("/test-endpoint", params=params)

            mock_client.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_api_request_with_json_data(
        self, client: CheckmarxOneClient
    ) -> None:
        """Test API request with JSON data."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": "test_data"}
        mock_response.raise_for_status.return_value = None

        json_data = {"key": "value"}

        with patch("checkmarx_one.clients.client.http_async_client") as mock_client:
            mock_client.request = AsyncMock(return_value=mock_response)
            _ = await client.send_api_request(
                "/test-endpoint", method="POST", json_data=json_data
            )

            mock_client.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_api_request_401_error(self, client: CheckmarxOneClient) -> None:
        """Test API request with 401 error."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized", request=MagicMock(), response=mock_response
        )

        with patch("checkmarx_one.clients.client.http_async_client") as mock_client:
            mock_client.request = AsyncMock(return_value=mock_response)
            result = await client.send_api_request("/test-endpoint")

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

        with patch("checkmarx_one.clients.client.http_async_client") as mock_client:
            mock_client.request = AsyncMock(return_value=mock_response)
            result = await client.send_api_request("/test-endpoint")

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

        with patch("checkmarx_one.clients.client.http_async_client") as mock_client:
            mock_client.request = AsyncMock(return_value=mock_response)
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

        with patch("checkmarx_one.clients.client.http_async_client") as mock_client:
            mock_client.request = AsyncMock(return_value=mock_response)
            with pytest.raises(httpx.HTTPStatusError):
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

        with patch("checkmarx_one.clients.client.http_async_client") as mock_client:
            mock_client.request = AsyncMock(return_value=mock_response)
            with pytest.raises(httpx.HTTPStatusError):
                await client.send_api_request("/test-endpoint")

    @pytest.mark.asyncio
    async def test_send_api_request_unexpected_error(
        self, client: CheckmarxOneClient
    ) -> None:
        """Test API request with unexpected error."""
        with patch("checkmarx_one.clients.client.http_async_client") as mock_client:
            mock_client.request = AsyncMock(side_effect=Exception("Unexpected error"))
            with pytest.raises(Exception):
                await client.send_api_request("/test-endpoint")

    @pytest.mark.asyncio
    async def test_get_paginated_resources_single_page(
        self, client: CheckmarxOneClient
    ) -> None:
        """Test getting paginated resources with single page."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": [{"id": 1}, {"id": 2}]}
        mock_response.raise_for_status.return_value = None

        with patch("checkmarx_one.clients.client.http_async_client") as mock_client:
            mock_client.request = AsyncMock(return_value=mock_response)
            results = []
            async for batch in client.send_paginated_request("/test", "data"):
                results.append(batch)

            assert len(results) == 1
            assert results[0] == [{"id": 1}, {"id": 2}]

    @pytest.mark.asyncio
    async def test_get_paginated_resources_multiple_pages(
        self, client: CheckmarxOneClient
    ) -> None:
        """Test getting paginated resources with multiple pages."""
        # First page: full page (100 items)
        mock_response1 = MagicMock()
        mock_response1.json.return_value = {"data": [{"id": i} for i in range(100)]}
        mock_response1.raise_for_status.return_value = None

        # Second page: partial page (50 items)
        mock_response2 = MagicMock()
        mock_response2.json.return_value = {
            "data": [{"id": i} for i in range(100, 150)]
        }
        mock_response2.raise_for_status.return_value = None

        with patch("checkmarx_one.clients.client.http_async_client") as mock_client:
            # Mock the request method to return different responses on subsequent calls
            mock_client.request = AsyncMock(
                side_effect=[mock_response1, mock_response2]
            )
            results = []
            async for batch in client.send_paginated_request("/test", "data"):
                results.append(batch)

            assert len(results) == 2
            assert len(results[0]) == 100
            assert len(results[1]) == 50
            assert results[0][0]["id"] == 0
            assert results[0][-1]["id"] == 99
            assert results[1][0]["id"] == 100
            assert results[1][-1]["id"] == 149

    @pytest.mark.asyncio
    async def test_get_paginated_resources_empty_response(
        self, client: CheckmarxOneClient
    ) -> None:
        """Test getting paginated resources with empty response."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": []}
        mock_response.raise_for_status.return_value = None

        with patch("checkmarx_one.clients.client.http_async_client") as mock_client:
            mock_client.request = AsyncMock(return_value=mock_response)
            results = []
            async for batch in client.send_paginated_request("/test", "data"):
                results.append(batch)

            assert len(results) == 0

    @pytest.mark.asyncio
    async def test_get_paginated_resources_list_response(
        self, client: CheckmarxOneClient
    ) -> None:
        """Test getting paginated resources with list response."""
        mock_response = MagicMock()
        mock_response.json.return_value = [{"id": 1}, {"id": 2}]
        mock_response.raise_for_status.return_value = None

        with patch("checkmarx_one.clients.client.http_async_client") as mock_client:
            mock_client.request = AsyncMock(return_value=mock_response)
            results = []
            async for batch in client.send_paginated_request("/test", "data"):
                results.append(batch)

            assert len(results) == 1
            assert results[0] == [{"id": 1}, {"id": 2}]

    @pytest.mark.asyncio
    async def test_get_paginated_resources_different_object_key(
        self, client: CheckmarxOneClient
    ) -> None:
        """Test getting paginated resources with different object key."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"items": [{"id": 1}, {"id": 2}]}
        mock_response.raise_for_status.return_value = None

        with patch("checkmarx_one.clients.client.http_async_client") as mock_client:
            mock_client.request = AsyncMock(return_value=mock_response)
            results = []
            async for batch in client.send_paginated_request("/test", "items"):
                results.append(batch)

            assert len(results) == 1
            assert results[0] == [{"id": 1}, {"id": 2}]

    @pytest.mark.asyncio
    async def test_get_paginated_resources_with_params(
        self, client: CheckmarxOneClient
    ) -> None:
        """Test getting paginated resources with parameters."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": [{"id": 1}]}
        mock_response.raise_for_status.return_value = None

        params = {"param1": "value1"}

        with patch("checkmarx_one.clients.client.http_async_client") as mock_client:
            mock_client.request = AsyncMock(return_value=mock_response)
            results = []
            async for batch in client.send_paginated_request("/test", "data", params):
                results.append(batch)

            assert len(results) == 1
            assert results[0] == [{"id": 1}]

    @pytest.mark.asyncio
    async def test_get_paginated_resources_request_error(
        self, client: CheckmarxOneClient
    ) -> None:
        """Test getting paginated resources with request error."""
        with patch("checkmarx_one.clients.client.http_async_client") as mock_client:
            mock_client.request = AsyncMock(side_effect=Exception("Request failed"))

            with pytest.raises(Exception, match="Request failed"):
                results = []
                async for batch in client.send_paginated_request("/test", "data"):
                    results.append(batch)

    def test_constants(self) -> None:
        """Test that constants are properly defined."""
        from checkmarx_one.clients.client import PAGE_SIZE

        assert PAGE_SIZE == 100

    @pytest.mark.asyncio
    async def test_send_paginated_request_offset_based_single_page(
        self, client: CheckmarxOneClient
    ) -> None:
        """Test getting offset-based paginated resources with single page."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"environments": [{"id": 1}, {"id": 2}]}
        mock_response.raise_for_status.return_value = None

        with patch("checkmarx_one.clients.client.http_async_client") as mock_client:
            mock_client.request = AsyncMock(return_value=mock_response)
            results = []
            async for batch in client.send_paginated_request_offset_based(
                "/dast/scans/environments", "environments"
            ):
                results.append(batch)

            # Should have one batch
            assert len(results) == 1
            assert results[0] == [{"id": 1}, {"id": 2}]

    @pytest.mark.asyncio
    async def test_send_paginated_request_offset_based_multiple_pages(
        self, client: CheckmarxOneClient
    ) -> None:
        """Test getting offset-based paginated resources with multiple pages."""
        # First page: full page (100 items)
        mock_response1 = MagicMock()
        mock_response1.json.return_value = {"scans": [{"id": i} for i in range(100)]}
        mock_response1.raise_for_status.return_value = None

        # Second page: full page (100 items)
        mock_response2 = MagicMock()
        mock_response2.json.return_value = {
            "scans": [{"id": i} for i in range(100, 200)]
        }
        mock_response2.raise_for_status.return_value = None

        # Third page: partial page (less than page size, indicates last page)
        mock_response3 = MagicMock()
        mock_response3.json.return_value = {"scans": [{"id": i} for i in range(200, 250)]}
        mock_response3.raise_for_status.return_value = None

        with patch("checkmarx_one.clients.client.http_async_client") as mock_client:
            mock_client.request = AsyncMock(
                side_effect=[mock_response1, mock_response2, mock_response3]
            )
            results = []
            async for batch in client.send_paginated_request_offset_based(
                "/dast/scans/scans", "scans"
            ):
                results.append(batch)

            assert len(results) == 3
            assert len(results[0]) == 100
            assert len(results[1]) == 100
            assert len(results[2]) == 50  # Less than PAGE_SIZE, so pagination stops

    @pytest.mark.asyncio
    async def test_send_paginated_request_offset_based_empty_response(
        self, client: CheckmarxOneClient
    ) -> None:
        """Test getting offset-based paginated resources with empty response."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"environments": []}
        mock_response.raise_for_status.return_value = None

        with patch("checkmarx_one.clients.client.http_async_client") as mock_client:
            mock_client.request = AsyncMock(return_value=mock_response)
            results = []
            async for batch in client.send_paginated_request_offset_based(
                "/dast/scans/environments", "environments"
            ):
                results.append(batch)

            assert len(results) == 0

    @pytest.mark.asyncio
    async def test_send_paginated_request_offset_based_with_params(
        self, client: CheckmarxOneClient
    ) -> None:
        """Test getting offset-based paginated resources with parameters."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"scans": [{"id": 1}]}
        mock_response.raise_for_status.return_value = None

        params = {"environmentId": "env-1", "sort": "updatetime:desc"}

        with patch("checkmarx_one.clients.client.http_async_client") as mock_client:
            mock_client.request = AsyncMock(return_value=mock_response)
            results = []
            async for batch in client.send_paginated_request_offset_based(
                "/dast/scans/scans", "scans", params
            ):
                results.append(batch)

            assert len(results) == 1
            assert results[0] == [{"id": 1}]

            # Verify that the request was called with correct pagination parameters
            call_args = mock_client.request.call_args
            assert call_args is not None
            actual_params = call_args.kwargs.get("params", {})
            assert actual_params.get("from") == 0
            assert actual_params.get("to") == 100  # PAGE_SIZE is 100
            assert actual_params.get("environmentId") == "env-1"
            assert actual_params.get("sort") == "updatetime:desc"

    @pytest.mark.asyncio
    async def test_send_paginated_request_offset_based_pagination_parameters(
        self, client: CheckmarxOneClient
    ) -> None:
        """Test that offset-based pagination uses correct parameters."""
        # First page
        mock_response1 = MagicMock()
        mock_response1.json.return_value = {"scans": [{"id": i} for i in range(100)]}
        mock_response1.raise_for_status.return_value = None

        # Second page
        mock_response2 = MagicMock()
        mock_response2.json.return_value = {"scans": [{"id": i} for i in range(100, 150)]}
        mock_response2.raise_for_status.return_value = None

        with patch("checkmarx_one.clients.client.http_async_client") as mock_client:
            mock_client.request = AsyncMock(
                side_effect=[mock_response1, mock_response2]
            )
            results = []
            async for batch in client.send_paginated_request_offset_based(
                "/dast/scans/scans", "scans"
            ):
                results.append(batch)

            # Verify pagination parameters for both requests
            calls = mock_client.request.call_args_list
            assert len(calls) == 2

            # First call: from=0, to=100
            first_params = calls[0].kwargs.get("params", {})
            assert first_params.get("from") == 0
            assert first_params.get("to") == 100

            # Second call: from=100, to=200
            second_params = calls[1].kwargs.get("params", {})
            assert second_params.get("from") == 100
            assert second_params.get("to") == 200

    @pytest.mark.asyncio
    async def test_send_paginated_request_page_based_single_page(
        self, client: CheckmarxOneClient
    ) -> None:
        """Test getting page-based paginated resources with single page."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [{"id": 1}, {"id": 2}],
            "pages_number": 1,
        }
        mock_response.raise_for_status.return_value = None

        with patch("checkmarx_one.clients.client.http_async_client") as mock_client:
            mock_client.request = AsyncMock(return_value=mock_response)
            results = []
            async for batch in client.send_paginated_request_page_based(
                "/dast/mfe-results/results/scan-1", "results"
            ):
                results.append(batch)

            assert len(results) == 1
            assert results[0] == [{"id": 1}, {"id": 2}]

    @pytest.mark.asyncio
    async def test_send_paginated_request_page_based_multiple_pages(
        self, client: CheckmarxOneClient
    ) -> None:
        """Test getting page-based paginated resources with multiple pages."""
        # First page
        mock_response1 = MagicMock()
        mock_response1.json.return_value = {
            "results": [{"id": i} for i in range(100)],
            "pages_number": 3,
        }
        mock_response1.raise_for_status.return_value = None

        # Second page
        mock_response2 = MagicMock()
        mock_response2.json.return_value = {
            "results": [{"id": i} for i in range(100, 200)],
            "pages_number": 3,
        }
        mock_response2.raise_for_status.return_value = None

        # Third page
        mock_response3 = MagicMock()
        mock_response3.json.return_value = {
            "results": [{"id": i} for i in range(200, 250)],
            "pages_number": 3,
        }
        mock_response3.raise_for_status.return_value = None

        with patch("checkmarx_one.clients.client.http_async_client") as mock_client:
            mock_client.request = AsyncMock(
                side_effect=[mock_response1, mock_response2, mock_response3]
            )
            results = []
            async for batch in client.send_paginated_request_page_based(
                "/dast/mfe-results/results/scan-1", "results"
            ):
                results.append(batch)

            assert len(results) == 3
            assert len(results[0]) == 100
            assert len(results[1]) == 100
            assert len(results[2]) == 50

    @pytest.mark.asyncio
    async def test_send_paginated_request_page_based_empty_response(
        self, client: CheckmarxOneClient
    ) -> None:
        """Test getting page-based paginated resources with empty response."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": [], "pages_number": 0}
        mock_response.raise_for_status.return_value = None

        with patch("checkmarx_one.clients.client.http_async_client") as mock_client:
            mock_client.request = AsyncMock(return_value=mock_response)
            results = []
            async for batch in client.send_paginated_request_page_based(
                "/dast/mfe-results/results/scan-1", "results"
            ):
                results.append(batch)

            assert len(results) == 0

    @pytest.mark.asyncio
    async def test_send_paginated_request_page_based_with_params(
        self, client: CheckmarxOneClient
    ) -> None:
        """Test getting page-based paginated resources with parameters."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [{"id": 1}],
            "pages_number": 1,
        }
        mock_response.raise_for_status.return_value = None

        params = {"severity": ["CRITICAL"], "status": ["NEW"]}

        with patch("checkmarx_one.clients.client.http_async_client") as mock_client:
            mock_client.request = AsyncMock(return_value=mock_response)
            results = []
            async for batch in client.send_paginated_request_page_based(
                "/dast/mfe-results/results/scan-1", "results", params
            ):
                results.append(batch)

            assert len(results) == 1
            assert results[0] == [{"id": 1}]

            # Verify that the request was called with correct pagination parameters
            call_args = mock_client.request.call_args
            assert call_args is not None
            actual_params = call_args.kwargs.get("params", {})
            assert actual_params.get("page") == 1
            assert actual_params.get("per_page") == 100  # PAGE_SIZE is 100
            assert actual_params.get("severity") == ["CRITICAL"]
            assert actual_params.get("status") == ["NEW"]

    @pytest.mark.asyncio
    async def test_send_paginated_request_page_based_pagination_parameters(
        self, client: CheckmarxOneClient
    ) -> None:
        """Test that page-based pagination uses correct parameters."""
        # First page
        mock_response1 = MagicMock()
        mock_response1.json.return_value = {
            "results": [{"id": i} for i in range(100)],
            "pages_number": 2,
        }
        mock_response1.raise_for_status.return_value = None

        # Second page
        mock_response2 = MagicMock()
        mock_response2.json.return_value = {
            "results": [{"id": i} for i in range(100, 150)],
            "pages_number": 2,
        }
        mock_response2.raise_for_status.return_value = None

        with patch("checkmarx_one.clients.client.http_async_client") as mock_client:
            mock_client.request = AsyncMock(
                side_effect=[mock_response1, mock_response2]
            )
            results = []
            async for batch in client.send_paginated_request_page_based(
                "/dast/mfe-results/results/scan-1", "results"
            ):
                results.append(batch)

            # Verify pagination parameters for both requests
            calls = mock_client.request.call_args_list
            assert len(calls) == 2

            # First call: page=1, per_page=100
            first_params = calls[0].kwargs.get("params", {})
            assert first_params.get("page") == 1
            assert first_params.get("per_page") == 100

            # Second call: page=2, per_page=100
            second_params = calls[1].kwargs.get("params", {})
            assert second_params.get("page") == 2
            assert second_params.get("per_page") == 100

    @pytest.mark.asyncio
    async def test_send_paginated_request_api_sec_single_page(
        self, client: CheckmarxOneClient
    ) -> None:
        """Test getting API security paginated resources with single page."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "entries": [{"risk_id": "1"}, {"risk_id": "2"}],
            "has_next": False,
            "next_page_number": 1,
        }
        mock_response.raise_for_status.return_value = None

        with patch("checkmarx_one.clients.client.http_async_client") as mock_client:
            mock_client.request = AsyncMock(return_value=mock_response)
            results = []
            async for batch in client.send_paginated_request_api_sec(
                "/test", "entries"
            ):
                results.append(batch)

            assert len(results) == 1
            assert results[0] == [{"risk_id": "1"}, {"risk_id": "2"}]

    @pytest.mark.asyncio
    async def test_send_paginated_request_api_sec_multiple_pages(
        self, client: CheckmarxOneClient
    ) -> None:
        """Test getting API security paginated resources with multiple pages."""
        # First page: full page with has_next=True
        mock_response1 = MagicMock()
        mock_response1.json.return_value = {
            "entries": [{"risk_id": str(i)} for i in range(100)],
            "has_next": True,
            "next_page_number": 2,
        }
        mock_response1.raise_for_status.return_value = None

        # Second page: partial page with has_next=False
        mock_response2 = MagicMock()
        mock_response2.json.return_value = {
            "entries": [{"risk_id": str(i)} for i in range(100, 150)],
            "has_next": False,
            "next_page_number": 3,
        }
        mock_response2.raise_for_status.return_value = None

        with patch("checkmarx_one.clients.client.http_async_client") as mock_client:
            mock_client.request = AsyncMock(
                side_effect=[mock_response1, mock_response2]
            )
            results = []
            async for batch in client.send_paginated_request_api_sec(
                "/test", "entries"
            ):
                results.append(batch)

            assert len(results) == 2
            assert len(results[0]) == 100
            assert len(results[1]) == 50
            assert results[0][0]["risk_id"] == "0"
            assert results[0][-1]["risk_id"] == "99"
            assert results[1][0]["risk_id"] == "100"
            assert results[1][-1]["risk_id"] == "149"

    @pytest.mark.asyncio
    async def test_send_paginated_request_api_sec_empty_response(
        self, client: CheckmarxOneClient
    ) -> None:
        """Test getting API security paginated resources with empty response."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "entries": [],
            "has_next": False,
            "next_page_number": 1,
        }
        mock_response.raise_for_status.return_value = None

        with patch("checkmarx_one.clients.client.http_async_client") as mock_client:
            mock_client.request = AsyncMock(return_value=mock_response)
            results = []
            async for batch in client.send_paginated_request_api_sec(
                "/test", "entries"
            ):
                results.append(batch)

            assert len(results) == 0

    @pytest.mark.asyncio
    async def test_send_paginated_request_api_sec_with_params(
        self, client: CheckmarxOneClient
    ) -> None:
        """Test getting API security paginated resources with parameters."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "entries": [{"risk_id": "1"}],
            "has_next": False,
            "next_page_number": 1,
        }
        mock_response.raise_for_status.return_value = None

        params = {"filtering": "test", "searching": "low"}

        with patch("checkmarx_one.clients.client.http_async_client") as mock_client:
            mock_client.request = AsyncMock(return_value=mock_response)
            results = []
            async for batch in client.send_paginated_request_api_sec(
                "/test", "entries", params
            ):
                results.append(batch)

            assert len(results) == 1
            assert results[0] == [{"risk_id": "1"}]

    @pytest.mark.asyncio
    async def test_send_paginated_request_api_sec_with_object_key_fallback(
        self, client: CheckmarxOneClient
    ) -> None:
        """Test getting API security paginated resources with object key fallback."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [{"risk_id": "1"}, {"risk_id": "2"}],
            "has_next": False,
            "next_page_number": 1,
        }
        mock_response.raise_for_status.return_value = None

        with patch("checkmarx_one.clients.client.http_async_client") as mock_client:
            mock_client.request = AsyncMock(return_value=mock_response)
            results = []
            async for batch in client.send_paginated_request_api_sec("/test", "data"):
                results.append(batch)

            assert len(results) == 1
            assert results[0] == [{"risk_id": "1"}, {"risk_id": "2"}]

    @pytest.mark.asyncio
    async def test_send_paginated_request_api_sec_missing_pagination_fields(
        self, client: CheckmarxOneClient
    ) -> None:
        """Test getting API security paginated resources with missing pagination fields."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "entries": [{"risk_id": "1"}],
            # Missing has_next and next_page_number fields
        }
        mock_response.raise_for_status.return_value = None

        with patch("checkmarx_one.clients.client.http_async_client") as mock_client:
            mock_client.request = AsyncMock(return_value=mock_response)

            with pytest.raises(KeyError, match="next_page_number"):
                results = []
                async for batch in client.send_paginated_request_api_sec(
                    "/test", "entries"
                ):
                    results.append(batch)

    @pytest.mark.asyncio
    async def test_send_paginated_request_api_sec_request_error(
        self, client: CheckmarxOneClient
    ) -> None:
        """Test getting API security paginated resources with request error."""
        with patch("checkmarx_one.clients.client.http_async_client") as mock_client:
            mock_client.request = AsyncMock(side_effect=Exception("Request failed"))

            with pytest.raises(Exception, match="Request failed"):
                results = []
                async for batch in client.send_paginated_request_api_sec(
                    "/test", "entries"
                ):
                    results.append(batch)

    @pytest.mark.asyncio
    async def test_send_paginated_request_api_sec_pagination_parameters(
        self, client: CheckmarxOneClient
    ) -> None:
        """Test that API security pagination uses correct parameters."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "entries": [{"risk_id": "1"}],
            "has_next": False,
            "next_page_number": 1,
        }
        mock_response.raise_for_status.return_value = None

        params = {"filtering": "test"}

        with patch("checkmarx_one.clients.client.http_async_client") as mock_client:
            mock_client.request = AsyncMock(return_value=mock_response)
            results = []
            async for batch in client.send_paginated_request_api_sec(
                "/test", "entries", params
            ):
                results.append(batch)

            # Verify that the request was called with correct pagination parameters
            call_args = mock_client.request.call_args
            assert call_args is not None

            # Check that the params dictionary contains the expected pagination parameters
            actual_params = call_args.kwargs.get("params", {})
            assert actual_params.get("page") == 1
            assert actual_params.get("per_page") == 100  # PAGE_SIZE is 100
            assert actual_params.get("filtering") == "test"
