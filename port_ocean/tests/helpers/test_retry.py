import pytest
from unittest.mock import Mock, AsyncMock, patch
from http import HTTPStatus
import httpx

from port_ocean.helpers.retry import (
    RetryConfig,
    RetryTransport,
    register_retry_config_callback,
    register_on_retry_callback,
)
import port_ocean.helpers.retry as retry_module


class TestRetryConfig:
    def test_default_configuration(self) -> None:
        """Test RetryConfig with default parameters."""
        config = RetryConfig()

        assert config.max_attempts == 10
        assert config.max_backoff_wait == 60.0
        assert config.base_delay == 0.1
        assert config.jitter_ratio == 0.1
        assert config.respect_retry_after_header is True
        assert config.retryable_methods == frozenset(
            ["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE"]
        )
        assert config.retry_status_codes == frozenset(
            [
                HTTPStatus.TOO_MANY_REQUESTS,
                HTTPStatus.BAD_GATEWAY,
                HTTPStatus.SERVICE_UNAVAILABLE,
                HTTPStatus.GATEWAY_TIMEOUT,
                HTTPStatus.UNAUTHORIZED,
                HTTPStatus.BAD_REQUEST,
            ]
        )
        assert config.retry_after_headers == ["Retry-After"]

    def test_custom_configuration(self) -> None:
        """Test RetryConfig with custom parameters."""
        config = RetryConfig(
            max_attempts=5,
            max_backoff_wait=30.0,
            base_delay=2.0,
            jitter_ratio=0.2,
            respect_retry_after_header=False,
            retryable_methods=["GET", "POST"],
            retry_after_headers=["X-Custom-Retry", "Retry-After"],
            additional_retry_status_codes=[418, 420],
        )

        assert config.max_attempts == 5
        assert config.max_backoff_wait == 30.0
        assert config.base_delay == 2.0
        assert config.jitter_ratio == 0.2
        assert config.respect_retry_after_header is False
        assert config.retryable_methods == frozenset(["GET", "POST"])
        # Should include defaults + additional codes
        expected_codes = frozenset(
            [
                HTTPStatus.TOO_MANY_REQUESTS,
                HTTPStatus.BAD_GATEWAY,
                HTTPStatus.SERVICE_UNAVAILABLE,
                HTTPStatus.GATEWAY_TIMEOUT,
                HTTPStatus.UNAUTHORIZED,
                HTTPStatus.BAD_REQUEST,
                418,
                420,
            ]
        )
        assert config.retry_status_codes == expected_codes
        assert config.retry_after_headers == ["X-Custom-Retry", "Retry-After"]

    def test_additional_status_codes(self) -> None:
        """Test that additional status codes extend defaults."""
        config = RetryConfig(
            additional_retry_status_codes=[418, 420],
        )

        # Should include defaults + additional codes
        expected_codes = frozenset(
            [
                HTTPStatus.TOO_MANY_REQUESTS,
                HTTPStatus.BAD_GATEWAY,
                HTTPStatus.SERVICE_UNAVAILABLE,
                HTTPStatus.GATEWAY_TIMEOUT,
                HTTPStatus.UNAUTHORIZED,
                HTTPStatus.BAD_REQUEST,
                418,
                420,
            ]
        )
        assert config.retry_status_codes == expected_codes

    def test_invalid_jitter_ratio(self) -> None:
        """Test that invalid jitter ratio raises ValueError."""
        with pytest.raises(
            ValueError, match="Jitter ratio should be between 0 and 0.5"
        ):
            RetryConfig(jitter_ratio=0.6)

        with pytest.raises(
            ValueError, match="Jitter ratio should be between 0 and 0.5"
        ):
            RetryConfig(jitter_ratio=-0.1)

    def test_empty_additional_status_codes(self) -> None:
        """Test that empty additional status codes work correctly."""
        config = RetryConfig(additional_retry_status_codes=[])
        assert config.retry_status_codes == frozenset(
            [
                HTTPStatus.TOO_MANY_REQUESTS,
                HTTPStatus.BAD_GATEWAY,
                HTTPStatus.SERVICE_UNAVAILABLE,
                HTTPStatus.GATEWAY_TIMEOUT,
                HTTPStatus.UNAUTHORIZED,
                HTTPStatus.BAD_REQUEST,
            ]
        )


class TestRetryConfigCallback:
    def setup_method(self) -> None:
        """Reset global callback state before each test."""
        retry_module._RETRY_CONFIG_CALLBACK = None
        retry_module._ON_RETRY_CALLBACK = None

    def test_register_retry_config_callback(self) -> None:
        """Test registering a retry config callback."""

        def mock_callback() -> RetryConfig:
            return RetryConfig(max_attempts=5)

        register_retry_config_callback(mock_callback)

        assert retry_module._RETRY_CONFIG_CALLBACK is mock_callback
        config = retry_module._RETRY_CONFIG_CALLBACK()
        assert config.max_attempts == 5

    def test_register_on_retry_callback(self) -> None:
        """Test registering an on retry callback."""

        def mock_callback(request: httpx.Request) -> httpx.Request:
            return request

        register_on_retry_callback(mock_callback)

        assert retry_module._ON_RETRY_CALLBACK is mock_callback

    def test_callback_overwrite(self) -> None:
        """Test that registering a new callback overwrites the previous one."""

        def callback1() -> RetryConfig:
            return RetryConfig(max_attempts=1)

        def callback2() -> RetryConfig:
            return RetryConfig(max_attempts=2)

        register_retry_config_callback(callback1)
        assert retry_module._RETRY_CONFIG_CALLBACK is not None
        assert retry_module._RETRY_CONFIG_CALLBACK().max_attempts == 1

        register_retry_config_callback(callback2)
        assert retry_module._RETRY_CONFIG_CALLBACK is not None
        assert retry_module._RETRY_CONFIG_CALLBACK().max_attempts == 2


class TestRetryTransport:
    def setup_method(self) -> None:
        """Reset global callback state before each test."""
        retry_module._RETRY_CONFIG_CALLBACK = None
        retry_module._ON_RETRY_CALLBACK = None

    def test_retry_transport_with_direct_config(self) -> None:
        """Test RetryTransport with direct retry_config parameter."""
        mock_transport = Mock()
        config = RetryConfig(max_attempts=5)

        transport = RetryTransport(
            wrapped_transport=mock_transport,
            retry_config=config,
        )

        assert transport._retry_config is config
        assert transport._retry_config.max_attempts == 5

    def test_retry_transport_with_callback(self) -> None:
        """Test RetryTransport using registered callback."""

        def mock_callback() -> RetryConfig:
            return RetryConfig(max_attempts=7)

        register_retry_config_callback(mock_callback)

        mock_transport = Mock()
        transport = RetryTransport(wrapped_transport=mock_transport)

        assert transport._retry_config.max_attempts == 7

    def test_retry_transport_priority_order(self) -> None:
        """Test that direct config takes priority over callback."""

        def mock_callback() -> RetryConfig:
            return RetryConfig(max_attempts=7)

        register_retry_config_callback(mock_callback)

        mock_transport = Mock()
        direct_config = RetryConfig(max_attempts=5)

        transport = RetryTransport(
            wrapped_transport=mock_transport,
            retry_config=direct_config,
        )

        assert transport._retry_config.max_attempts == 5  # Direct config wins

    def test_retry_transport_default_config(self) -> None:
        """Test RetryTransport with no config or callback."""
        mock_transport = Mock()
        transport = RetryTransport(wrapped_transport=mock_transport)

        assert transport._retry_config.max_attempts == 10  # Default value
        assert transport._retry_config.retry_after_headers == ["Retry-After"]

    def test_is_retryable_method(self) -> None:
        """Test _is_retryable_method functionality."""
        mock_transport = Mock()
        transport = RetryTransport(wrapped_transport=mock_transport)

        # Test with default retryable methods
        mock_request = Mock()
        mock_request.method = "GET"
        mock_request.extensions = {}

        assert transport._is_retryable_method(mock_request) is True

        mock_request.method = "POST"
        assert transport._is_retryable_method(mock_request) is False

        # Test with retryable extension
        mock_request.extensions = {"retryable": True}
        assert transport._is_retryable_method(mock_request) is True

    def test_should_retry(self) -> None:
        """Test _should_retry functionality."""
        mock_transport = Mock()
        transport = RetryTransport(wrapped_transport=mock_transport)

        mock_response = Mock()
        mock_response.status_code = 429
        assert transport._should_retry(mock_response) is True

        mock_response.status_code = 200
        assert transport._should_retry(mock_response) is False

    def test_parse_retry_header(self) -> None:
        """Test _parse_retry_header functionality."""
        mock_transport = Mock()
        transport = RetryTransport(wrapped_transport=mock_transport)

        # Test numeric seconds
        assert transport._parse_retry_header("30") == 30.0

        # Test invalid numeric
        assert transport._parse_retry_header("invalid") is None

        # Test ISO date (would need proper date parsing test)
        # This is a basic test - actual date parsing would need more complex setup
        assert (
            transport._parse_retry_header("2023-12-01T12:00:00Z") is None
        )  # Will fail parsing


class TestRetryConfigIntegration:
    """Integration tests for retry configuration."""

    def setup_method(self) -> None:
        """Reset global callback state before each test."""
        retry_module._RETRY_CONFIG_CALLBACK = None
        retry_module._ON_RETRY_CALLBACK = None

    def test_integration_style_config(self) -> None:
        """Test configuration similar to GitHub integration."""

        def integration_retry_config() -> RetryConfig:
            return RetryConfig(
                max_attempts=10,
                max_backoff_wait=60.0,
                base_delay=1.0,
                jitter_ratio=0.1,
                respect_retry_after_header=True,
                retry_after_headers=["X-RateLimit-Reset", "Retry-After"],
                additional_retry_status_codes=[HTTPStatus.FORBIDDEN],
            )

        register_retry_config_callback(integration_retry_config)

        mock_transport = Mock()
        transport = RetryTransport(wrapped_transport=mock_transport)

        assert transport._retry_config.max_attempts == 10
        assert transport._retry_config.base_delay == 1.0
        assert transport._retry_config.retry_after_headers == [
            "X-RateLimit-Reset",
            "Retry-After",
        ]
        assert HTTPStatus.FORBIDDEN in transport._retry_config.retry_status_codes


class TestResponseSizeLogging:
    """Tests for response size logging functionality."""

    def setup_method(self) -> None:
        """Reset global callback state before each test."""
        retry_module._RETRY_CONFIG_CALLBACK = None
        retry_module._ON_RETRY_CALLBACK = None

    def test_should_log_response_size_with_logger(self) -> None:
        """Test _should_log_response_size returns True when logger is present and not getport.io."""
        mock_transport = Mock()
        mock_logger = Mock()
        transport = RetryTransport(wrapped_transport=mock_transport, logger=mock_logger)

        mock_request = Mock()
        mock_request.url.host = "api.example.com"

        assert transport._should_log_response_size(mock_request) is True

    def test_should_log_response_size_without_logger(self) -> None:
        """Test _should_log_response_size returns False when no logger."""
        mock_transport = Mock()
        transport = RetryTransport(wrapped_transport=mock_transport)

        mock_request = Mock()
        mock_request.url.host = "api.example.com"

        assert transport._should_log_response_size(mock_request) is False

    def test_should_log_response_size_getport_io(self) -> None:
        """Test _should_log_response_size returns False for getport.io domains."""
        mock_transport = Mock()
        mock_logger = Mock()
        transport = RetryTransport(wrapped_transport=mock_transport, logger=mock_logger)

        mock_request = Mock()
        mock_request.url.host = "api.getport.io"

        assert transport._should_log_response_size(mock_request) is False

    def test_get_content_length_from_headers(self) -> None:
        """Test _get_content_length extracts content length from headers."""
        mock_transport = Mock()
        transport = RetryTransport(wrapped_transport=mock_transport)

        mock_response = Mock()
        mock_response.headers = {"Content-Length": "1024"}

        assert transport._get_content_length(mock_response) == 1024

    def test_get_content_length_case_insensitive(self) -> None:
        """Test _get_content_length works with case insensitive headers."""
        mock_transport = Mock()
        transport = RetryTransport(wrapped_transport=mock_transport)

        mock_response = Mock()
        mock_response.headers = {"content-length": "2048"}

        assert transport._get_content_length(mock_response) == 2048

    def test_get_content_length_no_header(self) -> None:
        """Test _get_content_length returns None when no content-length header."""
        mock_transport = Mock()
        transport = RetryTransport(wrapped_transport=mock_transport)

        mock_response = Mock()
        mock_response.headers = {}

        assert transport._get_content_length(mock_response) is None

    def test_get_content_length_invalid_value(self) -> None:
        """Test _get_content_length handles invalid header values."""
        mock_transport = Mock()
        transport = RetryTransport(wrapped_transport=mock_transport)

        mock_response = Mock()
        mock_response.headers = {"Content-Length": "invalid"}

        # Should raise ValueError when converting to int
        with pytest.raises(ValueError):
            transport._get_content_length(mock_response)

    @patch("port_ocean.helpers.retry.cast")
    def test_log_response_size_with_content_length(self, mock_cast: Mock) -> None:
        """Test _log_response_size logs when Content-Length header is present."""
        mock_transport = Mock()
        mock_logger = Mock()
        mock_cast.return_value = mock_logger
        transport = RetryTransport(wrapped_transport=mock_transport, logger=mock_logger)

        mock_request = Mock()
        mock_request.method = "GET"
        mock_url = Mock()
        mock_url.host = "api.example.com"
        mock_url.configure_mock(__str__=lambda self: "https://api.example.com/data")
        mock_request.url = mock_url

        mock_response = Mock()
        mock_response.headers = {"Content-Length": "1024"}

        transport._log_response_size(mock_request, mock_response)

        mock_logger.info.assert_called_once_with(
            "Response for GET https://api.example.com/data - Size: 1024 bytes"
        )

    @patch("port_ocean.helpers.retry.cast")
    def test_log_response_size_without_content_length(self, mock_cast: Mock) -> None:
        """Test _log_response_size reads content when no Content-Length header."""
        mock_transport = Mock()
        mock_logger = Mock()
        mock_cast.return_value = mock_logger
        transport = RetryTransport(wrapped_transport=mock_transport, logger=mock_logger)

        mock_request = Mock()
        mock_request.method = "POST"
        mock_url = Mock()
        mock_url.host = "api.example.com"
        mock_url.configure_mock(__str__=lambda self: "https://api.example.com/create")
        mock_request.url = mock_url

        mock_response = Mock()
        mock_response.headers = {}
        mock_response.read.return_value = b"test content"

        transport._log_response_size(mock_request, mock_response)

        mock_response.read.assert_called_once()
        mock_logger.info.assert_called_once_with(
            "Response for POST https://api.example.com/create - Size: 12 bytes"
        )

    @patch("port_ocean.helpers.retry.cast")
    def test_log_response_size_read_error(self, mock_cast: Mock) -> None:
        """Test _log_response_size handles read errors gracefully."""
        mock_transport = Mock()
        mock_logger = Mock()
        mock_cast.return_value = mock_logger
        transport = RetryTransport(wrapped_transport=mock_transport, logger=mock_logger)

        mock_request = Mock()
        mock_request.method = "GET"
        mock_request.url.host = "api.example.com"

        mock_response = Mock()
        mock_response.headers = {}
        mock_response.read.side_effect = Exception("Read error")

        transport._log_response_size(mock_request, mock_response)

        mock_logger.error.assert_called_once_with(
            "Error getting response size: Read error"
        )
        mock_logger.info.assert_not_called()

    @patch("port_ocean.helpers.retry.cast")
    def test_log_response_size_skips_when_should_not_log(self, mock_cast: Mock) -> None:
        """Test _log_response_size skips logging when _should_log_response_size returns False."""
        mock_transport = Mock()
        mock_logger = Mock()
        mock_cast.return_value = mock_logger
        transport = RetryTransport(wrapped_transport=mock_transport, logger=mock_logger)

        mock_request = Mock()
        mock_request.url.host = "api.getport.io"  # This should skip logging

        mock_response = Mock()
        mock_response.headers = {"Content-Length": "1024"}

        transport._log_response_size(mock_request, mock_response)

        mock_logger.info.assert_not_called()

    @pytest.mark.asyncio
    @patch("port_ocean.helpers.retry.cast")
    async def test_log_response_size_async_with_content_length(
        self, mock_cast: Mock
    ) -> None:
        """Test _log_response_size_async logs when Content-Length header is present."""
        mock_transport = Mock()
        mock_logger = Mock()
        mock_cast.return_value = mock_logger
        transport = RetryTransport(wrapped_transport=mock_transport, logger=mock_logger)

        mock_request = Mock()
        mock_request.method = "GET"
        mock_url = Mock()
        mock_url.host = "api.example.com"
        mock_url.configure_mock(__str__=lambda self: "https://api.example.com/data")
        mock_request.url = mock_url

        mock_response = Mock()
        mock_response.headers = {"Content-Length": "1024"}

        await transport._log_response_size_async(mock_request, mock_response)

        mock_logger.info.assert_called_once_with(
            "Response for GET https://api.example.com/data - Size: 1024 bytes"
        )

    @pytest.mark.asyncio
    @patch("port_ocean.helpers.retry.cast")
    async def test_log_response_size_async_without_content_length(
        self, mock_cast: Mock
    ) -> None:
        """Test _log_response_size_async reads content when no Content-Length header."""
        mock_transport = Mock()
        mock_logger = Mock()
        mock_cast.return_value = mock_logger
        transport = RetryTransport(wrapped_transport=mock_transport, logger=mock_logger)

        mock_request = Mock()
        mock_request.method = "POST"
        mock_url = Mock()
        mock_url.host = "api.example.com"
        mock_url.configure_mock(__str__=lambda self: "https://api.example.com/create")
        mock_request.url = mock_url

        mock_response = Mock()
        mock_response.headers = {}
        mock_response.aread = AsyncMock(return_value=b"test content")

        await transport._log_response_size_async(mock_request, mock_response)

        mock_response.aread.assert_called_once()
        mock_logger.info.assert_called_once_with(
            "Response for POST https://api.example.com/create - Size: 12 bytes"
        )

    @pytest.mark.asyncio
    @patch("port_ocean.helpers.retry.cast")
    async def test_log_response_size_async_read_error(self, mock_cast: Mock) -> None:
        """Test _log_response_size_async handles read errors gracefully."""
        mock_transport = Mock()
        mock_logger = Mock()
        mock_cast.return_value = mock_logger
        transport = RetryTransport(wrapped_transport=mock_transport, logger=mock_logger)

        mock_request = Mock()
        mock_request.method = "GET"
        mock_request.url.host = "api.example.com"

        mock_response = Mock()
        mock_response.headers = {}
        mock_response.aread = AsyncMock(side_effect=Exception("Async read error"))

        await transport._log_response_size_async(mock_request, mock_response)

        mock_logger.error.assert_called_once_with(
            "Error getting response size: Async read error"
        )
        mock_logger.info.assert_not_called()

    @pytest.mark.asyncio
    @patch("port_ocean.helpers.retry.cast")
    async def test_log_response_size_async_skips_when_should_not_log(
        self, mock_cast: Mock
    ) -> None:
        """Test _log_response_size_async skips logging when _should_log_response_size returns False."""
        mock_transport = Mock()
        mock_logger = Mock()
        mock_cast.return_value = mock_logger
        transport = RetryTransport(wrapped_transport=mock_transport, logger=mock_logger)

        mock_request = Mock()
        mock_request.url.host = "api.getport.io"  # This should skip logging

        mock_response = Mock()
        mock_response.headers = {"Content-Length": "1024"}

        await transport._log_response_size_async(mock_request, mock_response)

        mock_logger.info.assert_not_called()

    @pytest.mark.asyncio
    @patch("port_ocean.helpers.retry.cast")
    async def test_log_response_size_async_restores_content(
        self, mock_cast: Mock
    ) -> None:
        """Test _log_response_size_async restores response content after reading."""
        mock_transport = Mock()
        mock_logger = Mock()
        mock_cast.return_value = mock_logger
        transport = RetryTransport(wrapped_transport=mock_transport, logger=mock_logger)

        mock_request = Mock()
        mock_request.method = "GET"
        mock_url = Mock()
        mock_url.host = "api.example.com"
        mock_url.configure_mock(__str__=lambda self: "https://api.example.com/data")
        mock_request.url = mock_url

        test_content = b"test response content"
        mock_response = Mock()
        mock_response.headers = {}
        mock_response.aread = AsyncMock(return_value=test_content)

        await transport._log_response_size_async(mock_request, mock_response)

        # Verify that the content was restored to the response
        assert mock_response._content == test_content
        mock_logger.info.assert_called_once_with(
            "Response for GET https://api.example.com/data - Size: 21 bytes"
        )

    @patch("port_ocean.helpers.retry.cast")
    def test_log_response_size_restores_content(self, mock_cast: Mock) -> None:
        """Test _log_response_size restores response content after reading."""
        mock_transport = Mock()
        mock_logger = Mock()
        mock_cast.return_value = mock_logger
        transport = RetryTransport(wrapped_transport=mock_transport, logger=mock_logger)

        mock_request = Mock()
        mock_request.method = "GET"
        mock_url = Mock()
        mock_url.host = "api.example.com"
        mock_url.configure_mock(__str__=lambda self: "https://api.example.com/data")
        mock_request.url = mock_url

        test_content = b"test response content"
        mock_response = Mock()
        mock_response.headers = {}
        mock_response.read.return_value = test_content

        transport._log_response_size(mock_request, mock_response)

        # Verify that the content was restored to the response
        assert mock_response._content == test_content
        mock_logger.info.assert_called_once_with(
            "Response for GET https://api.example.com/data - Size: 21 bytes"
        )


class TestResponseSizeLoggingIntegration:
    """Integration tests to verify response consumption works after size logging."""

    def setup_method(self) -> None:
        """Reset global callback state before each test."""
        retry_module._RETRY_CONFIG_CALLBACK = None
        retry_module._ON_RETRY_CALLBACK = None

    @patch("port_ocean.helpers.retry.cast")
    def test_log_response_size_preserves_json_consumption(
        self, mock_cast: Mock
    ) -> None:
        """Test that _log_response_size preserves response for .json() consumption."""
        mock_transport = Mock()
        mock_logger = Mock()
        mock_cast.return_value = mock_logger
        transport = RetryTransport(wrapped_transport=mock_transport, logger=mock_logger)

        mock_request = Mock()
        mock_request.method = "GET"
        mock_request.url.host = "api.example.com"

        # Create a mock response with JSON content
        json_content = b'{"message": "test", "data": [1, 2, 3]}'
        mock_response = Mock()
        mock_response.headers = {}  # No Content-Length header to force content reading
        mock_response.read.return_value = json_content
        mock_response.json.return_value = {"message": "test", "data": [1, 2, 3]}

        # Call the logging function
        transport._log_response_size(mock_request, mock_response)

        # Verify logging occurred
        mock_logger.info.assert_called_once()

        # Verify that response.json() can still be called without StreamConsumed error
        result = mock_response.json()
        assert result == {"message": "test", "data": [1, 2, 3]}

        # Verify that read was called and content was restored
        mock_response.read.assert_called_once()
        assert mock_response._content == json_content

    @patch("port_ocean.helpers.retry.cast")
    def test_log_response_size_with_content_length_preserves_json(
        self, mock_cast: Mock
    ) -> None:
        """Test that _log_response_size with Content-Length header preserves JSON consumption."""
        mock_transport = Mock()
        mock_logger = Mock()
        mock_cast.return_value = mock_logger
        transport = RetryTransport(wrapped_transport=mock_transport, logger=mock_logger)

        mock_request = Mock()
        mock_request.method = "POST"
        mock_request.url.host = "api.example.com"

        # Create a mock response with Content-Length header
        mock_response = Mock()
        mock_response.headers = {"Content-Length": "1024"}
        mock_response.json.return_value = {"status": "success", "id": 123}

        # Call the logging function
        transport._log_response_size(mock_request, mock_response)

        # Verify logging occurred
        mock_logger.info.assert_called_once()

        # Verify that response.json() can still be called
        result = mock_response.json()
        assert result == {"status": "success", "id": 123}

        # Verify that read was NOT called since we had Content-Length
        mock_response.read.assert_not_called()

    @pytest.mark.asyncio
    @patch("port_ocean.helpers.retry.cast")
    async def test_log_response_size_async_preserves_json_consumption(
        self, mock_cast: Mock
    ) -> None:
        """Test that _log_response_size_async preserves response for .json() consumption."""
        mock_transport = Mock()
        mock_logger = Mock()
        mock_cast.return_value = mock_logger
        transport = RetryTransport(wrapped_transport=mock_transport, logger=mock_logger)

        mock_request = Mock()
        mock_request.method = "GET"
        mock_request.url.host = "api.example.com"

        # Create a mock response with JSON content
        json_content = b'{"users": [{"name": "John", "age": 30}]}'
        mock_response = Mock()
        mock_response.headers = {}  # No Content-Length header to force content reading
        mock_response.aread = AsyncMock(return_value=json_content)
        mock_response.json.return_value = {"users": [{"name": "John", "age": 30}]}

        # Call the async logging function
        await transport._log_response_size_async(mock_request, mock_response)

        # Verify logging occurred
        mock_logger.info.assert_called_once()

        # Verify that response.json() can still be called without StreamConsumed error
        result = mock_response.json()
        assert result == {"users": [{"name": "John", "age": 30}]}

        # Verify that aread was called and content was restored
        mock_response.aread.assert_called_once()
        assert mock_response._content == json_content

    @pytest.mark.asyncio
    @patch("port_ocean.helpers.retry.cast")
    async def test_log_response_size_async_with_content_length_preserves_json(
        self, mock_cast: Mock
    ) -> None:
        """Test that _log_response_size_async with Content-Length header preserves JSON consumption."""
        mock_transport = Mock()
        mock_logger = Mock()
        mock_cast.return_value = mock_logger
        transport = RetryTransport(wrapped_transport=mock_transport, logger=mock_logger)

        mock_request = Mock()
        mock_request.method = "PUT"
        mock_request.url.host = "api.example.com"

        # Create a mock response with Content-Length header
        mock_response = Mock()
        mock_response.headers = {"Content-Length": "2048"}
        mock_response.json.return_value = {
            "updated": True,
            "timestamp": "2023-12-01T12:00:00Z",
        }

        # Call the async logging function
        await transport._log_response_size_async(mock_request, mock_response)

        # Verify logging occurred
        mock_logger.info.assert_called_once()

        # Verify that response.json() can still be called
        result = mock_response.json()
        assert result == {"updated": True, "timestamp": "2023-12-01T12:00:00Z"}

        # Verify that aread was NOT called since we had Content-Length
        mock_response.aread.assert_not_called()

    @patch("port_ocean.helpers.retry.cast")
    def test_log_response_size_preserves_text_consumption(
        self, mock_cast: Mock
    ) -> None:
        """Test that _log_response_size preserves response for .text consumption."""
        mock_transport = Mock()
        mock_logger = Mock()
        mock_cast.return_value = mock_logger
        transport = RetryTransport(wrapped_transport=mock_transport, logger=mock_logger)

        mock_request = Mock()
        mock_request.method = "GET"
        mock_request.url.host = "api.example.com"

        # Create a mock response with text content
        text_content = b"Hello, World! This is a test response."
        mock_response = Mock()
        mock_response.headers = {}  # No Content-Length header to force content reading
        mock_response.read.return_value = text_content
        mock_response.text = "Hello, World! This is a test response."

        # Call the logging function
        transport._log_response_size(mock_request, mock_response)

        # Verify logging occurred
        mock_logger.info.assert_called_once()

        # Verify that response.text can still be accessed
        assert mock_response.text == "Hello, World! This is a test response."

        # Verify that read was called and content was restored
        mock_response.read.assert_called_once()
        assert mock_response._content == text_content

    @pytest.mark.asyncio
    @patch("port_ocean.helpers.retry.cast")
    async def test_log_response_size_async_preserves_content_consumption(
        self, mock_cast: Mock
    ) -> None:
        """Test that _log_response_size_async preserves response for .content consumption."""
        mock_transport = Mock()
        mock_logger = Mock()
        mock_cast.return_value = mock_logger
        transport = RetryTransport(wrapped_transport=mock_transport, logger=mock_logger)

        mock_request = Mock()
        mock_request.method = "GET"
        mock_request.url.host = "api.example.com"

        # Create a mock response with binary content
        binary_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        mock_response = Mock()
        mock_response.headers = {}  # No Content-Length header to force content reading
        mock_response.aread = AsyncMock(return_value=binary_content)
        mock_response.content = binary_content

        # Call the async logging function
        await transport._log_response_size_async(mock_request, mock_response)

        # Verify logging occurred
        mock_logger.info.assert_called_once()

        # Verify that response.content can still be accessed
        assert mock_response.content == binary_content

        # Verify that aread was called and content was restored
        mock_response.aread.assert_called_once()
        assert mock_response._content == binary_content

    @patch("port_ocean.helpers.retry.cast")
    def test_log_response_size_error_handling_preserves_response(
        self, mock_cast: Mock
    ) -> None:
        """Test that _log_response_size error handling doesn't break response consumption."""
        mock_transport = Mock()
        mock_logger = Mock()
        mock_cast.return_value = mock_logger
        transport = RetryTransport(wrapped_transport=mock_transport, logger=mock_logger)

        mock_request = Mock()
        mock_request.method = "GET"
        mock_request.url.host = "api.example.com"

        # Create a mock response that will fail on read
        mock_response = Mock()
        mock_response.headers = {}  # No Content-Length header to force content reading
        mock_response.read.side_effect = Exception("Network error")
        mock_response.json.return_value = {"error": "handled gracefully"}

        # Call the logging function
        transport._log_response_size(mock_request, mock_response)

        # Verify error was logged
        mock_logger.error.assert_called_once_with(
            "Error getting response size: Network error"
        )

        # Verify that response.json() can still be called despite the error
        result = mock_response.json()
        assert result == {"error": "handled gracefully"}

        # Verify that read was attempted
        mock_response.read.assert_called_once()

    @pytest.mark.asyncio
    @patch("port_ocean.helpers.retry.cast")
    async def test_log_response_size_async_error_handling_preserves_response(
        self, mock_cast: Mock
    ) -> None:
        """Test that _log_response_size_async error handling doesn't break response consumption."""
        mock_transport = Mock()
        mock_logger = Mock()
        mock_cast.return_value = mock_logger
        transport = RetryTransport(wrapped_transport=mock_transport, logger=mock_logger)

        mock_request = Mock()
        mock_request.method = "GET"
        mock_request.url.host = "api.example.com"

        # Create a mock response that will fail on aread
        mock_response = Mock()
        mock_response.headers = {}  # No Content-Length header to force content reading
        mock_response.aread = AsyncMock(side_effect=Exception("Async network error"))
        mock_response.json.return_value = {"error": "handled gracefully"}

        # Call the async logging function
        await transport._log_response_size_async(mock_request, mock_response)

        # Verify error was logged
        mock_logger.error.assert_called_once_with(
            "Error getting response size: Async network error"
        )

        # Verify that response.json() can still be called despite the error
        result = mock_response.json()
        assert result == {"error": "handled gracefully"}

        # Verify that aread was attempted
        mock_response.aread.assert_called_once()
