import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from client import OpenCostClient
from utils import IgnoredError
from port_ocean.context.event import event_context
from port_ocean.context.resource import resource_context
from integration import CloudCostResourceConfig, OpencostResourceConfig


@pytest.mark.asyncio
class TestOpenCostClient:
    async def test_send_api_request_success(self) -> None:
        """Test successful API request."""
        # Mock response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"id": 1, "cost": 100}]}

        # Mock HTTP client
        mock_http_client = AsyncMock()
        mock_http_client.request.return_value = mock_response

        # Create client with patched HTTP client

        with patch("client.http_async_client", new=mock_http_client):
            client = OpenCostClient(app_host="http://localhost:9003")

            # Test the method
            response = await client.send_api_request(
                url="http://localhost:9003/allocation/compute", params={"window": "7d"}
            )

            assert response == {"data": [{"id": 1, "cost": 100}]}

    async def test_send_api_request_with_params(self) -> None:
        """Test API request with query parameters."""
        # Mock response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"sets": []}}

        # Mock HTTP client
        mock_http_client = AsyncMock()
        mock_http_client.request.return_value = mock_response

        # Create client with patched HTTP client
        with patch("client.http_async_client", new=mock_http_client):
            client = OpenCostClient(app_host="http://localhost:9003")

            # Test parameters
            params = {"window": "7d", "aggregate": "namespace"}
            url = "http://localhost:9003/cloudCost"

            await client.send_api_request(url=url, params=params)

            # Verify the request was made with the correct arguments
            mock_http_client.request.assert_called_once_with(
                method="GET",
                url=url,
                params=params,
            )

    async def test_send_api_request_404_error_ignored(self) -> None:
        """Test 404 Not Found error handling - should be ignored by default."""
        # Mock 404 error response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found", request=MagicMock(), response=mock_response
        )

        # Mock HTTP client
        mock_http_client = AsyncMock()
        mock_http_client.request.return_value = mock_response

        # Create client with patched HTTP client
        with patch("client.http_async_client", new=mock_http_client):
            client = OpenCostClient(app_host="http://localhost:9003")

            # Should return empty dict for 404 (ignored error)
            response = await client.send_api_request(
                "http://localhost:9003/nonexistent-endpoint"
            )
            assert response == {}

    async def test_send_api_request_403_error_ignored(self) -> None:
        """Test 403 Forbidden error handling - should be ignored by default."""
        # Mock 403 error response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 403
        mock_response.text = "Forbidden"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "403 Forbidden", request=MagicMock(), response=mock_response
        )

        # Mock HTTP client
        mock_http_client = AsyncMock()
        mock_http_client.request.return_value = mock_response

        # Create client with patched HTTP client
        with patch("client.http_async_client", new=mock_http_client):
            client = OpenCostClient(app_host="http://localhost:9003")

            # Should return empty dict for 403 (ignored error)
            response = await client.send_api_request(
                "http://localhost:9003/forbidden-endpoint"
            )
            assert response == {}

    async def test_send_api_request_401_error_ignored(self) -> None:
        """Test 401 Unauthorized error handling - should be ignored by default."""
        # Mock 401 error response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized", request=MagicMock(), response=mock_response
        )

        # Mock HTTP client
        mock_http_client = AsyncMock()
        mock_http_client.request.return_value = mock_response

        # Create client with patched HTTP client
        with patch("client.http_async_client", new=mock_http_client):
            client = OpenCostClient(app_host="http://localhost:9003")

            # Should return empty dict for 401 (ignored error)
            response = await client.send_api_request(
                "http://localhost:9003/unauthorized-endpoint"
            )
            assert response == {}

    async def test_send_api_request_500_error_raised(self) -> None:
        """Test 500 Internal Server Error - should NOT be ignored by default."""
        # Mock 500 error response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        http_error = httpx.HTTPStatusError(
            "500 Internal Server Error", request=MagicMock(), response=mock_response
        )
        mock_response.raise_for_status.side_effect = http_error

        # Mock HTTP client
        mock_http_client = AsyncMock()
        mock_http_client.request.return_value = mock_response

        # Create client with patched HTTP client
        with patch("client.http_async_client", new=mock_http_client):
            client = OpenCostClient(app_host="http://localhost:9003")

            # Should raise the error for 500 (not ignored)
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await client.send_api_request(
                    "http://localhost:9003/allocation/compute"
                )

            assert exc_info.value.response.status_code == 500

    async def test_send_api_request_with_custom_ignored_errors(self) -> None:
        """Test with custom ignored errors."""
        # Mock 500 error response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Internal Server Error", request=MagicMock(), response=mock_response
        )

        # Mock HTTP client
        mock_http_client = AsyncMock()
        mock_http_client.request.return_value = mock_response

        # Create client with patched HTTP client
        with patch("client.http_async_client", new=mock_http_client):
            client = OpenCostClient(app_host="http://localhost:9003")

            # Custom ignored errors
            custom_ignored_errors = [
                IgnoredError(status=500, message="Custom 500 error")
            ]

            # Should return empty dict for 500 (custom ignored error)
            response = await client.send_api_request(
                "http://localhost:9003/allocation/compute",
                ignored_errors=custom_ignored_errors,
            )
            assert response == {}

    async def test_send_api_request_network_error_raised(self) -> None:
        """Test network-level HTTP error."""
        # Create a network error
        network_error = httpx.ConnectError("Connection failed")

        # Mock HTTP client
        mock_http_client = AsyncMock()
        mock_http_client.request.side_effect = network_error

        # Create client with patched HTTP client
        with patch("client.http_async_client", new=mock_http_client):
            client = OpenCostClient(app_host="http://localhost:9003")

            # Should raise the network error
            with pytest.raises(httpx.HTTPError):
                await client.send_api_request(
                    "http://localhost:9003/allocation/compute"
                )

    async def test_send_api_request_different_http_methods(self) -> None:
        """Test different HTTP methods."""
        # Mock response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200

        # Mock HTTP client
        mock_http_client = AsyncMock()
        mock_http_client.request.return_value = mock_response

        # Create client with patched HTTP client
        with patch("client.http_async_client", new=mock_http_client):
            client = OpenCostClient(app_host="http://localhost:9003")
            url = "http://localhost:9003/allocation/compute"

            # Test GET (default)
            await client.send_api_request(url)
            mock_http_client.request.assert_called_with(
                method="GET",
                url=url,
                params=None,
            )

            # Test POST
            mock_http_client.request.reset_mock()
            await client.send_api_request(url, method="POST")
            mock_http_client.request.assert_called_with(
                method="POST",
                url=url,
                params=None,
            )

            # Test PUT
            mock_http_client.request.reset_mock()
            await client.send_api_request(url, method="PUT")
            mock_http_client.request.assert_called_with(
                method="PUT",
                url=url,
                params=None,
            )

    async def test_should_ignore_error_with_default_errors(self) -> None:
        """Test _should_ignore_error method with default ignored errors."""
        # Create client
        client = OpenCostClient(app_host="http://localhost:9003")

        # Test 404 error (should be ignored)
        mock_response_404 = MagicMock()
        mock_response_404.status_code = 404
        error_404 = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=mock_response_404
        )

        assert client._should_ignore_error(error_404, "test-endpoint") is True

        # Test 403 error (should be ignored)
        mock_response_403 = MagicMock()
        mock_response_403.status_code = 403
        error_403 = httpx.HTTPStatusError(
            "403", request=MagicMock(), response=mock_response_403
        )

        assert client._should_ignore_error(error_403, "test-endpoint") is True

        # Test 500 error (should NOT be ignored)
        mock_response_500 = MagicMock()
        mock_response_500.status_code = 500
        error_500 = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=mock_response_500
        )

        assert client._should_ignore_error(error_500, "test-endpoint") is False

    async def test_should_ignore_error_with_custom_errors(self) -> None:
        """Test _should_ignore_error method with custom ignored errors."""
        # Create client
        client = OpenCostClient(app_host="http://localhost:9003")

        # Test 500 error with custom ignored error
        mock_response_500 = MagicMock()
        mock_response_500.status_code = 500
        error_500 = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=mock_response_500
        )

        custom_ignored_errors = [IgnoredError(status=500, message="Custom 500 error")]

        assert (
            client._should_ignore_error(
                error_500, "test-endpoint", custom_ignored_errors
            )
            is True
        )

    async def test_get_cost_allocation_success(
        self, opencost_resource_config: OpencostResourceConfig
    ) -> None:
        """Test get_cost_allocation method success."""

        # Mock response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{"id": 1, "cost": 100, "namespace": "default"}]
        }

        # Mock HTTP client
        mock_http_client = AsyncMock()
        mock_http_client.request.return_value = mock_response

        # Create client with patched HTTP client
        with patch("client.http_async_client", new=mock_http_client):
            client = OpenCostClient(app_host="http://localhost:9003")

            # Set up proper event and resource contexts
            async with event_context("test_event"):
                async with resource_context(opencost_resource_config, 0):
                    result = await client.get_cost_allocation()

            assert result == [{"id": 1, "cost": 100, "namespace": "default"}]

    async def test_get_cost_allocation_with_ignored_error(
        self, opencost_resource_config: OpencostResourceConfig
    ) -> None:
        """Test get_cost_allocation method with ignored error."""

        # Mock 404 error response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found", request=MagicMock(), response=mock_response
        )

        # Mock HTTP client
        mock_http_client = AsyncMock()
        mock_http_client.request.return_value = mock_response

        # Create client with patched HTTP client
        with patch("client.http_async_client", new=mock_http_client):
            client = OpenCostClient(app_host="http://localhost:9003")

            # Set up proper event and resource contexts
            async with event_context("test_event"):
                async with resource_context(opencost_resource_config, 0):
                    result = await client.get_cost_allocation()

            # Should return empty list when error is ignored
            assert result == []

    async def test_get_cloudcost_success(
        self, cloudcost_resource_config: CloudCostResourceConfig
    ) -> None:
        """Test get_cloudcost method success."""

        # Mock response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {"sets": [{"id": 1, "cost": 200, "provider": "aws"}]}
        }

        # Mock HTTP client
        mock_http_client = AsyncMock()
        mock_http_client.request.return_value = mock_response

        # Create client with patched HTTP client
        with patch("client.http_async_client", new=mock_http_client):
            client = OpenCostClient(app_host="http://localhost:9003")

            # Set up proper event and resource contexts
            async with event_context("test_event"):
                async with resource_context(cloudcost_resource_config, 0):
                    result = await client.get_cloudcost()

            assert result == [{"id": 1, "cost": 200, "provider": "aws"}]

    async def test_get_cloudcost_with_ignored_error(
        self, cloudcost_resource_config: CloudCostResourceConfig
    ) -> None:
        """Test get_cloudcost method with ignored error."""

        # Mock 403 error response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 403
        mock_response.text = "Forbidden"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "403 Forbidden", request=MagicMock(), response=mock_response
        )

        # Mock HTTP client
        mock_http_client = AsyncMock()
        mock_http_client.request.return_value = mock_response

        # Create client with patched HTTP client
        with patch("client.http_async_client", new=mock_http_client):
            client = OpenCostClient(app_host="http://localhost:9003")

            # Set up proper event and resource contexts
            async with event_context("test_event"):
                async with resource_context(cloudcost_resource_config, 0):
                    result = await client.get_cloudcost()

            # Should return empty list when error is ignored
            assert result == []
