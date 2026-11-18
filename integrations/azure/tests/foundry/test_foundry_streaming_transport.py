from unittest.mock import MagicMock

from azure_integration.foundry.clients.http.retry_transport import (
    FoundryRetryTransport,
    FoundryStreamingTransport,
)


def _transport(cls: type) -> FoundryRetryTransport:
    return cls(wrapped_transport=MagicMock())


def test_streaming_transport_always_reports_streaming_enabled() -> None:
    assert _transport(FoundryStreamingTransport)._is_streaming_enabled() is True


def test_streaming_transport_skips_prefetch_without_content_length() -> None:
    transport = _transport(FoundryStreamingTransport)
    request = MagicMock()
    response = MagicMock()
    response.headers = {}
    assert transport._should_prefetch_body_for_retry(request, response) is False


def test_regular_transport_prefetches_chunked_when_streaming_disabled() -> None:
    transport = _transport(FoundryRetryTransport)
    transport._is_streaming_enabled = MagicMock(return_value=False)  # type: ignore[method-assign]
    request = MagicMock()
    response = MagicMock()
    response.headers = {}
    assert transport._should_prefetch_body_for_retry(request, response) is True
