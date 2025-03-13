from typing import Dict, Type, Set
from fastapi import APIRouter, Request
from loguru import logger
import asyncio

from port_ocean.context.ocean import ocean
from port_ocean.context.event import EventType, event_context
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.integrations.mixins.events import EventsMixin
from port_ocean.core.integrations.mixins.live_events import LiveEventsMixin
from .webhook_event import WebhookEvent, WebhookEventRawResults, LiveEventTimestamp
from port_ocean.context.event import event


from .abstract_webhook_processor import AbstractWebhookProcessor
from port_ocean.utils.signal import SignalHandler
from port_ocean.core.handlers.queue import AbstractQueue, LocalQueue


class LiveEventsProcessorManager(LiveEventsMixin, EventsMixin):
    """Manages webhook processors and their routes"""

    def __init__(
        self,
        router: APIRouter,
        signal_handler: SignalHandler,
        max_event_processing_seconds: float,
        max_wait_seconds_before_shutdown: float,
    ) -> None:
        self._router = router
        self._processors_classes: Dict[str, list[Type[AbstractWebhookProcessor]]] = {}
        self._event_queues: Dict[str, AbstractQueue[WebhookEvent]] = {}
        self._webhook_processor_tasks: Set[asyncio.Task[None]] = set()
        self._max_event_processing_seconds = max_event_processing_seconds
        self._max_wait_seconds_before_shutdown = max_wait_seconds_before_shutdown
        signal_handler.register(self.shutdown)

    async def start_processing_event_messages(self) -> None:
        """Start processing events for all registered paths"""
        await self.initialize_handlers()
        loop = asyncio.get_event_loop()
        for path in self._event_queues.keys():
            try:
                task = loop.create_task(self.process_queue(path))
                self._webhook_processor_tasks.add(task)
                task.add_done_callback(self._webhook_processor_tasks.discard)
            except Exception as e:
                logger.exception(f"Error starting queue processor for {path}: {str(e)}")

    async def _extract_matching_processors(
        self, webhook_event: WebhookEvent, path: str
    ) -> list[tuple[ResourceConfig, AbstractWebhookProcessor]]:
        """Find and extract the matching processor for an event"""

        created_processors: list[tuple[ResourceConfig, AbstractWebhookProcessor]] = []

        for processor_class in self._processors_classes[path]:
            processor = processor_class(webhook_event.clone())
            if await processor.should_process_event(webhook_event):
                kinds = await processor.get_matching_kinds(webhook_event)
                for kind in kinds:
                    for resource in event.port_app_config.resources:
                        if resource.kind == kind:
                            created_processors.append((resource, processor))

        if not created_processors:
            raise ValueError("No matching processors found")

        logger.info(
            "Found matching processors for webhook event",
            processors_count=len(created_processors),
            webhook_path=path,
        )
        return created_processors

    async def process_queue(self, path: str) -> None:
        """Process events for a specific path in order"""
        while True:
            matching_processors_with_resource: list[
                tuple[ResourceConfig, AbstractWebhookProcessor]
            ] = []
            webhook_event: WebhookEvent | None = None
            try:
                queue = self._event_queues[path]
                webhook_event = await queue.get()
                with logger.contextualize(
                    webhook_path=path, trace_id=webhook_event.trace_id
                ):
                    async with event_context(
                        EventType.HTTP_REQUEST,
                        trigger_type="machine",
                    ):
                        # This forces the Processor manager to fetch the latest port app config for each event
                        await ocean.integration.port_app_config_handler.get_port_app_config(
                            use_cache=False
                        )
                        matching_processors_with_resource = (
                            await self._extract_matching_processors(webhook_event, path)
                        )
                        webhook_event_raw_results_for_all_resources = await asyncio.gather(
                            *(
                                self._process_single_event(processor, path, resource)
                                for resource, processor in matching_processors_with_resource
                            ),
                            return_exceptions=True,
                        )

                        successful_raw_results: list[WebhookEventRawResults] = [
                            result
                            for result in webhook_event_raw_results_for_all_resources
                            if isinstance(result, WebhookEventRawResults)
                        ]

                        if successful_raw_results:
                            logger.info(
                                "Exporting raw event results to entities",
                                webhook_event_raw_results_for_all_resources_length=len(
                                    successful_raw_results
                                ),
                            )
                            await self.sync_raw_results(successful_raw_results)
            except asyncio.CancelledError:
                logger.info(f"Queue processor for {path} is shutting down")
                for _, processor in matching_processors_with_resource:
                    await processor.cancel()
                    self._timestamp_event_error(processor.event)
                break
            except Exception as e:
                logger.exception(
                    f"Unexpected error in queue processor for {path}: {str(e)}"
                )
                for _, processor in matching_processors_with_resource:
                    self._timestamp_event_error(processor.event)
            finally:
                if webhook_event:
                    await self._event_queues[path].commit()
                    # Prevents committing empty events for cases where we shutdown while processing
                    webhook_event = None

    def _timestamp_event_error(self, event: WebhookEvent) -> None:
        """Timestamp an event as having an error"""
        event.set_timestamp(LiveEventTimestamp.FinishedProcessingWithError)

    async def _process_single_event(
        self, processor: AbstractWebhookProcessor, path: str, resource: ResourceConfig
    ) -> WebhookEventRawResults:
        """Process a single event with a specific processor"""
        try:
            logger.debug("Start processing queued webhook")
            processor.event.set_timestamp(LiveEventTimestamp.StartedProcessing)

            webhook_event_raw_results = await self._execute_processor(
                processor, resource
            )
            processor.event.set_timestamp(
                LiveEventTimestamp.FinishedProcessingSuccessfully
            )
            return webhook_event_raw_results
        except Exception as e:
            logger.exception(f"Error processing queued webhook for {path}: {str(e)}")
            self._timestamp_event_error(processor.event)
            raise

    async def _execute_processor(
        self, processor: AbstractWebhookProcessor, resource: ResourceConfig
    ) -> WebhookEventRawResults:
        """Execute a single processor within a max processing time"""
        try:
            return await asyncio.wait_for(
                self._process_webhook_request(processor, resource),
                timeout=self._max_event_processing_seconds,
            )
        except asyncio.TimeoutError:
            raise asyncio.TimeoutError(
                f"Processor processing timed out after {self._max_event_processing_seconds} seconds"
            )

    async def _process_webhook_request(
        self, processor: AbstractWebhookProcessor, resource: ResourceConfig
    ) -> WebhookEventRawResults:
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

        webhook_event_raw_results = None
        while True:
            try:
                webhook_event_raw_results = await processor.handle_event(
                    payload, resource
                )
                webhook_event_raw_results.resource = resource
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
        return webhook_event_raw_results

    def register_processor(
        self, path: str, processor: Type[AbstractWebhookProcessor]
    ) -> None:
        """Register a webhook processor for a specific path with optional filter

        Args:
            path: The webhook path to register
            processor: The processor class to register
            kind: The resource kind to associate with this processor, or None to match any kind
        """

        if not issubclass(processor, AbstractWebhookProcessor):
            raise ValueError("Processor must extend AbstractWebhookProcessor")

        if path not in self._processors_classes:
            self._processors_classes[path] = []
            self._event_queues[path] = LocalQueue()
            self._register_route(path)

        self._processors_classes[path].append(processor)

    def _register_route(self, path: str) -> None:
        """Register a route for a specific path"""

        async def handle_webhook(request: Request) -> Dict[str, str]:
            """Handle incoming webhook requests for a specific path."""
            try:
                webhook_event = await WebhookEvent.from_request(request)
                webhook_event.set_timestamp(LiveEventTimestamp.AddedToQueue)
                await self._event_queues[path].put(webhook_event)
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
