from fastapi import APIRouter
import pytest

from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.exceptions.webhook_processor import RetryableError
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
)
from port_ocean.core.handlers.webhook.processor_manager import WebhookProcessorManager
from port_ocean.utils.signal import SignalHandler


class MockWebhookHandler(AbstractWebhookProcessor):
    """Concrete implementation for testing."""

    def __init__(
        self,
        event: WebhookEvent,
        should_fail: bool = False,
        fail_count: int = 0,
        max_retries: int = 3,
    ) -> None:
        super().__init__(event)
        self.authenticated = False
        self.validated = False
        self.handled = False
        self.should_fail = should_fail
        self.fail_count = fail_count
        self.current_fails = 0
        self.error_handler_called = False
        self.cancelled = False
        self.max_retries = max_retries

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        self.authenticated = True
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        self.validated = True
        return True

    async def handle_event(self, payload: EventPayload) -> None:
        if self.should_fail and self.current_fails < self.fail_count:
            self.current_fails += 1
            raise RetryableError("Temporary failure")
        self.handled = True

    async def cancel(self) -> None:
        self.cancelled = True

    async def on_error(self, error: Exception) -> None:
        self.error_handler_called = True
        await super().on_error(error)


@pytest.mark.skip("Skipping until fixed")
class TestAbstractWebhookHandler:
    @pytest.fixture
    def webhook_event(self) -> WebhookEvent:
        return WebhookEvent(
            trace_id="test-trace",
            payload={"test": "data"},
            headers={"content-type": "application/json"},
        )

    @pytest.fixture
    def processor_manager(self) -> WebhookProcessorManager:
        return WebhookProcessorManager(APIRouter(), SignalHandler())

    @pytest.fixture
    def processor(self, webhook_event: WebhookEvent) -> MockWebhookHandler:
        return MockWebhookHandler(webhook_event)

    async def test_successful_processing(
        self, processor: MockWebhookHandler, processor_manager: WebhookProcessorManager
    ) -> None:
        """Test successful webhook processing flow."""
        await processor_manager._process_webhook_request(processor)

        assert processor.authenticated
        assert processor.validated
        assert processor.handled
        assert not processor.error_handler_called

    async def test_retry_mechanism(
        self, webhook_event: WebhookEvent, processor_manager: WebhookProcessorManager
    ) -> None:
        """Test retry mechanism with temporary failures."""
        processor = MockWebhookHandler(webhook_event, should_fail=True, fail_count=2)

        await processor_manager._process_webhook_request(processor)

        assert processor.handled
        assert processor.current_fails == 2
        assert processor.retry_count == 2
        assert processor.error_handler_called

    async def test_max_retries_exceeded(
        self, webhook_event: WebhookEvent, processor_manager: WebhookProcessorManager
    ) -> None:
        """Test behavior when max retries are exceeded."""
        processor = MockWebhookHandler(
            webhook_event, should_fail=True, fail_count=2, max_retries=1
        )

        with pytest.raises(RetryableError):
            await processor_manager._process_webhook_request(processor)

        assert processor.retry_count == processor.max_retries
        assert processor.error_handler_called
        assert not processor.handled
