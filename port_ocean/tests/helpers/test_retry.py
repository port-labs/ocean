import pytest
from unittest.mock import Mock, patch
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

    @patch("port_ocean.helpers.retry.ocean")
    def test_get_content_length_no_header(self, mock_ocean: Mock) -> None:
        """Test _get_content_length returns 0 when no content-length header and streaming enabled."""
        mock_ocean.config.streaming.enabled = True
        mock_transport = Mock()
        transport = RetryTransport(wrapped_transport=mock_transport)

        mock_response = Mock()
        mock_response.headers = {}
        mock_response.num_bytes_downloaded = 0

        assert transport._get_content_length(mock_response) == 0

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

    @patch("port_ocean.helpers.retry.ocean")
    @patch("port_ocean.helpers.retry.cast")
    def test_log_response_size_without_content_length(
        self, mock_cast: Mock, mock_ocean: Mock
    ) -> None:
        """Test _log_response_size does nothing when no Content-Length header."""
        mock_ocean.config.streaming.enabled = True
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
        mock_response.num_bytes_downloaded = 0

        transport._log_response_size(mock_request, mock_response)

        mock_response.read.assert_not_called()
        mock_logger.info.assert_not_called()

    # Read error path removed since _log_response_size no longer reads body

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


class TestResponseSizeLoggingIntegration:
    """Integration tests to verify response consumption works after size logging."""

    def setup_method(self) -> None:
        """Reset global callback state before each test."""
        retry_module._RETRY_CONFIG_CALLBACK = None
        retry_module._ON_RETRY_CALLBACK = None

    @patch("port_ocean.helpers.retry.ocean")
    @patch("port_ocean.helpers.retry.cast")
    def test_log_response_size_preserves_json_consumption(
        self, mock_cast: Mock, mock_ocean: Mock
    ) -> None:
        """When no Content-Length, no logging/reading occurs; response usable."""
        mock_ocean.config.streaming.enabled = True
        mock_transport = Mock()
        mock_logger = Mock()
        mock_cast.return_value = mock_logger
        transport = RetryTransport(wrapped_transport=mock_transport, logger=mock_logger)

        mock_request = Mock()
        mock_request.method = "GET"
        mock_request.url.host = "api.example.com"

        mock_response = Mock()
        mock_response.headers = {}
        mock_response.num_bytes_downloaded = 0
        mock_response.json.return_value = {"message": "test", "data": [1, 2, 3]}

        transport._log_response_size(mock_request, mock_response)

        mock_logger.info.assert_not_called()
        result = mock_response.json()
        assert result == {"message": "test", "data": [1, 2, 3]}
        mock_response.read.assert_not_called()

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

    @patch("port_ocean.helpers.retry.ocean")
    @patch("port_ocean.helpers.retry.cast")
    def test_log_response_size_preserves_text_consumption(
        self, mock_cast: Mock, mock_ocean: Mock
    ) -> None:
        """When no Content-Length, no logging/reading; response.text still accessible."""
        mock_ocean.config.streaming.enabled = True
        mock_transport = Mock()
        mock_logger = Mock()
        mock_cast.return_value = mock_logger
        transport = RetryTransport(wrapped_transport=mock_transport, logger=mock_logger)

        mock_request = Mock()
        mock_request.method = "GET"
        mock_request.url.host = "api.example.com"

        mock_response = Mock()
        mock_response.headers = {}
        mock_response.num_bytes_downloaded = 0
        mock_response.text = "Hello, World! This is a test response."

        transport._log_response_size(mock_request, mock_response)

        mock_logger.info.assert_not_called()
        assert mock_response.text == "Hello, World! This is a test response."
        mock_response.read.assert_not_called()


class TestGetContentLength:
    """Tests for the _get_content_length method."""

    def test_get_content_length_from_header(self) -> None:
        """Test getting content length from Content-Length header."""
        mock_transport = Mock()
        transport = RetryTransport(wrapped_transport=mock_transport)

        mock_response = Mock()
        mock_response.headers = {"Content-Length": "2048"}

        result = transport._get_content_length(mock_response)
        assert result == 2048

    def test_get_content_length_lowercase_header(self) -> None:
        """Test getting content length from lowercase content-length header."""
        mock_transport = Mock()
        transport = RetryTransport(wrapped_transport=mock_transport)

        mock_response = Mock()
        mock_response.headers = {"content-length": "4096"}

        result = transport._get_content_length(mock_response)
        assert result == 4096

    @patch("port_ocean.helpers.retry.ocean")
    def test_get_content_length_from_read_when_no_header(
        self, mock_ocean: Mock
    ) -> None:
        """Test getting content length by reading response when no header and streaming disabled."""
        mock_ocean.config.streaming.enabled = False

        mock_transport = Mock()
        transport = RetryTransport(wrapped_transport=mock_transport)

        mock_response = Mock()
        mock_response.headers = {}
        mock_response.read.return_value = b"test response body"

        result = transport._get_content_length(mock_response)
        assert result == 18  # len("test response body")
        mock_response.read.assert_called_once()

    @patch("port_ocean.helpers.retry.ocean")
    def test_get_content_length_from_num_bytes_downloaded(
        self, mock_ocean: Mock
    ) -> None:
        """Test getting content length from num_bytes_downloaded when streaming enabled."""
        mock_ocean.config.streaming.enabled = True

        mock_transport = Mock()
        transport = RetryTransport(wrapped_transport=mock_transport)

        mock_response = Mock()
        mock_response.headers = {}
        mock_response.num_bytes_downloaded = 8192

        result = transport._get_content_length(mock_response)
        assert result == 8192

    @patch("port_ocean.helpers.retry.ocean")
    def test_get_content_length_returns_zero_when_nothing_available(
        self, mock_ocean: Mock
    ) -> None:
        """Test getting content length returns 0 when no data available."""
        mock_ocean.config.streaming.enabled = True

        mock_transport = Mock()
        transport = RetryTransport(wrapped_transport=mock_transport)

        mock_response = Mock()
        mock_response.headers = {}
        mock_response.num_bytes_downloaded = 0

        result = transport._get_content_length(mock_response)
        assert result == 0


class TestMonitorIntegrationInRetry:
    """Tests for monitor integration in RetryTransport."""

    def setup_method(self) -> None:
        """Reset global callback state before each test."""
        retry_module._RETRY_CONFIG_CALLBACK = None
        retry_module._ON_RETRY_CALLBACK = None

    @patch("port_ocean.helpers.retry.get_monitor")
    @patch("port_ocean.helpers.retry.cast")
    def test_log_response_size_records_to_monitor(
        self, mock_cast: Mock, mock_get_monitor: Mock
    ) -> None:
        """Test that _log_response_size records size to monitor when tracking is active."""
        mock_logger = Mock()
        mock_cast.return_value = mock_logger

        mock_monitor = Mock()
        mock_monitor.current_tracking_kind = "test-kind-0"
        mock_get_monitor.return_value = mock_monitor

        mock_transport = Mock()
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

        mock_get_monitor.assert_called_once()
        mock_monitor.record_response_size.assert_called_once_with(1024)

    @patch("port_ocean.helpers.retry.get_monitor")
    @patch("port_ocean.helpers.retry.cast")
    def test_log_response_size_logs_debug_when_no_tracking(
        self, mock_cast: Mock, mock_get_monitor: Mock
    ) -> None:
        """Test that _log_response_size logs debug when no tracking is active."""
        mock_logger = Mock()
        mock_cast.return_value = mock_logger

        mock_monitor = Mock()
        mock_monitor.current_tracking_kind = None
        mock_get_monitor.return_value = mock_monitor

        mock_transport = Mock()
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

        mock_monitor.record_response_size.assert_not_called()
        # Should log debug message about no active tracking
        mock_logger.debug.assert_called()

    @patch("port_ocean.helpers.retry.get_monitor")
    @patch("port_ocean.helpers.retry.cast")
    def test_log_response_size_handles_monitor_exception(
        self, mock_cast: Mock, mock_get_monitor: Mock
    ) -> None:
        """Test that _log_response_size handles monitor exceptions gracefully."""
        mock_logger = Mock()
        mock_cast.return_value = mock_logger

        mock_get_monitor.side_effect = Exception("Monitor error")

        mock_transport = Mock()
        transport = RetryTransport(wrapped_transport=mock_transport, logger=mock_logger)

        mock_request = Mock()
        mock_request.method = "GET"
        mock_url = Mock()
        mock_url.host = "api.example.com"
        mock_url.configure_mock(__str__=lambda self: "https://api.example.com/data")
        mock_request.url = mock_url

        mock_response = Mock()
        mock_response.headers = {"Content-Length": "1024"}

        # Should not raise exception
        transport._log_response_size(mock_request, mock_response)

        # Should log debug about error
        mock_logger.debug.assert_called()

    @patch("port_ocean.helpers.retry.get_monitor")
    @patch("port_ocean.helpers.retry.cast")
    def test_log_response_size_skips_zero_content_length(
        self, mock_cast: Mock, mock_get_monitor: Mock
    ) -> None:
        """Test that _log_response_size skips recording when content length is 0."""
        mock_logger = Mock()
        mock_cast.return_value = mock_logger

        mock_monitor = Mock()
        mock_monitor.current_tracking_kind = "test-kind-0"
        mock_get_monitor.return_value = mock_monitor

        mock_transport = Mock()
        transport = RetryTransport(wrapped_transport=mock_transport, logger=mock_logger)

        mock_request = Mock()
        mock_request.method = "GET"
        mock_url = Mock()
        mock_url.host = "api.example.com"
        mock_request.url = mock_url

        mock_response = Mock()
        mock_response.headers = {}  # No Content-Length
        mock_response.num_bytes_downloaded = 0

        with patch("port_ocean.helpers.retry.ocean") as mock_ocean:
            mock_ocean.config.streaming.enabled = True
            transport._log_response_size(mock_request, mock_response)

        # Should not call monitor when content length is 0
        mock_get_monitor.assert_not_called()
