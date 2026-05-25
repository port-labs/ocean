import copy
from typing import Dict, Optional, Tuple, Type, Set, List

from fastapi import APIRouter, Request
from loguru import logger
import asyncio
import base64
import json

from port_ocean.context.ocean import ocean
from port_ocean.context.event import EventType, event_context
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.queue.abstract_queue import AbstractQueue
from port_ocean.core.integrations.mixins.events import EventsMixin
from port_ocean.core.integrations.mixins.live_events import LiveEventsMixin
from port_ocean.exceptions.webhook_processor import WebhookEventNotSupportedError
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
    LiveEventTimestamp,
)
from port_ocean.core.handlers.webhook.dead_letter_queue import (
    DiskBackedDeadLetterQueue,
    DLQEntry,
)
from port_ocean.config.settings import WebhookDeadLetterQueueSettings
from port_ocean.core.models import ProcessExecutionMode
from port_ocean.context.event import event
from port_ocean.log.sensetive import sensitive_log_filter

from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
    WebhookProcessorType,
)
from port_ocean.utils.signal import SignalHandler
from port_ocean.core.handlers.queue import LocalQueue

# Cap JSON UTF-8 size before base64 when logging under events_debug_logging (1 MiB).
_WEBHOOK_DEBUG_LOG_MAX_JSON_UTF8_BYTES = 1024 * 1024


def _truncate_utf8_bytes_for_webhook_debug_log(data: bytes, max_len: int) -> bytes:
    """Truncate UTF-8 for webhook debug log lines without splitting a code point."""
    if len(data) <= max_len:
        return data
    truncated = data[:max_len]
    while truncated and (truncated[-1] & 0b11000000) == 0b10000000:
        truncated = truncated[:-1]
    return truncated


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
        self._dlqs: Dict[str, DiskBackedDeadLetterQueue] = {}
        self._pending_get_tasks: Dict[Tuple[str, int], asyncio.Task[WebhookEvent]] = {}
        signal_handler.register(self.shutdown)

    def _dlq_settings(self) -> Optional[WebhookDeadLetterQueueSettings]:
        dlq = ocean.integration.context.config.webhook_dlq
        return dlq if dlq.enabled else None

    def _ensure_dlq(self, path: str) -> Optional[DiskBackedDeadLetterQueue]:
        dlq = self._dlqs.get(path)
        if dlq is not None:
            return dlq
        settings = self._dlq_settings()
        if settings is None:
            return None
        if (
            ocean.integration.context.config.process_execution_mode
            == ProcessExecutionMode.multi_process
        ):
            logger.warning(
                "Webhook DLQ is enabled with multi_process execution mode; "
                "separate processes sharing the same storage_path will collide. "
                "Use a process-unique storage_path or switch to single_process.",
                webhook_path=path,
                storage_path=settings.storage_path,
            )
        dlq = DiskBackedDeadLetterQueue(
            path=path,
            storage_path=settings.storage_path,
            max_age_seconds=settings.max_age_seconds,
            initial_backoff_seconds=settings.initial_backoff_seconds,
            max_backoff_seconds=settings.max_backoff_seconds,
            backoff_multiplier=settings.backoff_multiplier,
            max_entries=settings.max_entries,
        )
        self._dlqs[path] = dlq
        return dlq

    async def start_processing_event_messages(self) -> None:
        """Start processing events for all registered paths with N workers each."""
        await self.initialize_handlers()
        loop = asyncio.get_event_loop()
        config = ocean.integration.context.config

        for path in self._event_queues.keys():
            self._ensure_dlq(path)
            for worker_id in range(0, config.event_workers_count):
                task = loop.create_task(self._process_webhook_events(path, worker_id))
                self._event_processor_tasks.add(task)
                task.add_done_callback(self._event_processor_tasks.discard)

    async def _next_event(
        self, path: str, worker_id: int
    ) -> Tuple[WebhookEvent, Optional[DLQEntry]]:
        """Return the next event to process. Ready DLQ replays take priority over the main queue."""
        queue = self._event_queues[path]
        key = (path, worker_id)
        while True:
            dlq = self._dlqs.get(path)
            if dlq is not None:
                ready = await dlq.try_pop_ready()
                if ready is not None:
                    return ready.event, ready

            # If a prior wait_for timed out while get_task already completed,
            # we MUST consume its result here — asyncio.Queue.get() doesn't
            # undo on cancel, so dropping it would lose the event.
            get_task = self._pending_get_tasks.get(key)
            if get_task is None or get_task.done():
                if get_task is not None and get_task.done():
                    try:
                        event_obj = get_task.result()
                        self._pending_get_tasks.pop(key, None)
                        return event_obj, None
                    except BaseException:
                        self._pending_get_tasks.pop(key, None)
                get_task = asyncio.ensure_future(queue.get())
                self._pending_get_tasks[key] = get_task

            wait_seconds = (
                await dlq.seconds_until_next_ready() if dlq is not None else None
            )

            if wait_seconds is None:
                event_obj = await asyncio.shield(get_task)
                self._pending_get_tasks.pop(key, None)
                return event_obj, None

            try:
                event_obj = await asyncio.wait_for(
                    asyncio.shield(get_task), timeout=max(wait_seconds, 0.001)
                )
                self._pending_get_tasks.pop(key, None)
                return event_obj, None
            except asyncio.TimeoutError:
                continue

    async def _process_webhook_events(self, path: str, worker_id: int) -> None:
        """Process webhook events from the queue for a given path."""
        queue = self._event_queues[path]
        while True:
            event = None
            dlq_entry: Optional[DLQEntry] = None
            matching_processors: List[
                Tuple[ResourceConfig | None, AbstractWebhookProcessor, int | None]
            ] = []
            try:
                event, dlq_entry = await self._next_event(path, worker_id)
                with logger.contextualize(
                    worker=worker_id,
                    webhook_path=path,
                    trace_id=event.trace_id,
                    dlq_replay=dlq_entry is not None,
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
                                self._process_single_event(
                                    proc, path, res, resource_index
                                )
                                for res, proc, resource_index in matching_processors
                            ),
                            return_exceptions=True,
                        )

                        successful_results: List[WebhookEventRawResults] = []
                        failed_exceptions: List[Exception] = []
                        dlq_eligible_error: Optional[Exception] = None

                        for (_, proc, _), result in zip(
                            matching_processors, processing_results
                        ):
                            if isinstance(result, WebhookEventRawResults):
                                successful_results.append(result)
                            elif isinstance(result, Exception):
                                failed_exceptions.append(result)
                                if (
                                    dlq_eligible_error is None
                                    and proc.should_dead_letter(result)
                                ):
                                    dlq_eligible_error = result

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

                        await self._handle_dlq_outcome(
                            path,
                            event,
                            dlq_entry,
                            dlq_eligible_error,
                            bool(failed_exceptions),
                        )

            except asyncio.CancelledError:
                logger.info(f"Worker {worker_id} for {path} shutting down")
                for _, proc, _ in matching_processors:
                    await proc.cancel()
                    self._timestamp_event_error(proc.event)
                if dlq_entry is not None:
                    dlq = self._dlqs.get(path)
                    if dlq is not None:
                        await dlq.release_in_flight(dlq_entry.trace_id)
                break
            except Exception as e:
                logger.exception(
                    f"Unexpected error in worker {worker_id} for {path}: {e}"
                )
                for _, proc, _ in matching_processors:
                    self._timestamp_event_error(proc.event)
                if dlq_entry is not None:
                    dlq = self._dlqs.get(path)
                    if dlq is not None:
                        await dlq.release_in_flight(dlq_entry.trace_id)
            finally:
                try:
                    if event is not None and dlq_entry is None:
                        await queue.commit()

                except Exception as e:
                    logger.exception(
                        f"Unexpected error in queue commit in worker {worker_id} for {path}: {e}"
                    )

    async def _handle_dlq_outcome(
        self,
        path: str,
        event: WebhookEvent,
        dlq_entry: Optional[DLQEntry],
        dlq_eligible_error: Optional[Exception],
        any_failure: bool,
    ) -> None:
        dlq = self._dlqs.get(path)
        if dlq is None:
            return
        try:
            if dlq_entry is not None:
                if any_failure:
                    err = dlq_eligible_error or Exception("DLQ replay failed")
                    await dlq.add(event, f"{type(err).__name__}: {err}")
                else:
                    await dlq.mark_succeeded(dlq_entry.trace_id)
                return
            if dlq_eligible_error is not None:
                await dlq.add(
                    event,
                    f"{type(dlq_eligible_error).__name__}: {dlq_eligible_error}",
                )
        except Exception as e:
            logger.exception(
                "DLQ outcome handling failed",
                webhook_path=path,
                trace_id=event.trace_id,
                error=str(e),
            )

    async def _extract_matching_processors(
        self, webhook_event: WebhookEvent, path: str
    ) -> list[tuple[ResourceConfig | None, AbstractWebhookProcessor, int | None]]:
        """Find and extract the matching processor for an event"""

        created_processors: list[
            tuple[ResourceConfig | None, AbstractWebhookProcessor, int | None]
        ] = []
        event_processor_names = []

        for processor_class in self._processors_classes[path]:
            processor = processor_class(webhook_event.clone())
            if await processor.should_process_event(webhook_event):
                event_processor_names.append(processor.__class__.__name__)
                if processor.get_processor_type() == WebhookProcessorType.ACTION:
                    created_processors.append((None, processor, None))
                    continue

                kinds = await processor.get_matching_kinds(webhook_event)
                for kind in kinds:
                    for resource_index, resource in enumerate(
                        event.port_app_config.resources
                    ):
                        if resource.kind == kind:
                            created_processors.append(
                                (resource, processor, resource_index)
                            )

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
        self,
        processor: AbstractWebhookProcessor,
        path: str,
        resource: ResourceConfig | None,
        resource_index: int | None = None,
    ) -> WebhookEventRawResults:
        """Process a single event with a specific processor"""
        try:
            logger.debug("Start processing queued webhook")
            processor.event.set_timestamp(LiveEventTimestamp.StartedProcessing)

            webhook_event_raw_results = await self._execute_processor(
                processor, resource, resource_index
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
        self,
        processor: AbstractWebhookProcessor,
        resource: ResourceConfig | None,
        resource_index: int | None = None,
    ) -> WebhookEventRawResults:
        """Execute a single processor within a max processing time"""
        try:
            return await asyncio.wait_for(
                self._process_webhook_request(processor, resource, resource_index),
                timeout=self._max_event_processing_seconds,
            )
        except asyncio.TimeoutError:
            raise asyncio.TimeoutError(
                f"Processor processing timed out after {self._max_event_processing_seconds} seconds"
            )

    async def _process_webhook_request(
        self,
        processor: AbstractWebhookProcessor,
        resource: ResourceConfig | None,
        resource_index: int | None = None,
    ) -> WebhookEventRawResults:
        """Process a webhook request with retry logic

        Args:
            processor: The webhook processor to use
        """
        await processor.before_processing()

        payload = processor.event.payload
        headers = processor.event.headers
        # Capture immutable copy of original payload before any processing
        original_payload = copy.deepcopy(payload)

        if not await processor.authenticate(payload, headers):
            raise ValueError("Authentication failed")

        if not await processor.validate_payload(payload):
            raise ValueError("Invalid payload")

        webhook_event_raw_results = None
        while True:
            try:
                webhook_event_raw_results = await processor.handle_event(
                    payload, resource  # type: ignore[arg-type]
                )
                if resource is not None:
                    webhook_event_raw_results.resource = resource
                    webhook_event_raw_results.resource_index = resource_index
                webhook_event_raw_results._webhook_trace_id = processor.event.trace_id
                webhook_event_raw_results._created_at = processor.event.created_at
                webhook_event_raw_results.original_webhook = original_payload
                webhook_event_raw_results.original_headers = headers
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
        self,
        path: str,
        processor: Type[AbstractWebhookProcessor],
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
            if self._event_processor_tasks:
                self._ensure_dlq(path)

        self._processors_classes[path].append(processor)

    def _register_route(self, path: str) -> None:
        """Register a route for a specific path"""

        async def handle_webhook(request: Request) -> Dict[str, str]:
            """Handle incoming webhook requests for a specific path."""
            try:
                webhook_event = await WebhookEvent.from_request(request)
                webhook_event.set_timestamp(LiveEventTimestamp.AddedToQueue)
                if ocean.config.events_debug_logging:
                    self._log_webhook_event(webhook_event)
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

    def _log_webhook_event(self, webhook_event: WebhookEvent) -> None:
        """Log a webhook event"""
        try:
            webhook_event_masked = sensitive_log_filter.mask_object(
                webhook_event.payload, full_hide=True
            )
            json_bytes = json.dumps(webhook_event_masked).encode("utf-8")
            payload_truncated = len(json_bytes) > _WEBHOOK_DEBUG_LOG_MAX_JSON_UTF8_BYTES
            json_bytes = _truncate_utf8_bytes_for_webhook_debug_log(
                json_bytes, _WEBHOOK_DEBUG_LOG_MAX_JSON_UTF8_BYTES
            )
            base64_payload = base64.b64encode(json_bytes).decode("utf-8")
            log_kwargs: Dict[str, str | bool] = {
                "base64_masked_webhook_debug_payload": base64_payload,
                "trace_id": webhook_event.trace_id,
            }
            if payload_truncated:
                log_kwargs["webhook_debug_log_json_truncated"] = True
            logger.info("Got webhook event", **log_kwargs)
        except Exception as e:
            logger.error("Error logging webhook event", error=str(e))

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

        for task in self._pending_get_tasks.values():
            task.cancel()
        self._pending_get_tasks.clear()

        try:
            await asyncio.wait_for(
                asyncio.gather(
                    *(queue.teardown() for queue in self._event_queues.values())
                ),
                timeout=self._max_wait_seconds_before_shutdown,
            )
        except asyncio.TimeoutError:
            logger.warning("Shutdown timed out waiting for queues to empty")
