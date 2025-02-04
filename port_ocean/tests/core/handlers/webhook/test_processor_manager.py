import asyncio
import pytest
from fastapi import APIRouter
from typing import Dict, Any

from port_ocean.exceptions.webhook_processor import RetryableError
from port_ocean.core.handlers.webhook.processor_manager import WebhookProcessorManager
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
)
from port_ocean.core.handlers.queue import LocalQueue
from port_ocean.utils.signal import SignalHandler


class MockWebhookProcessor(AbstractWebhookProcessor):
    def __init__(self, event: WebhookEvent) -> None:
        super().__init__(event)
        self.processed = False
        self.cancel_called = False
        self.error_to_raise: Exception | asyncio.CancelledError | None = None
        self.retry_count = 0
        self.max_retries = 3

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


class TestableWebhookProcessorManager(WebhookProcessorManager):
    __test__ = False

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.running_processors: list[AbstractWebhookProcessor] = []
        self.no_matching_processors: bool = False

    def _extract_matching_processors(
        self, event: WebhookEvent, path: str
    ) -> list[AbstractWebhookProcessor]:
        try:
            return super()._extract_matching_processors(event, path)
        except ValueError:
            self.no_matching_processors = True
            raise

    async def _process_single_event(
        self, processor: AbstractWebhookProcessor, path: str
    ) -> None:
        self.running_processors.append(processor)
        await super()._process_single_event(processor, path)


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
    ) -> TestableWebhookProcessorManager:
        return TestableWebhookProcessorManager(router, signal_handler)

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
    def assert_event_processed_successfully(
        processor: MockWebhookProcessor,
    ) -> None:
        """Assert that a processor's event was processed successfully"""
        assert processor.processed, "Event was not processed successfully"

    @staticmethod
    def assert_event_processed_with_error(processor: MockWebhookProcessor) -> None:
        """Assert that an event was processed with an error"""
        assert not processor.processed, "Event did not fail as expected"

    @pytest.mark.skip(reason="Temporarily ignoring this test")
    async def test_register_handler(
        self, processor_manager: TestableWebhookProcessorManager
    ) -> None:
        """Test registering a processor for a path."""
        processor_manager.register_processor("/test", MockWebhookProcessor)
        assert "/test" in processor_manager._processors
        assert len(processor_manager._processors["/test"]) == 1
        assert isinstance(processor_manager._event_queues["/test"], LocalQueue)

    @pytest.mark.skip(reason="Temporarily ignoring this test")
    async def test_register_multiple_handlers_with_filters(
        self, processor_manager: TestableWebhookProcessorManager
    ) -> None:
        """Test registering multiple processors with different filters."""

        def filter1(e: WebhookEvent) -> bool:
            return e.payload.get("type") == "type1"

        def filter2(e: WebhookEvent) -> bool:
            return e.payload.get("type") == "type2"

        processor_manager.register_processor("/test", MockWebhookProcessor, filter1)
        processor_manager.register_processor("/test", MockWebhookProcessor, filter2)

        assert len(processor_manager._processors["/test"]) == 2

    @pytest.mark.skip(reason="Temporarily ignoring this test")
    async def test_successful_event_processing(
        self,
        processor_manager: TestableWebhookProcessorManager,
        mock_event: WebhookEvent,
    ) -> None:
        """Test successful processing of an event."""
        processed_events: list[MockWebhookProcessor] = []

        class SuccessProcessor(MockWebhookProcessor):
            async def handle_event(self, payload: Dict[str, Any]) -> None:
                self.processed = True
                processed_events.append(self)

        processor_manager.register_processor("/test", SuccessProcessor)

        await processor_manager.start_processing_event_messages()
        await processor_manager._event_queues["/test"].put(mock_event)

        # Allow time for processing
        await asyncio.sleep(0.1)

        # Verify at least one processor ran and completed successfully
        assert len(processed_events) > 0
        for processor in processed_events:
            self.assert_event_processed_successfully(processor)

    @pytest.mark.skip(reason="Temporarily ignoring this test")
    async def test_graceful_shutdown(
        self,
        processor_manager: TestableWebhookProcessorManager,
        mock_event: WebhookEvent,
    ) -> None:
        """Test graceful shutdown with in-flight requests"""
        processor_manager.register_processor("/test", MockWebhookProcessor)

        await processor_manager.start_processing_event_messages()
        await processor_manager._event_queues["/test"].put(mock_event)

        # Start shutdown
        await processor_manager.shutdown()

        # Verify all tasks are cleaned up
        assert len(processor_manager._webhook_processor_tasks) == 0
        self.assert_event_processed_successfully(
            processor_manager.running_processors[0]  # type: ignore
        )

    @pytest.mark.skip(reason="Temporarily ignoring this test")
    async def test_handler_filter_matching(
        self, processor_manager: TestableWebhookProcessorManager
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
        self.assert_event_processed_successfully(
            processor_manager.running_processors[0]  # type: ignore
        )
        self.assert_event_processed_successfully(
            processor_manager.running_processors[1]  # type: ignore
        )

    @pytest.mark.skip(reason="Temporarily ignoring this test")
    async def test_handler_timeout(
        self, router: APIRouter, signal_handler: SignalHandler, mock_event: WebhookEvent
    ) -> None:
        """Test processor timeout behavior."""

        # Set a short timeout for testing
        processor_manager = TestableWebhookProcessorManager(
            router, signal_handler, max_event_processing_seconds=0.1
        )

        class TimeoutHandler(MockWebhookProcessor):
            async def handle_event(self, payload: Dict[str, Any]) -> None:
                await asyncio.sleep(2)  # Longer than max_handler_processing_seconds

        processor_manager.register_processor("/test", TimeoutHandler)
        await processor_manager.start_processing_event_messages()
        await processor_manager._event_queues["/test"].put(mock_event)

        # Wait long enough for the timeout to occur
        await asyncio.sleep(0.2)

        self.assert_event_processed_with_error(
            processor_manager.running_processors[0]  # type: ignore
        )

    @pytest.mark.skip(reason="Temporarily ignoring this test")
    async def test_handler_cancellation(
        self,
        processor_manager: TestableWebhookProcessorManager,
        mock_event: WebhookEvent,
    ) -> None:
        """Test processor cancellation during shutdown."""
        cancelled_events: list[WebhookEvent] = []

        class CanceledHandler(MockWebhookProcessor):
            async def handle_event(self, payload: Dict[str, Any]) -> None:
                await asyncio.sleep(0.2)

            async def cancel(self) -> None:
                cancelled_events.append(self.event)
                self.event.payload["canceled"] = True

        processor_manager.register_processor("/test", CanceledHandler)
        await processor_manager.start_processing_event_messages()
        await processor_manager._event_queues["/test"].put(mock_event)

        await asyncio.sleep(0.1)

        # Wait for the event to be processed
        await processor_manager._cancel_all_tasks()

        # Verify at least one event was cancelled
        assert len(cancelled_events) > 0
        assert any(event.payload.get("canceled") for event in cancelled_events)

    @pytest.mark.skip(reason="Temporarily ignoring this test")
    async def test_invalid_handler_registration(self) -> None:
        """Test registration of invalid processor type."""
        handler_manager = WebhookProcessorManager(APIRouter(), SignalHandler())

        with pytest.raises(ValueError):
            handler_manager.register_processor("/test", object)  # type: ignore

    async def test_no_matching_handlers(
        self,
        processor_manager: TestableWebhookProcessorManager,
        mock_event: WebhookEvent,
    ) -> None:
        """Test behavior when no processors match the event."""
        processor_manager.register_processor(
            "/test", MockWebhookProcessor, lambda e: False
        )

        await processor_manager.start_processing_event_messages()
        await processor_manager._event_queues["/test"].put(mock_event)

        await asyncio.sleep(0.1)

        assert processor_manager.no_matching_processors
        assert len(processor_manager.running_processors) == 0

    @pytest.mark.skip(reason="Temporarily ignoring this test")
    async def test_multiple_processors(
        self, processor_manager: TestableWebhookProcessorManager
    ) -> None:
        # Test multiple processors for same path
        processor_manager.register_processor("/test", MockWebhookProcessor)
        processor_manager.register_processor("/test", MockWebhookProcessor)
        assert len(processor_manager._processors["/test"]) == 2

    @pytest.mark.skip(reason="Temporarily ignoring this test")
    async def test_all_matching_processors_execute(
        self,
        processor_manager: TestableWebhookProcessorManager,
        mock_event: WebhookEvent,
    ) -> None:
        """Test that all matching processors are executed even if some fail."""
        processed_count = 0

        class SuccessProcessor(MockWebhookProcessor):
            async def handle_event(self, payload: Dict[str, Any]) -> None:
                nonlocal processed_count
                processed_count += 1
                self.processed = True

        class FailingProcessor(MockWebhookProcessor):
            async def handle_event(self, payload: Dict[str, Any]) -> None:
                raise Exception("Simulated failure")

        # Register mix of successful and failing processors
        processor_manager.register_processor("/test", SuccessProcessor)
        processor_manager.register_processor("/test", FailingProcessor)
        processor_manager.register_processor("/test", SuccessProcessor)

        await processor_manager.start_processing_event_messages()
        await processor_manager._event_queues["/test"].put(mock_event)

        # Wait for processing to complete
        await asyncio.sleep(0.1)

        # Verify successful processors ran despite failing one
        assert processed_count == 2

    @pytest.mark.skip(reason="Temporarily ignoring this test")
    async def test_retry_mechanism(
        self,
        processor_manager: TestableWebhookProcessorManager,
        mock_event: WebhookEvent,
    ) -> None:
        """Test retry mechanism with temporary failures."""
        processor = MockWebhookProcessor(mock_event)
        processor.error_to_raise = RetryableError("Temporary failure")

        # Simulate 2 failures before success
        async def handle_event(payload: Dict[str, Any]) -> None:
            if processor.retry_count < 2:
                raise RetryableError("Temporary failure")
            processor.processed = True

        processor.handle_event = handle_event  # type: ignore

        await processor_manager._process_webhook_request(processor)

        assert processor.processed
        assert processor.retry_count == 2

    @pytest.mark.skip(reason="Temporarily ignoring this test")
    async def test_max_retries_exceeded(
        self,
        processor_manager: TestableWebhookProcessorManager,
        mock_event: WebhookEvent,
    ) -> None:
        """Test behavior when max retries are exceeded."""
        processor = MockWebhookProcessor(mock_event)
        processor.max_retries = 1
        processor.error_to_raise = RetryableError("Temporary failure")

        with pytest.raises(RetryableError):
            await processor_manager._process_webhook_request(processor)

        assert processor.retry_count == processor.max_retries
