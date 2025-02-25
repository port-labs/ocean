import pytest
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.exceptions.webhook_processor import RetryableError


class ConcreteWebhookProcessor(AbstractWebhookProcessor):
    """Concrete implementation for testing the abstract class"""

    def __init__(self, webhook_event: WebhookEvent) -> None:
        super().__init__(webhook_event)
        self.before_processing_called = False
        self.after_processing_called = False
        self.cancel_called = False

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        return True

    async def handle_event(
        self, payload: EventPayload, resource: ResourceConfig
    ) -> WebhookEventRawResults:
        return WebhookEventRawResults(updated_raw_results=[{}], deleted_raw_results=[])

    async def should_process_event(self, webhook_event: WebhookEvent) -> bool:
        return True

    async def before_processing(self) -> None:
        await super().before_processing()
        self.before_processing_called = True

    async def after_processing(self) -> None:
        await super().after_processing()
        self.after_processing_called = True

    async def cancel(self) -> None:
        await super().cancel()
        self.cancel_called = True

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return ["test"]


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
async def test_lifecycleHooks_callsCorrectly(
    processor: ConcreteWebhookProcessor,
) -> None:
    assert not processor.before_processing_called
    assert not processor.after_processing_called
    assert not processor.cancel_called

    await processor.before_processing()
    assert processor.before_processing_called

    await processor.after_processing()
    assert processor.after_processing_called

    await processor.cancel()
    assert processor.cancel_called
