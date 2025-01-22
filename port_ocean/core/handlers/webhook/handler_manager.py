from typing import Dict, Type, Set, Callable
from fastapi import APIRouter, Request
from loguru import logger
import asyncio
from dataclasses import dataclass

from .webhook_event import WebhookEvent, WebhookEventTimestamp


from .abstract_webhook_handler import AbstractWebhookHandler
from port_ocean.utils.signal import SignalHandler
from port_ocean.core.handlers.queue import AbstractQueue, LocalQueue


@dataclass
class HandlerRegistration:
    """Represents a registered handler with its filter."""

    handler: Type[AbstractWebhookHandler]
    filter: Callable[[WebhookEvent], bool]


class WebhookHandlerManager:
    """Manages webhook handlers and their routes."""

    def __init__(
        self,
        router: APIRouter,
        signal_handler: SignalHandler,
        max_event_processing_seconds: float = 90.0,
        max_wait_seconds_before_shutdown: float = 5.0,
    ) -> None:
        self._router = router
        self._handlers: Dict[str, list[HandlerRegistration]] = {}
        self._event_queues: Dict[str, AbstractQueue[WebhookEvent]] = {}
        self._webhook_processor_tasks: Set[asyncio.Task[None]] = set()
        self._max_event_processing_seconds = max_event_processing_seconds
        self._max_wait_seconds_before_shutdown = max_wait_seconds_before_shutdown
        signal_handler.register(self.shutdown)

    async def start_processing_event_messages(self) -> None:
        """Start processing events for all registered paths."""
        loop = asyncio.get_event_loop()
        for path in self._event_queues.keys():
            try:
                task = loop.create_task(self.process_queue(path))
                self._webhook_processor_tasks.add(task)
                task.add_done_callback(self._webhook_processor_tasks.discard)
            except Exception as e:
                logger.exception(f"Error starting queue processor for {path}: {str(e)}")

    def _extract_matching_handler(
        self, event: WebhookEvent, path: str
    ) -> AbstractWebhookHandler:
        """Find and extract the matching handler for an event."""
        matching_handlers = [
            reg.handler for reg in self._handlers[path] if reg.filter(event)
        ]

        if not matching_handlers:
            raise ValueError("No matching handlers found")

        handler = matching_handlers[0](event)
        return handler

    async def process_queue(self, path: str) -> None:
        """Process events for a specific path in order."""
        while True:
            handler: AbstractWebhookHandler | None = None
            event: WebhookEvent | None = None
            try:
                event = await self._event_queues[path].get()
                with logger.contextualize(webhook_path=path, trace_id=event.trace_id):
                    handler = self._extract_matching_handler(event, path)
                    await self._process_single_event(handler, path)
            except asyncio.CancelledError:
                logger.info(f"Queue processor for {path} is shutting down")
                self._timestamp_event_error(event)
                if handler:
                    await handler.cancel()
                break
            except Exception as e:
                logger.exception(
                    f"Unexpected error in queue processor for {path}: {str(e)}"
                )
                self._timestamp_event_error(event)

    def _timestamp_event_error(self, event: WebhookEvent | None) -> None:
        """Timestamp an event as having an error."""
        if event:
            event.set_timestamp(WebhookEventTimestamp.FinishedProcessingWithError)

    async def _process_single_event(
        self, handler: AbstractWebhookHandler, path: str
    ) -> None:
        """Process a single event with a specific handler."""
        try:
            logger.debug("Start processing queued webhook")
            handler.event.set_timestamp(WebhookEventTimestamp.StartedProcessing)

            await self._execute_handler(handler)
            handler.event.set_timestamp(
                WebhookEventTimestamp.FinishedProcessingSuccessfully
            )
        except Exception as e:
            logger.exception(f"Error processing queued webhook for {path}: {str(e)}")
            self._timestamp_event_error(handler.event)
        finally:
            await self._event_queues[path].commit()
            if handler:
                handler.teardown()
            self._log_processing_completion(handler.event)

    async def _execute_handler(self, handler: AbstractWebhookHandler) -> None:
        """Execute a single handler within a max processing time."""
        try:
            await asyncio.wait_for(
                handler.process_request(),
                timeout=self._max_event_processing_seconds,
            )
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Handler processing timed out after {self._max_event_processing_seconds} seconds"
            )

    def _log_processing_completion(self, event: WebhookEvent) -> None:
        """Log the completion of event processing with timing information."""

        logger.debug(
            "Finished processing queued webhook",
            timestamps={
                timestamp: event.get_timestamp(timestamp)
                for timestamp in WebhookEventTimestamp
            },
        )

    def register_handler(
        self,
        path: str,
        handler: Type[AbstractWebhookHandler],
        event_filter: Callable[[WebhookEvent], bool] = lambda _: True,
    ) -> None:
        """Register a webhook handler for a specific path with optional filter."""

        if not issubclass(handler, AbstractWebhookHandler):
            raise ValueError("Handler must extend AbstractWebhookHandler")

        if path not in self._handlers:
            self._handlers[path] = []
            self._event_queues[path] = LocalQueue()
            self._register_route(path)

        self._handlers[path].append(
            HandlerRegistration(handler=handler, filter=event_filter)
        )

    def _register_route(self, path: str) -> None:
        """Register a route for a specific path."""

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
        """Cancel all webhook processor tasks."""
        for task in self._webhook_processor_tasks:
            task.cancel()

        await asyncio.gather(*self._webhook_processor_tasks, return_exceptions=True)

    async def shutdown(self) -> None:
        """Gracefully shutdown all queue processors."""
        logger.warning("Shutting down webhook handler manager")

        try:
            await asyncio.wait_for(
                asyncio.gather(
                    *(
                        queue.wait_for_all_items_to_be_complete()
                        for queue in self._event_queues.values()
                    )
                ),
                timeout=self._max_wait_seconds_before_shutdown,
            )
        except asyncio.TimeoutError:
            logger.warning("Shutdown timed out waiting for queues to empty")

        await self._cancel_all_tasks()
