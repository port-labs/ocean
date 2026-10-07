import logging

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
    original.webhook_path = "/webhook"
    original.log_full_payload = True
    original.merge_live_event_log_identifiers({"custom": "id"})

    cloned = original.clone()

    assert cloned.trace_id == original.trace_id
    assert cloned.payload == original.payload
    assert cloned.headers == original.headers
    assert cloned._original_request == original._original_request
    assert cloned is not original
    assert cloned.webhook_path == "/webhook"
    assert cloned.log_full_payload is True
    assert cloned.live_event_log_identifiers == {"custom": "id"}


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
    """Added To Queue logs compact identifiers when payload logging is disabled."""
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload=sample_payload,
        headers=sample_headers,
        original_request=None,
    )
    event.webhook_path = "/webhook"

    record, extra = _capture_set_timestamp_record(
        event, LiveEventTimestamp.AddedToQueue
    )
    assert record.levelno == logging.INFO

    assert extra["trace_id"] == "test-trace-id"
    assert extra["timestamp_type"] == "Added To Queue"
    assert extra["webhook_path"] == "/webhook"
    assert "payload" not in extra
    assert "headers" not in extra
    assert "payload_b64" not in extra
    assert extra.get("extra") is None


def test_setTimestamp_addedToQueue_logsFullPayloadWhenBothGatesOn() -> None:
    payload = {f"key_{index}": {"nested": index} for index in range(250)}
    headers = {
        "x-github-event": "pull_request",
        "authorization": "secret",
    }
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload=payload,
        headers=headers,
        original_request=None,
    )
    event.webhook_path = "/webhook"
    event.log_full_payload = True

    record, extra = _capture_set_timestamp_record(
        event, LiveEventTimestamp.AddedToQueue
    )
    assert record.levelno == logging.DEBUG

    assert extra["trace_id"] == "test-trace-id"
    headers_logged = extra["headers"]
    assert isinstance(headers_logged, dict)
    assert headers_logged["x-github-event"] == "pull_request"
    assert headers_logged["authorization"] == "[REDACTED]"
    assert "payload" not in extra
    assert "payload_b64" in extra


def test_setTimestamp_configOnFeatureFlagOff_logsCompactOnly() -> None:
    payload = {"action": "opened", "secret": "value"}
    headers = {"x-github-event": "pull_request", "authorization": "Bearer secret"}
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload=payload,
        headers=headers,
        original_request=None,
    )
    event.webhook_path = "/webhook"
    event.log_full_payload = False

    record, extra = _capture_set_timestamp_record(
        event, LiveEventTimestamp.StartedProcessing
    )
    assert record.levelno == logging.INFO

    assert extra["timestamp_type"] == "Started Processing"
    assert "payload" not in extra
    assert extra["headers"] == {"x-github-event": "pull_request"}
    assert "payload_b64" not in extra


def _capture_set_timestamp_record(
    event: WebhookEvent, timestamp: LiveEventTimestamp
) -> tuple[LogRecord, dict[str, object]]:
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
        event.set_timestamp(timestamp)
        logger.complete()
        record = queue.get()
        assert queue.empty()
    finally:
        logger.remove(logger_id)

    extra: dict[str, object] = _serialize_record(record)["extra"]
    return record, extra


def _capture_set_timestamp_extra(
    event: WebhookEvent, timestamp: LiveEventTimestamp
) -> dict[str, object]:
    _, extra = _capture_set_timestamp_record(event, timestamp)
    return extra


def test_setTimestamp_startedProcessing_logsCompactIdentifiersByDefault(
    sample_payload: EventPayload, sample_headers: EventHeaders
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload=sample_payload,
        headers=sample_headers,
        original_request=None,
    )
    event.webhook_path = "/webhook"

    extra = _capture_set_timestamp_extra(event, LiveEventTimestamp.StartedProcessing)

    assert extra["trace_id"] == "test-trace-id"
    assert extra["timestamp_type"] == "Started Processing"
    assert extra["webhook_path"] == "/webhook"
    assert "payload" not in extra
    assert "headers" not in extra
    assert "payload_b64" not in extra


def test_setTimestamp_startedProcessing_logsProcessorSuppliedIdentifiers() -> None:
    payload = {"action": "opened", "large_field": "should-not-appear"}
    headers = {
        "x-github-event": "pull_request",
        "x-github-delivery": "delivery-id",
        "x-hub-signature-256": "sha256=secret",
    }
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload=payload,
        headers=headers,
        original_request=None,
    )
    event.webhook_path = "/webhook"
    event.merge_live_event_log_identifiers({"action": "opened", "repo": "org/repo"})

    extra = _capture_set_timestamp_extra(event, LiveEventTimestamp.StartedProcessing)

    assert extra["headers"] == {
        "x-github-event": "pull_request",
        "x-github-delivery": "delivery-id",
    }
    assert extra["payload"] == {"action": "opened", "repo": "org/repo"}


def test_setTimestamp_startedProcessing_logsFullPayloadWhenBothGatesOn() -> None:
    payload = {"action": "opened", "secret": "value"}
    headers = {
        "x-github-event": "pull_request",
        "authorization": "Bearer secret",
    }
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload=payload,
        headers=headers,
        original_request=None,
    )
    event.log_full_payload = True

    record, extra = _capture_set_timestamp_record(
        event, LiveEventTimestamp.StartedProcessing
    )
    assert record.levelno == logging.DEBUG

    assert extra["payload"] == payload
    headers_logged = extra["headers"]
    assert isinstance(headers_logged, dict)
    assert headers_logged["x-github-event"] == "pull_request"
    assert headers_logged["authorization"] == "[REDACTED]"


def test_setTimestamp_finishedProcessing_follows_same_gating_as_started() -> None:
    payload = {f"key_{index}": {"nested": index} for index in range(250)}
    headers = {"x-github-event": "pull_request", "authorization": "secret"}
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload=payload,
        headers=headers,
        original_request=None,
    )
    event.webhook_path = "/webhook"
    event.log_full_payload = True

    record, extra = _capture_set_timestamp_record(
        event, LiveEventTimestamp.FinishedProcessingSuccessfully
    )
    assert record.levelno == logging.DEBUG
    assert extra["timestamp_type"] == "Finished Processing Successfully"
    headers_logged = extra["headers"]
    assert isinstance(headers_logged, dict)
    assert headers_logged["authorization"] == "[REDACTED]"
    assert "payload" not in extra
    assert "payload_b64" in extra

    event.log_full_payload = False
    event.merge_live_event_log_identifiers({"kind": "issue"})
    record_compact, extra_compact = _capture_set_timestamp_record(
        event, LiveEventTimestamp.FinishedProcessingWithError
    )
    assert record_compact.levelno == logging.INFO
    assert extra_compact["payload"] == {"kind": "issue"}
    assert extra_compact["headers"] == {"x-github-event": "pull_request"}


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
