from typing import Dict, Type, Set, Callable
from fastapi import APIRouter, Request
from loguru import logger
import asyncio
from dataclasses import dataclass

from .webhook_event import WebhookEvent, WebhookEventTimestamp


from .abstract_webhook_processor import AbstractWebhookProcessor
from port_ocean.utils.signal import SignalHandler
from port_ocean.core.handlers.queue import AbstractQueue, LocalQueue


@dataclass
class ProcessorRegistration:
    """Represents a registered processor with its filter"""

    processor: Type[AbstractWebhookProcessor]
    filter: Callable[[WebhookEvent], bool]


class WebhookProcessorManager:
    """Manages webhook processors and their routes"""

    def __init__(
        self,
        router: APIRouter,
        signal_handler: SignalHandler,
        max_event_processing_seconds: float = 90.0,
        max_wait_seconds_before_shutdown: float = 5.0,
    ) -> None:
        self._router = router
        self._processors: Dict[str, list[ProcessorRegistration]] = {}
        self._event_queues: Dict[str, AbstractQueue[WebhookEvent]] = {}
        self._webhook_processor_tasks: Set[asyncio.Task[None]] = set()
        self._max_event_processing_seconds = max_event_processing_seconds
        self._max_wait_seconds_before_shutdown = max_wait_seconds_before_shutdown
        signal_handler.register(self.shutdown)

    async def start_processing_event_messages(self) -> None:
        """Start processing events for all registered paths"""
        loop = asyncio.get_event_loop()
        for path in self._event_queues.keys():
            try:
                task = loop.create_task(self.process_queue(path))
                self._webhook_processor_tasks.add(task)
                task.add_done_callback(self._webhook_processor_tasks.discard)
            except Exception as e:
                logger.exception(f"Error starting queue processor for {path}: {str(e)}")

    def _extract_matching_processors(
        self, event: WebhookEvent, path: str
    ) -> list[AbstractWebhookProcessor]:
        """Find and extract the matching processor for an event"""
        matching_processors = [
            registration.processor
            for registration in self._processors[path]
            if registration.filter(event)
        ]

        if not matching_processors:
            raise ValueError("No matching processors found")

        created_processors: list[AbstractWebhookProcessor] = []
        for processor_class in matching_processors:
            processor = processor_class(event.clone())
            created_processors.append(processor)
        return created_processors

    async def process_queue(self, path: str) -> None:
        """Process events for a specific path in order"""
        while True:
            matching_processors: list[AbstractWebhookProcessor] = []
            event: WebhookEvent | None = None
            try:
                event = await self._event_queues[path].get()
                with logger.contextualize(webhook_path=path, trace_id=event.trace_id):
                    matching_processors = self._extract_matching_processors(event, path)
                    await asyncio.gather(
                        *(
                            self._process_single_event(processor, path)
                            for processor in matching_processors
                        )
                    )
            except asyncio.CancelledError:
                logger.info(f"Queue processor for {path} is shutting down")
                for processor in matching_processors:
                    await processor.cancel()
                    self._timestamp_event_error(processor.event)
                break
            except Exception as e:
                logger.exception(
                    f"Unexpected error in queue processor for {path}: {str(e)}"
                )
                for processor in matching_processors:
                    self._timestamp_event_error(processor.event)
            finally:
                if event:
                    await self._event_queues[path].commit()
                    # Prevents committing empty events for cases where we shutdown while processing
                    event = None

    def _timestamp_event_error(self, event: WebhookEvent) -> None:
        """Timestamp an event as having an error"""
        event.set_timestamp(WebhookEventTimestamp.FinishedProcessingWithError)

    async def _process_single_event(
        self, processor: AbstractWebhookProcessor, path: str
    ) -> None:
        """Process a single event with a specific processor"""
        try:
            logger.debug("Start processing queued webhook")
            processor.event.set_timestamp(WebhookEventTimestamp.StartedProcessing)

            await self._execute_processor(processor)
            processor.event.set_timestamp(
                WebhookEventTimestamp.FinishedProcessingSuccessfully
            )
        except Exception as e:
            logger.exception(f"Error processing queued webhook for {path}: {str(e)}")
            self._timestamp_event_error(processor.event)

    async def _execute_processor(self, processor: AbstractWebhookProcessor) -> None:
        """Execute a single processor within a max processing time"""
        try:
            await asyncio.wait_for(
                self._process_webhook_request(processor),
                timeout=self._max_event_processing_seconds,
            )
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Processor processing timed out after {self._max_event_processing_seconds} seconds"
            )

    async def _process_webhook_request(
        self, processor: AbstractWebhookProcessor
    ) -> None:
        """Process a webhook request with retry logic

        Args:
            processor: The webhook processor to use
        """
        await processor.before_processing()

        payload = processor.event.payload
        headers = processor.event.headers

        if not await processor.authenticate(payload, headers):
            raise ValueError("Authentication failed")

        if not await processor.validate_payload(payload):
            raise ValueError("Invalid payload")

        while True:
            try:
                await processor.handle_event(payload)
                break

            except Exception as e:
                await processor.on_error(e)

                if (
                    processor.should_retry(e)
                    and processor.retry_count < processor.max_retries
                ):
                    processor.retry_count += 1
                    delay = processor.calculate_retry_delay()
                    await asyncio.sleep(delay)
                    continue

                raise

        await processor.after_processing()

    def register_processor(
        self,
        path: str,
        processor: Type[AbstractWebhookProcessor],
        event_filter: Callable[[WebhookEvent], bool] = lambda _: True,
    ) -> None:
        """Register a webhook processor for a specific path with optional filter"""

        if not issubclass(processor, AbstractWebhookProcessor):
            raise ValueError("Processor must extend AbstractWebhookProcessor")

        if path not in self._processors:
            self._processors[path] = []
            self._event_queues[path] = LocalQueue()
            self._register_route(path)

        self._processors[path].append(
            ProcessorRegistration(processor=processor, filter=event_filter)
        )

    def _register_route(self, path: str) -> None:
        """Register a route for a specific path"""

        async def handle_webhook(request: Request) -> Dict[str, str]:
            """Handle incoming webhook requests for a specific path."""
            try:
                event = await WebhookEvent.from_request(request)
                event.set_timestamp(WebhookEventTimestamp.AddedToQueue)
                await self._event_queues[path].put(event)
                return {"status": "ok"}
            except Exception as e:
                logger.exception(f"Error processing webhook: {str(e)}")
                return {"status": "error", "message": str(e)}

        self._router.add_api_route(
            path,
            handle_webhook,
            methods=["POST"],
        )

    async def _cancel_all_tasks(self) -> None:
        """Cancel all webhook processor tasks"""
        for task in self._webhook_processor_tasks:
            task.cancel()

        await asyncio.gather(*self._webhook_processor_tasks, return_exceptions=True)

    async def shutdown(self) -> None:
        """Gracefully shutdown all queue processors"""
        logger.warning("Shutting down webhook processor manager")

        try:
            await asyncio.wait_for(
                asyncio.gather(
                    *(queue.teardown() for queue in self._event_queues.values())
                ),
                timeout=self._max_wait_seconds_before_shutdown,
            )
        except asyncio.TimeoutError:
            logger.warning("Shutdown timed out waiting for queues to empty")

        await self._cancel_all_tasks()
