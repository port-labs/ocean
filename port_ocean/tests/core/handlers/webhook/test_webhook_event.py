import pytest
from logging import LogRecord
from logging.handlers import QueueHandler
from queue import Queue

from fastapi import Request
from loguru import logger

from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    LiveEventTimestamp,
    WebhookEvent,
    WebhookRequestAdapter,
)
from port_ocean.log.handlers import _serialize_record


@pytest.fixture
def sample_payload() -> EventPayload:
    return {"test": "data", "nested": {"value": 123}}


@pytest.fixture
def sample_headers() -> EventHeaders:
    return {"content-type": "application/json", "x-test-header": "test-value"}


@pytest.fixture
def mock_request(sample_payload: EventPayload, sample_headers: EventHeaders) -> Request:
    scope = {
        "type": "http",
        "headers": [(k.encode(), v.encode()) for k, v in sample_headers.items()],
    }
    mock_request = Request(scope)
    mock_request._json = sample_payload
    return mock_request


@pytest.fixture
def webhook_event(
    sample_payload: EventPayload, sample_headers: EventHeaders
) -> WebhookEvent:
    return WebhookEvent(
        trace_id="test-trace-id",
        payload=sample_payload,
        headers=sample_headers,
    )


async def test_fromRequest_createdSuccessfully(mock_request: Request) -> None:
    """Test creating WebhookEvent from a request."""
    event = await WebhookEvent.from_request(mock_request)

    assert event.trace_id is not None
    assert len(event.trace_id) > 0
    assert event.headers == dict(mock_request.headers)
    assert event._original_request == mock_request


def test_fromDict_createdSuccessfully(
    sample_payload: EventPayload, sample_headers: EventHeaders
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
    sample_payload: EventPayload, sample_headers: EventHeaders
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
    sample_payload: EventPayload, sample_headers: EventHeaders
) -> None:
    """Test that setting a timestamp logs the event and stores the timestamp."""
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload=sample_payload,
        headers=sample_headers,
        original_request=None,
    )

    event.set_timestamp(LiveEventTimestamp.StartedProcessing)
    assert event._timestamp == LiveEventTimestamp.StartedProcessing

    event.set_timestamp(LiveEventTimestamp.FinishedProcessingSuccessfully)
    assert event._timestamp == LiveEventTimestamp.FinishedProcessingSuccessfully


def test_setTimestamp_logsTraceIdAtTopLevelExtra(
    sample_payload: EventPayload, sample_headers: EventHeaders
) -> None:
    """Added To Queue logs headers and payload on a single entry."""
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload=sample_payload,
        headers=sample_headers,
        original_request=None,
    )

    queue: Queue[LogRecord] = Queue()
    queue_handler = QueueHandler(queue)
    logger_id = logger.add(
        queue_handler,
        level="DEBUG",
        format="{message}",
        diagnose=False,
        enqueue=True,
    )
    try:
        event.set_timestamp(LiveEventTimestamp.AddedToQueue)
        logger.complete()
        record = queue.get()
        assert queue.empty()
    finally:
        logger.remove(logger_id)

    extra = _serialize_record(record)["extra"]

    assert extra["trace_id"] == "test-trace-id"
    assert extra["timestamp_type"] == "Added To Queue"
    assert extra["payload"] == sample_payload
    assert extra["headers"] == sample_headers
    assert "payload_b64" not in extra
    assert extra.get("extra") is None


def test_setTimestamp_addedToQueue_base64EncodesOversizedPayload() -> None:
    payload = {f"key_{index}": {"nested": index} for index in range(250)}
    headers = {"x-github-event": "pull_request"}
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload=payload,
        headers=headers,
        original_request=None,
    )

    queue: Queue[LogRecord] = Queue()
    queue_handler = QueueHandler(queue)
    logger_id = logger.add(
        queue_handler,
        level="DEBUG",
        format="{message}",
        diagnose=False,
        enqueue=True,
    )
    try:
        event.set_timestamp(LiveEventTimestamp.AddedToQueue)
        logger.complete()
        record = queue.get()
        assert queue.empty()
    finally:
        logger.remove(logger_id)

    extra = _serialize_record(record)["extra"]

    assert extra["trace_id"] == "test-trace-id"
    assert extra["headers"] == headers
    assert "payload" not in extra
    assert "payload_b64" in extra


class TestWebhookRequestAdapter:
    @pytest.mark.asyncio
    async def test_body_returns_raw_bytes(self) -> None:
        raw = b'{"action":"opened"}'
        adapter = WebhookRequestAdapter(raw_body=raw, headers={})
        assert await adapter.body() == raw

    @pytest.mark.asyncio
    async def test_body_is_idempotent(self) -> None:
        raw = b'{"x":1}'
        adapter = WebhookRequestAdapter(raw_body=raw, headers={})
        assert await adapter.body() == await adapter.body()

    def test_headers_accessible(self) -> None:
        headers = {
            "x-hub-signature-256": "sha256=abc",
            "content-type": "application/json",
        }
        adapter = WebhookRequestAdapter(raw_body=b"", headers=headers)
        assert adapter.headers == headers
