import pytest
from unittest.mock import Mock
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
