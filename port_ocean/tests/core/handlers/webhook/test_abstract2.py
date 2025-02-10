import pytest
from unittest.mock import AsyncMock
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
)
from port_ocean.exceptions.webhook_processor import RetryableError


class ConcreteWebhookProcessor(AbstractWebhookProcessor):
    """Concrete implementation for testing the abstract class"""

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        return True

    async def handle_event(self, payload: EventPayload) -> None:
        pass


@pytest.fixture
def webhook_event() -> WebhookEvent:
    return WebhookEvent(payload={}, headers={}, trace_id="test-trace-id")


@pytest.fixture
def processor(webhook_event: WebhookEvent) -> ConcreteWebhookProcessor:
    return ConcreteWebhookProcessor(webhook_event)


async def test_init_finishedSuccessfully(webhook_event: WebhookEvent) -> None:
    processor = ConcreteWebhookProcessor(webhook_event)
    assert processor.event == webhook_event
    assert processor.retry_count == 0


@pytest.mark.asyncio
async def test_calculateRetryDelay_delayCalculatedCorrectly(
    processor: ConcreteWebhookProcessor,
) -> None:
    assert processor.calculate_retry_delay() == 1.0

    processor.retry_count = 1
    assert processor.calculate_retry_delay() == 2.0

    processor.retry_count = 10
    assert processor.calculate_retry_delay() == 30.0


@pytest.mark.asyncio
async def test_shouldRetry_returnsTrueOnRetryableError(
    processor: ConcreteWebhookProcessor,
) -> None:
    assert processor.should_retry(RetryableError("test")) is True
    assert processor.should_retry(ValueError("test")) is False


@pytest.mark.asyncio
async def test_processData_callsOnLiveEvent(
    processor: ConcreteWebhookProcessor,
) -> None:
    mock_on_live_event = AsyncMock()
    processor.on_live_event = mock_on_live_event  # type: ignore

    test_kind = "test_kind"
    test_data = [{"id": 1}, {"id": 2}]

    await processor.process_data(test_kind, test_data)

    mock_on_live_event.assert_called_once_with(test_kind, test_data)


@pytest.mark.asyncio
async def test_lifecycle_hooks(processor: ConcreteWebhookProcessor) -> None:
    await processor.before_processing()
    await processor.after_processing()
    await processor.cancel()
