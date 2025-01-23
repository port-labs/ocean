import pytest
from datetime import datetime
from fastapi import Request
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
    WebhookEventTimestamp,
)


class TestWebhookEvent:
    @pytest.fixture
    def sample_payload(self) -> EventPayload:
        return {"test": "data", "nested": {"value": 123}}

    @pytest.fixture
    def sample_headers(self) -> EventHeaders:
        return {"content-type": "application/json", "x-test-header": "test-value"}

    @pytest.fixture
    def mock_request(
        self, sample_payload: EventPayload, sample_headers: EventHeaders
    ) -> Request:
        scope = {
            "type": "http",
            "headers": [(k.encode(), v.encode()) for k, v in sample_headers.items()],
        }
        mock_request = Request(scope)
        mock_request._json = sample_payload
        return mock_request

    @pytest.fixture
    def webhook_event(
        self, sample_payload: EventPayload, sample_headers: EventHeaders
    ) -> WebhookEvent:
        return WebhookEvent(
            trace_id="test-trace-id",
            payload=sample_payload,
            headers=sample_headers,
        )

    async def test_create_from_request(self, mock_request: Request) -> None:
        """Test creating WebhookEvent from a request."""
        event = await WebhookEvent.from_request(mock_request)

        assert event.trace_id is not None
        assert len(event.trace_id) > 0
        assert event.headers == dict(mock_request.headers)
        assert event._original_request == mock_request

    def test_create_from_dict(
        self, sample_payload: EventPayload, sample_headers: EventHeaders
    ) -> None:
        """Test creating WebhookEvent from a dictionary."""
        data = {
            "trace_id": "test-trace-id",
            "payload": sample_payload,
            "headers": sample_headers,
        }

        event = WebhookEvent.from_dict(data)

        assert event.trace_id == "test-trace-id"
        assert event.payload == sample_payload
        assert event.headers == sample_headers
        assert event._original_request is None
        assert event._timestamps == {}

    def test_set_timestamp(self, webhook_event: WebhookEvent) -> None:
        """Test setting timestamps."""
        webhook_event.set_timestamp(WebhookEventTimestamp.AddedToQueue)

        timestamp = webhook_event.get_timestamp(WebhookEventTimestamp.AddedToQueue)
        assert isinstance(timestamp, datetime)
        assert timestamp <= datetime.now()

    def test_set_duplicate_timestamp(self, webhook_event: WebhookEvent) -> None:
        """Test that setting the same timestamp twice raises an error."""
        webhook_event.set_timestamp(WebhookEventTimestamp.AddedToQueue)

        with pytest.raises(ValueError) as exc_info:
            webhook_event.set_timestamp(WebhookEventTimestamp.AddedToQueue)

        assert "Timestamp AddedToQueue already set" in str(exc_info.value)

    def test_get_nonexistent_timestamp(self, webhook_event: WebhookEvent) -> None:
        """Test getting a timestamp that hasn't been set."""
        timestamp = webhook_event.get_timestamp(WebhookEventTimestamp.StartedProcessing)
        assert timestamp is None
