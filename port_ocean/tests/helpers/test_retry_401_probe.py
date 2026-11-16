"""
Tests to verify that 401 (Unauthorized) responses during test connection/probe
are not retried when skip_retry is set.

This test suite confirms that:
1. skip_retry=True prevents ALL retries (including for 401)
2. Without skip_retry, 401 IS retried by default (which is the problem for probe)
3. The fix ensures 401 is NOT retried during probe/test-connection flows
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from http import HTTPStatus
import httpx

from port_ocean.helpers.retry import RetryConfig, RetryTransport, SKIP_RETRY_EXTENSION_KEY


class TestProbe401NoRetry:
    """Test that 401 responses with skip_retry are not retried."""

    @pytest.mark.asyncio
    async def test_401_with_skip_retry_does_not_retry(self) -> None:
        """
        When skip_retry extension is set, a 401 response should NOT be retried.
        This is the CURRENT and EXPECTED behavior for test connection / probe.
        
        This test confirms the mechanism works correctly.
        """
        mock_transport = Mock()
        transport = RetryTransport(
            wrapped_transport=mock_transport,
            retry_config=RetryConfig(max_attempts=3),
        )

        request = httpx.Request(
            "GET",
            "https://example.com/api/myself",
            extensions={SKIP_RETRY_EXTENSION_KEY: True},
        )

        # Mock a 401 response
        response_401 = httpx.Response(
            HTTPStatus.UNAUTHORIZED,
            request=request,
            json={"error": "Unauthorized"},
        )

        mock_transport.handle_async_request = AsyncMock(return_value=response_401)

        # Execute the request
        result = await transport.handle_async_request(request)

        # Assert: Should NOT retry, so handle_async_request called exactly once
        assert mock_transport.handle_async_request.await_count == 1
        assert result.status_code == HTTPStatus.UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_401_without_skip_retry_is_retried(self) -> None:
        """
        When skip_retry is NOT set, a 401 response SHOULD be retried (current behavior).
        This confirms the default retry logic includes 401.
        """
        mock_transport = Mock()
        transport = RetryTransport(
            wrapped_transport=mock_transport,
            retry_config=RetryConfig(max_attempts=3),
        )

        # Request without skip_retry extension
        request = httpx.Request("GET", "https://example.com/api/myself")

        # Mock responses: two 401s, then success
        response_401_1 = httpx.Response(
            HTTPStatus.UNAUTHORIZED,
            request=request,
            json={"error": "Unauthorized"},
        )
        response_401_1.aclose = AsyncMock()

        response_401_2 = httpx.Response(
            HTTPStatus.UNAUTHORIZED,
            request=request,
            json={"error": "Unauthorized"},
        )
        response_401_2.aclose = AsyncMock()

        response_200 = httpx.Response(
            HTTPStatus.OK,
            request=request,
            json={"user": "test"},
        )

        mock_transport.handle_async_request = AsyncMock(
            side_effect=[response_401_1, response_401_2, response_200]
        )

        # Patch sleep to avoid waiting
        with patch(
            "port_ocean.helpers.retry.asyncio.sleep",
            new=AsyncMock(return_value=None),
        ):
            result = await transport.handle_async_request(request)

        # Assert: Should retry twice (3 total calls)
        assert mock_transport.handle_async_request.await_count == 3
        assert result.status_code == HTTPStatus.OK

    @pytest.mark.asyncio
    async def test_500_with_skip_retry_does_not_retry(self) -> None:
        """
        Verify skip_retry also prevents retries for other status codes like 500.
        """
        mock_transport = Mock()
        transport = RetryTransport(
            wrapped_transport=mock_transport,
            retry_config=RetryConfig(max_attempts=3),
        )

        request = httpx.Request(
            "GET",
            "https://example.com/api/myself",
            extensions={SKIP_RETRY_EXTENSION_KEY: True},
        )

        response_500 = httpx.Response(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            request=request,
            json={"error": "Server error"},
        )

        mock_transport.handle_async_request = AsyncMock(return_value=response_500)

        result = await transport.handle_async_request(request)

        # Should NOT retry
        assert mock_transport.handle_async_request.await_count == 1
        assert result.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
