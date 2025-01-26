import asyncio
import pytest
from fastapi import APIRouter
from typing import Dict, Any

from port_ocean.core.handlers.webhook.processor_manager import WebhookProcessorManager
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
    RetryableError,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventTimestamp,
)
from port_ocean.core.handlers.queue import LocalQueue
from port_ocean.utils.signal import SignalHandler


class MockWebhookProcessor(AbstractWebhookProcessor):
    def __init__(self, event: WebhookEvent) -> None:
        super().__init__(event)
        self.processed = False
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

    async def cancel(self) -> None:
        self.cancel_called = True


class RetryableProcessor(MockWebhookProcessor):
    def __init__(self, event: WebhookEvent) -> None:
        super().__init__(event)
        self.attempt_count = 0

    async def handle_event(self, payload: Dict[str, Any]) -> None:
        self.attempt_count += 1
        if self.attempt_count < 3:  # Succeed on third attempt
            raise RetryableError("Temporary failure")
        self.processed = True


class TestWebhookProcessorManager:
    @pytest.fixture
    def router(self) -> APIRouter:
        return APIRouter()

    @pytest.fixture
    def signal_handler(self) -> SignalHandler:
        return SignalHandler()

    @pytest.fixture
    def processor_manager(
        self, router: APIRouter, signal_handler: SignalHandler
    ) -> WebhookProcessorManager:
        return WebhookProcessorManager(router, signal_handler)

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
        self, processor_manager: WebhookProcessorManager
    ) -> None:
        """Test registering a processor for a path."""
        processor_manager.register_processor("/test", MockWebhookProcessor)
        assert "/test" in processor_manager._processors
        assert len(processor_manager._processors["/test"]) == 1
        assert isinstance(processor_manager._event_queues["/test"], LocalQueue)

    async def test_register_multiple_handlers_with_filters(
        self, processor_manager: WebhookProcessorManager
    ) -> None:
        """Test registering multiple processors with different filters."""

        def filter1(e: WebhookEvent) -> bool:
            return e.payload.get("type") == "type1"

        def filter2(e: WebhookEvent) -> bool:
            return e.payload.get("type") == "type2"

        processor_manager.register_processor("/test", MockWebhookProcessor, filter1)
        processor_manager.register_processor("/test", MockWebhookProcessor, filter2)

        assert len(processor_manager._processors["/test"]) == 2

    async def test_successful_event_processing(
        self, processor_manager: WebhookProcessorManager, mock_event: WebhookEvent
    ) -> None:
        """Test successful processing of an event."""
        processor_manager.register_processor("/test", MockWebhookProcessor)

        # Start the processor
        await processor_manager.start_processing_event_messages()

        # Put event in queue
        await processor_manager._event_queues["/test"].put(mock_event)

        # Allow time for processing
        await asyncio.sleep(0.1)

        # Verify timestamps
        self.assert_event_processed_successfully(mock_event)

    async def test_graceful_shutdown(
        self, processor_manager: WebhookProcessorManager, mock_event: WebhookEvent
    ) -> None:
        """Test graceful shutdown with in-flight requests."""
        processor_manager.register_processor("/test", MockWebhookProcessor)

        await processor_manager.start_processing_event_messages()
        await processor_manager._event_queues["/test"].put(mock_event)

        # Start shutdown
        await processor_manager.shutdown()

        # Verify all tasks are cleaned up
        assert len(processor_manager._webhook_processor_tasks) == 0
        self.assert_event_processed_successfully(mock_event)

    async def test_handler_filter_matching(
        self, processor_manager: WebhookProcessorManager
    ) -> None:
        """Test that processors are selected based on their filters."""
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

        processor_manager.register_processor("/test", MockWebhookProcessor, filter1)
        processor_manager.register_processor("/test", MockWebhookProcessor, filter2)

        await processor_manager.start_processing_event_messages()

        # Process both events
        await processor_manager._event_queues["/test"].put(type1_event)
        await processor_manager._event_queues["/test"].put(type2_event)

        await asyncio.sleep(0.1)

        # Verify both events were processed
        self.assert_event_processed_successfully(type1_event)
        self.assert_event_processed_successfully(type2_event)

    async def test_handler_timeout(
        self, router: APIRouter, signal_handler: SignalHandler, mock_event: WebhookEvent
    ) -> None:
        """Test processor timeout behavior."""

        # Set a short timeout for testing
        handler_manager = WebhookProcessorManager(
            router, signal_handler, max_event_processing_seconds=0.1
        )

        class TimeoutHandler(MockWebhookProcessor):
            async def handle_event(self, payload: Dict[str, Any]) -> None:
                await asyncio.sleep(2)  # Longer than max_handler_processing_seconds

        handler_manager.register_processor("/test", TimeoutHandler)
        await handler_manager.start_processing_event_messages()
        await handler_manager._event_queues["/test"].put(mock_event)

        # Wait long enough for the timeout to occur
        await asyncio.sleep(0.2)

        self.assert_event_processed_with_error(mock_event)

    async def test_handler_cancellation(
        self, processor_manager: WebhookProcessorManager, mock_event: WebhookEvent
    ) -> None:
        """Test processor cancellation during shutdown."""

        class CanceledHandler(MockWebhookProcessor):
            async def handle_event(self, payload: Dict[str, Any]) -> None:
                await asyncio.sleep(0.2)

            async def cancel(self) -> None:
                self.event.payload["canceled"] = True

        processor_manager.register_processor("/test", CanceledHandler)
        await processor_manager.start_processing_event_messages()
        await processor_manager._event_queues["/test"].put(mock_event)

        await asyncio.sleep(0.1)

        # Wait for the event to be processed
        await processor_manager._cancel_all_tasks()

        # Verify the cancellation timestamp was set
        assert mock_event.payload.get("canceled") is True

    async def test_invalid_handler_registration(self) -> None:
        """Test registration of invalid processor type."""
        handler_manager = WebhookProcessorManager(APIRouter(), SignalHandler())

        with pytest.raises(ValueError):
            handler_manager.register_processor("/test", object)  # type: ignore

    async def test_no_matching_handlers(
        self, processor_manager: WebhookProcessorManager, mock_event: WebhookEvent
    ) -> None:
        """Test behavior when no processors match the event."""
        processor_manager.register_processor(
            "/test", MockWebhookProcessor, lambda e: False
        )

        await processor_manager.start_processing_event_messages()
        await processor_manager._event_queues["/test"].put(mock_event)

        await asyncio.sleep(0.1)

        assert (
            mock_event.get_timestamp(WebhookEventTimestamp.FinishedProcessingWithError)
            is not None
        )

    async def test_multiple_processors(
        self, processor_manager: WebhookProcessorManager
    ) -> None:
        # Test multiple processors for same path
        processor_manager.register_processor("/test", MockWebhookProcessor)
        processor_manager.register_processor("/test", MockWebhookProcessor)
        assert len(processor_manager._processors["/test"]) == 2
