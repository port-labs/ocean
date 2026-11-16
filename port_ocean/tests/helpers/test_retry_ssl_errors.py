"""
Tests for SSL/TLS certificate error handling in RetryTransport.

SSL/certificate errors should NOT be retried - they indicate configuration
problems (invalid cert, expired cert, hostname mismatch, etc.), not transient failures.
"""

import pytest
import ssl
from unittest.mock import AsyncMock, Mock, patch
from http import HTTPStatus
import httpx

from port_ocean.helpers.retry import RetryConfig, RetryTransport, _is_ssl_error


class TestIsSSLError:
    """Test the _is_ssl_error() helper function."""

    def test_detects_ssl_error_as_direct_cause(self) -> None:
        """SSL error as __cause__ is detected."""
        ssl_err = ssl.SSLError("certificate verify failed")
        connect_err = httpx.ConnectError("SSL error")
        connect_err.__cause__ = ssl_err

        assert _is_ssl_error(connect_err) is True

    def test_detects_ssl_cert_verification_error(self) -> None:
        """SSLCertVerificationError is detected."""
        ssl_err = ssl.SSLCertVerificationError("hostname mismatch")
        connect_err = httpx.ConnectError("SSL error")
        connect_err.__cause__ = ssl_err

        assert _is_ssl_error(connect_err) is True

    def test_detects_ssl_error_in_context_chain(self) -> None:
        """SSL error as __context__ (implicit) is detected."""
        ssl_err = ssl.SSLError("handshake failure")
        connect_err = httpx.ConnectError("Connection failed")
        connect_err.__context__ = ssl_err

        assert _is_ssl_error(connect_err) is True

    def test_detects_ssl_error_nested_in_chain(self) -> None:
        """SSL error deep in exception chain is detected."""
        ssl_err = ssl.SSLCertVerificationError("certificate verify failed")
        mid_err = RuntimeError("Mid error")
        mid_err.__cause__ = ssl_err
        connect_err = httpx.ConnectError("Connection error")
        connect_err.__cause__ = mid_err

        assert _is_ssl_error(connect_err) is True

    def test_returns_false_for_non_ssl_connect_error(self) -> None:
        """Generic ConnectError without SSL in chain returns False."""
        connect_err = httpx.ConnectError("Connection refused")

        assert _is_ssl_error(connect_err) is False

    def test_returns_false_for_timeout_error(self) -> None:
        """Timeout errors are not SSL errors."""
        timeout_err = httpx.ConnectTimeout("Timed out")

        assert _is_ssl_error(timeout_err) is False

    def test_handles_circular_exception_chain(self) -> None:
        """Circular exception chain doesn't cause infinite loop."""
        err1 = RuntimeError("Error 1")
        err2 = RuntimeError("Error 2")
        err1.__cause__ = err2
        err2.__cause__ = err1

        assert _is_ssl_error(err1) is False


class TestSSLErrorNoRetry:
    """Test that SSL/certificate errors are NOT retried."""

    @pytest.mark.asyncio
    async def test_ssl_error_not_retried_exactly_one_attempt(self) -> None:
        """
        SSL/certificate errors should fail immediately with exactly ONE attempt.
        No retries should occur.
        """
        request_count = {"count": 0}

        class SSLErrorTransport(httpx.AsyncHTTPTransport):
            async def handle_async_request(
                self, request: httpx.Request
            ) -> httpx.Response:
                request_count["count"] += 1
                # Simulate SSL certificate verification failure
                ssl_err = ssl.SSLCertVerificationError(
                    "certificate verify failed: self signed certificate"
                )
                connect_err = httpx.ConnectError("SSL: CERTIFICATE_VERIFY_FAILED")
                connect_err.__cause__ = ssl_err
                raise connect_err

        transport = RetryTransport(
            wrapped_transport=SSLErrorTransport(),
            retry_config=RetryConfig(max_attempts=10),
        )

        request = httpx.Request("GET", "https://example.com/api")

        # Should raise immediately without retries
        with pytest.raises(httpx.ConnectError) as exc_info:
            await transport.handle_async_request(request)

        # Verify it's the SSL error
        assert (
            "SSL" in str(exc_info.value) or "certificate" in str(exc_info.value).lower()
        )

        # Exactly one attempt, no retries
        assert (
            request_count["count"] == 1
        ), f"Expected exactly 1 attempt for SSL error, got {request_count['count']}"

    @pytest.mark.asyncio
    async def test_generic_connect_error_is_still_retried(self) -> None:
        """
        Non-SSL ConnectErrors (connection refused, network unreachable, etc.)
        should still be retried as before.
        """
        request_count = {"count": 0}

        class TransientConnectErrorTransport(httpx.AsyncHTTPTransport):
            async def handle_async_request(
                self, request: httpx.Request
            ) -> httpx.Response:
                request_count["count"] += 1
                if request_count["count"] < 3:
                    # Connection refused - retryable
                    raise httpx.ConnectError("Connection refused")
                else:
                    # Success on third attempt
                    return httpx.Response(
                        HTTPStatus.OK,
                        request=request,
                        content=b'{"success": true}',
                    )

        transport = RetryTransport(
            wrapped_transport=TransientConnectErrorTransport(),
            retry_config=RetryConfig(max_attempts=5),
        )

        request = httpx.Request("GET", "https://example.com/api")

        # Patch sleep to speed up test
        with patch("port_ocean.helpers.retry.asyncio.sleep", new=AsyncMock()):
            response = await transport.handle_async_request(request)

        # Should have retried and succeeded
        assert response.status_code == HTTPStatus.OK
        assert request_count["count"] == 3, "Should have made 3 attempts (2 retries)"

    @pytest.mark.asyncio
    async def test_timeout_errors_still_retried(self) -> None:
        """
        Timeout errors should still be retried as before.
        """
        request_count = {"count": 0}

        class TimeoutThenSuccessTransport(httpx.AsyncHTTPTransport):
            async def handle_async_request(
                self, request: httpx.Request
            ) -> httpx.Response:
                request_count["count"] += 1
                if request_count["count"] < 3:
                    raise httpx.ConnectTimeout("Connection timed out")
                else:
                    return httpx.Response(
                        HTTPStatus.OK,
                        request=request,
                        content=b'{"success": true}',
                    )

        transport = RetryTransport(
            wrapped_transport=TimeoutThenSuccessTransport(),
            retry_config=RetryConfig(max_attempts=5),
        )

        request = httpx.Request("GET", "https://example.com/api")

        with patch("port_ocean.helpers.retry.asyncio.sleep", new=AsyncMock()):
            response = await transport.handle_async_request(request)

        assert response.status_code == HTTPStatus.OK
        assert request_count["count"] == 3, "Should have retried timeouts"

    @pytest.mark.asyncio
    async def test_ssl_error_logs_clear_message(self) -> None:
        """
        SSL errors should log a clear error message about certificate validation.
        """
        ssl_err = ssl.SSLCertVerificationError("certificate verify failed")
        connect_err = httpx.ConnectError("SSL error")
        connect_err.__cause__ = ssl_err

        class SSLErrorTransport(httpx.AsyncHTTPTransport):
            async def handle_async_request(
                self, request: httpx.Request
            ) -> httpx.Response:
                raise connect_err

        mock_logger = Mock()
        transport = RetryTransport(
            wrapped_transport=SSLErrorTransport(),
            retry_config=RetryConfig(max_attempts=10),
            logger=mock_logger,
        )

        request = httpx.Request("GET", "https://example.com/api")

        with pytest.raises(httpx.ConnectError):
            await transport.handle_async_request(request)

        # Verify clear error message was logged
        mock_logger.error.assert_called_once()
        error_msg = mock_logger.error.call_args[0][0]
        assert "SSL" in error_msg or "certificate" in error_msg.lower()
        assert "verify" in error_msg.lower() or "validation" in error_msg.lower()
