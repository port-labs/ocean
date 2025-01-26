import pytest

from port_ocean.core.handlers.webhook.abstract_webhook_handler import (
    AbstractWebhookHandler,
    RetryableError,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
)


class TestWebhookHandler(AbstractWebhookHandler):
    """Concrete implementation for testing."""

    def __init__(
        self,
        event: WebhookEvent,
        should_fail: bool = False,
        fail_count: int = 0,
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


class TestAbstractWebhookHandler:
    @pytest.fixture
    def webhook_event(self) -> WebhookEvent:
        return WebhookEvent(
            trace_id="test-trace",
            payload={"test": "data"},
            headers={"content-type": "application/json"},
        )

    @pytest.fixture
    def handler(self, webhook_event: WebhookEvent) -> TestWebhookHandler:
        return TestWebhookHandler(webhook_event)

    async def test_successful_processing(self, handler: TestWebhookHandler) -> None:
        """Test successful webhook processing flow."""
        await handler.process_request()

        assert handler.authenticated
        assert handler.validated
        assert handler.handled
        assert not handler.error_handler_called

    async def test_retry_mechanism(self, webhook_event: WebhookEvent) -> None:
        """Test retry mechanism with temporary failures."""
        handler = TestWebhookHandler(webhook_event, should_fail=True, fail_count=2)

        await handler.process_request()

        assert handler.handled
        assert handler.current_fails == 2
        assert handler.retry_count == 2
        assert handler.error_handler_called

    async def test_max_retries_exceeded(self, webhook_event: WebhookEvent) -> None:
        """Test behavior when max retries are exceeded."""
        handler = TestWebhookHandler(webhook_event, should_fail=True, fail_count=5)

        with pytest.raises(RetryableError):
            await handler.process_request()

        assert handler.retry_count == handler.max_retries
        assert handler.error_handler_called
        assert not handler.handled
