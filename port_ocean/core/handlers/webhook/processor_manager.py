from typing import Dict, Tuple, Type, Set, List

from fastapi import APIRouter, Request
from loguru import logger
import asyncio

from port_ocean.context.ocean import ocean
from port_ocean.context.event import EventType, event_context
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.queue.abstract_queue import AbstractQueue
from port_ocean.core.integrations.mixins.events import EventsMixin
from port_ocean.core.integrations.mixins.live_events import LiveEventsMixin
from port_ocean.exceptions.webhook_processor import WebhookEventNotSupportedError
from .webhook_event import WebhookEvent, WebhookEventRawResults, LiveEventTimestamp
from port_ocean.context.event import event


from .abstract_webhook_processor import AbstractWebhookProcessor
from port_ocean.utils.signal import SignalHandler
from port_ocean.core.handlers.queue import LocalQueue


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
        self._event_processor_tasks: Set[asyncio.Task[None]] = set()
        self._max_event_processing_seconds = max_event_processing_seconds
        self._max_wait_seconds_before_shutdown = max_wait_seconds_before_shutdown
        signal_handler.register(self.shutdown)

    async def start_processing_event_messages(self) -> None:
        """Start processing events for all registered paths with N workers each."""
        await self.initialize_handlers()
        loop = asyncio.get_event_loop()
        config = ocean.integration.context.config

        for path in self._event_queues.keys():
            for worker_id in range(0, config.event_workers_count):
                task = loop.create_task(self._process_webhook_events(path, worker_id))
                self._event_processor_tasks.add(task)
                task.add_done_callback(self._event_processor_tasks.discard)

    async def _process_webhook_events(self, path: str, worker_id: int) -> None:
        """Process webhook events from the queue for a given path."""
        queue = self._event_queues[path]
        while True:
            event = None
            matching_processors: List[
                Tuple[ResourceConfig, AbstractWebhookProcessor]
            ] = []
            try:
                event = await queue.get()
                with logger.contextualize(
                    worker=worker_id,
                    webhook_path=path,
                    trace_id=event.trace_id,
                ):
                    async with event_context(
                        EventType.HTTP_REQUEST,
                        trigger_type="machine",
                    ):

                        await ocean.integration.port_app_config_handler.get_port_app_config(
                            use_cache=False
                        )
                        matching_processors = await self._extract_matching_processors(
                            event, path
                        )

                        processing_results = await asyncio.gather(
                            *(
                                self._process_single_event(proc, path, res)
                                for res, proc in matching_processors
                            ),
                            return_exceptions=True,
                        )

                        successful_results: List[WebhookEventRawResults] = []
                        failed_exceptions: List[Exception] = []

                        for result in processing_results:
                            if isinstance(result, WebhookEventRawResults):
                                successful_results.append(result)
                            elif isinstance(result, Exception):
                                failed_exceptions.append(result)

                        if successful_results:
                            logger.info(
                                "Successfully processed webhook events",
                                success_count=len(successful_results),
                                failure_count=len(failed_exceptions),
                            )

                        if failed_exceptions:
                            logger.warning(
                                "Some webhook events failed processing",
                                failures=[str(e) for e in failed_exceptions],
                            )

                        await self.sync_raw_results(successful_results)

            except asyncio.CancelledError:
                logger.info(f"Worker {worker_id} for {path} shutting down")
                for _, proc in matching_processors:
                    await proc.cancel()
                    self._timestamp_event_error(proc.event)
                break
            except Exception as e:
                logger.exception(
                    f"Unexpected error in worker {worker_id} for {path}: {e}"
                )
                for _, proc in matching_processors:
                    self._timestamp_event_error(proc.event)
            finally:
                try:
                    if event is not None:
                        await queue.commit()

                except Exception as e:
                    logger.exception(
                        f"Unexpected error in queue commit in worker {worker_id} for {path}: {e}"
                    )

    async def _extract_matching_processors(
        self, webhook_event: WebhookEvent, path: str
    ) -> list[tuple[ResourceConfig, AbstractWebhookProcessor]]:
        """Find and extract the matching processor for an event"""

        created_processors: list[tuple[ResourceConfig, AbstractWebhookProcessor]] = []
        event_processor_names = []

        for processor_class in self._processors_classes[path]:
            processor = processor_class(webhook_event.clone())
            if await processor.should_process_event(webhook_event):
                event_processor_names.append(processor.__class__.__name__)
                kinds = await processor.get_matching_kinds(webhook_event)
                for kind in kinds:
                    for resource in event.port_app_config.resources:
                        if resource.kind == kind:
                            created_processors.append((resource, processor))

        if not created_processors:
            if event_processor_names:
                logger.info(
                    "Webhook processors are available to handle this webhook event, but the corresponding kinds are not configured in the integration's mapping",
                    processors_available=event_processor_names,
                    webhook_path=path,
                )
                return []
            else:
                logger.warning(
                    "Unknown webhook event type received",
                    webhook_path=path,
                    message="No processors registered to handle this webhook event type.",
                )
                raise WebhookEventNotSupportedError(
                    "No matching processors found for webhook event"
                )

        logger.info(
            "Found matching processors for webhook event",
            processors_count=len(created_processors),
            webhook_path=path,
        )
        return created_processors

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

    async def _cancel_all_event_processors(
        self,
    ) -> None:
        """Cancel all event processor tasks"""
        for task in self._event_processor_tasks:
            task.cancel()

        await asyncio.gather(*self._event_processor_tasks, return_exceptions=True)

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
