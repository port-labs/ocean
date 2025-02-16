import pytest
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

    async def test_fromRequest_createdSuccessfully(self, mock_request: Request) -> None:
        """Test creating WebhookEvent from a request."""
        event = await WebhookEvent.from_request(mock_request)

        assert event.trace_id is not None
        assert len(event.trace_id) > 0
        assert event.headers == dict(mock_request.headers)
        assert event._original_request == mock_request

    def test_fromDict_createdSuccessfully(
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

    def test_clone_createsExactCopy(
        self, sample_payload: EventPayload, sample_headers: EventHeaders
    ) -> None:
        """Test cloning a WebhookEvent creates an exact copy."""
        original = WebhookEvent(
            trace_id="test-trace-id",
            payload=sample_payload,
            headers=sample_headers,
            original_request=None,
        )

        cloned = original.clone()

        assert cloned.trace_id == original.trace_id
        assert cloned.payload == original.payload
        assert cloned.headers == original.headers
        assert cloned._original_request == original._original_request
        assert cloned is not original  # Verify it's a new instance

    def test_setTimestamp_setsTimestampCorrectly(
        self, sample_payload: EventPayload, sample_headers: EventHeaders
    ) -> None:
        """Test that setting a timestamp logs the event and stores the timestamp."""
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload=sample_payload,
            headers=sample_headers,
            original_request=None,
        )

        event.set_timestamp(WebhookEventTimestamp.StartedProcessing)
        assert event._timestamp == WebhookEventTimestamp.StartedProcessing

        event.set_timestamp(WebhookEventTimestamp.FinishedProcessingSuccessfully)
        assert event._timestamp == WebhookEventTimestamp.FinishedProcessingSuccessfully
