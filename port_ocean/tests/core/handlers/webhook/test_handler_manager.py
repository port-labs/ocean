import asyncio
import pytest
from fastapi import APIRouter
from typing import Dict, Any

from port_ocean.core.handlers.webhook.handler_manager import WebhookHandlerManager
from port_ocean.core.handlers.webhook.abstract_webhook_handler import (
    AbstractWebhookHandler,
    RetryableError,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventTimestamp,
)
from port_ocean.core.handlers.queue import LocalQueue
from port_ocean.utils.signal import SignalHandler


class MockWebhookHandler(AbstractWebhookHandler):
    def __init__(self, event: WebhookEvent) -> None:
        super().__init__(event)
        self.processed = False
        self.teardown_called = False
        self.cancel_called = False
        self.error_to_raise: Exception | asyncio.CancelledError | None = None

    async def authenticate(
        self, payload: Dict[str, Any], headers: Dict[str, str]
    ) -> bool:
        return True

    async def validate_payload(self, payload: Dict[str, Any]) -> bool:
        return True

    async def handle_event(self, payload: Dict[str, Any]) -> None:
        if self.error_to_raise:
            raise self.error_to_raise
        self.processed = True

    def teardown(self) -> None:
        self.teardown_called = True

    async def cancel(self) -> None:
        self.cancel_called = True


class RetryableHandler(MockWebhookHandler):
    def __init__(self, event: WebhookEvent) -> None:
        super().__init__(event)
        self.attempt_count = 0

    async def handle_event(self, payload: Dict[str, Any]) -> None:
        self.attempt_count += 1
        if self.attempt_count < 3:  # Succeed on third attempt
            raise RetryableError("Temporary failure")
        self.processed = True


class TestWebhookHandlerManager:
    @pytest.fixture
    def router(self) -> APIRouter:
        return APIRouter()

    @pytest.fixture
    def signal_handler(self) -> SignalHandler:
        return SignalHandler()

    @pytest.fixture
    def handler_manager(
        self, router: APIRouter, signal_handler: SignalHandler
    ) -> WebhookHandlerManager:
        return WebhookHandlerManager(router, signal_handler)

    @pytest.fixture
    def mock_event(self) -> WebhookEvent:
        return WebhookEvent.from_dict(
            {
                "payload": {"test": "data"},
                "headers": {"content-type": "application/json"},
                "trace_id": "test-trace",
            }
        )

    @staticmethod
    def assert_event_processed_successfully(event: WebhookEvent) -> None:
        """Assert that an event was processed successfully by checking its timestamp."""
        assert (
            event.get_timestamp(WebhookEventTimestamp.FinishedProcessingSuccessfully)
            is not None
        ), "Event was not processed successfully"

    @staticmethod
    def assert_event_processed_with_error(event: WebhookEvent) -> None:
        """Assert that an event was processed with an error by checking its timestamp."""
        assert (
            event.get_timestamp(WebhookEventTimestamp.FinishedProcessingWithError)
            is not None
        ), "Event did not fail as expected"

    async def test_register_handler(
        self, handler_manager: WebhookHandlerManager
    ) -> None:
        """Test registering a handler for a path."""
        handler_manager.register_handler("/test", MockWebhookHandler)
        assert "/test" in handler_manager._handlers
        assert len(handler_manager._handlers["/test"]) == 1
        assert isinstance(handler_manager._event_queues["/test"], LocalQueue)

    async def test_register_multiple_handlers_with_filters(
        self, handler_manager: WebhookHandlerManager
    ) -> None:
        """Test registering multiple handlers with different filters."""

        def filter1(e: WebhookEvent) -> bool:
            return e.payload.get("type") == "type1"

        def filter2(e: WebhookEvent) -> bool:
            return e.payload.get("type") == "type2"

        handler_manager.register_handler("/test", MockWebhookHandler, filter1)
        handler_manager.register_handler("/test", MockWebhookHandler, filter2)

        assert len(handler_manager._handlers["/test"]) == 2

    async def test_successful_event_processing(
        self, handler_manager: WebhookHandlerManager, mock_event: WebhookEvent
    ) -> None:
        """Test successful processing of an event."""
        handler_manager.register_handler("/test", MockWebhookHandler)

        # Start the processor
        await handler_manager.start_processing_event_messages()

        # Put event in queue
        await handler_manager._event_queues["/test"].put(mock_event)

        # Allow time for processing
        await asyncio.sleep(0.1)

        # Verify timestamps
        self.assert_event_processed_successfully(mock_event)

    async def test_graceful_shutdown(
        self, handler_manager: WebhookHandlerManager, mock_event: WebhookEvent
    ) -> None:
        """Test graceful shutdown with in-flight requests."""
        handler_manager.register_handler("/test", MockWebhookHandler)

        await handler_manager.start_processing_event_messages()
        await handler_manager._event_queues["/test"].put(mock_event)

        # Start shutdown
        await handler_manager.shutdown()

        # Verify all tasks are cleaned up
        assert len(handler_manager._webhook_processor_tasks) == 0
        self.assert_event_processed_successfully(mock_event)

    async def test_handler_filter_matching(
        self, handler_manager: WebhookHandlerManager
    ) -> None:
        """Test that handlers are selected based on their filters."""
        type1_event = WebhookEvent.from_dict(
            {"payload": {"type": "type1"}, "headers": {}, "trace_id": "test-trace-1"}
        )

        type2_event = WebhookEvent.from_dict(
            {"payload": {"type": "type2"}, "headers": {}, "trace_id": "test-trace-2"}
        )

        def filter1(e: WebhookEvent) -> bool:
            return e.payload.get("type") == "type1"

        def filter2(e: WebhookEvent) -> bool:
            return e.payload.get("type") == "type2"

        handler_manager.register_handler("/test", MockWebhookHandler, filter1)
        handler_manager.register_handler("/test", MockWebhookHandler, filter2)

        await handler_manager.start_processing_event_messages()

        # Process both events
        await handler_manager._event_queues["/test"].put(type1_event)
        await handler_manager._event_queues["/test"].put(type2_event)

        await asyncio.sleep(0.1)

        # Verify both events were processed
        self.assert_event_processed_successfully(type1_event)
        self.assert_event_processed_successfully(type2_event)

    async def test_handler_timeout(
        self, router: APIRouter, signal_handler: SignalHandler, mock_event: WebhookEvent
    ) -> None:
        """Test handler timeout behavior."""

        # Set a short timeout for testing
        handler_manager = WebhookHandlerManager(
            router, signal_handler, max_event_processing_seconds=0.1
        )

        class TimeoutHandler(MockWebhookHandler):
            async def handle_event(self, payload: Dict[str, Any]) -> None:
                await asyncio.sleep(2)  # Longer than max_handler_processing_seconds

        handler_manager.register_handler("/test", TimeoutHandler)
        await handler_manager.start_processing_event_messages()
        await handler_manager._event_queues["/test"].put(mock_event)

        # Wait long enough for the timeout to occur
        await asyncio.sleep(0.2)

        self.assert_event_processed_with_error(mock_event)

    async def test_handler_cancellation(
        self, handler_manager: WebhookHandlerManager, mock_event: WebhookEvent
    ) -> None:
        """Test handler cancellation during shutdown."""

        class CanceledHandler(MockWebhookHandler):
            async def handle_event(self, payload: Dict[str, Any]) -> None:
                await asyncio.sleep(0.2)

            async def cancel(self) -> None:
                self.event.payload["canceled"] = True

        handler_manager.register_handler("/test", CanceledHandler)
        await handler_manager.start_processing_event_messages()
        await handler_manager._event_queues["/test"].put(mock_event)

        await asyncio.sleep(0.1)

        # Wait for the event to be processed
        await handler_manager._cancel_all_tasks()

        # Verify the cancellation timestamp was set
        assert mock_event.payload.get("canceled") is True

    async def test_invalid_handler_registration(self) -> None:
        """Test registration of invalid handler type."""
        handler_manager = WebhookHandlerManager(APIRouter(), SignalHandler())

        with pytest.raises(ValueError):
            handler_manager.register_handler("/test", object)  # type: ignore

    async def test_no_matching_handlers(
        self, handler_manager: WebhookHandlerManager, mock_event: WebhookEvent
    ) -> None:
        """Test behavior when no handlers match the event."""
        handler_manager.register_handler("/test", MockWebhookHandler, lambda e: False)

        await handler_manager.start_processing_event_messages()
        await handler_manager._event_queues["/test"].put(mock_event)

        await asyncio.sleep(0.1)

        assert (
            mock_event.get_timestamp(WebhookEventTimestamp.FinishedProcessingWithError)
            is not None
        )

    async def test_multiple_handlers(
        self, handler_manager: WebhookHandlerManager
    ) -> None:
        # Test multiple handlers for same path
        handler_manager.register_handler("/test", MockWebhookHandler)
        handler_manager.register_handler("/test", MockWebhookHandler)
        assert len(handler_manager._handlers["/test"]) == 2
