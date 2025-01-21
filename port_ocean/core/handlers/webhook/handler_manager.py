from typing import Dict, Type, Set, Callable
from fastapi import APIRouter, Request
from loguru import logger
import asyncio
from dataclasses import dataclass

from .webhook_event import WebhookEvent, WebhookEventTimestamp


from .abstract_webhook_handler import AbstractWebhookHandler
from port_ocean.utils.signal import signal_handler
from port_ocean.core.handlers.queue import AbstractQueue, LocalQueue


MAX_HANDLER_PROCESSING_SECONDS = 90.0
MAX_WAIT_SECONDS_BEFORE_SHUTDOWN = 5.0


@dataclass
class HandlerRegistration:
    """Represents a registered handler with its filter."""

    handler: Type[AbstractWebhookHandler]
    filter: Callable[[WebhookEvent], bool]


class WebhookHandlerManager:
    """Manages webhook handlers and their routes."""

    def __init__(self, router: APIRouter) -> None:
        self._router = router
        self._handlers: Dict[str, list[HandlerRegistration]] = {}
        self._event_queues: Dict[str, AbstractQueue[WebhookEvent]] = {}
        self._webhook_processor_tasks: Set[asyncio.Task[None]] = set()
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

    async def process_queue(self, path: str) -> None:
        """Process events for a specific path in order."""
        while True:
            handler: AbstractWebhookHandler | None = None
            try:
                event = await self._event_queues[path].get()
                with logger.contextualize(webhook_path=path, trace_id=event.trace_id):
                    handler = await self._process_single_event(path, event)
            except asyncio.CancelledError:
                logger.info(f"Queue processor for {path} is shutting down")
                if handler:
                    await handler.cancel()
                break
            except Exception as e:
                logger.exception(
                    f"Unexpected error in queue processor for {path}: {str(e)}"
                )

    async def _process_single_event(
        self, path: str, event: WebhookEvent
    ) -> AbstractWebhookHandler | None:
        """Process a single webhook event and return the handler if one was created."""
        handler: AbstractWebhookHandler | None = None
        try:
            logger.debug("Start processing queued webhook")
            event.set_timestamp(WebhookEventTimestamp.StartedProcessing)

            handler = await self._execute_matching_handler(event, path)
            event.set_timestamp(WebhookEventTimestamp.FinishedProcessingSuccessfully)
        except Exception as e:
            logger.exception(f"Error processing queued webhook for {path}: {str(e)}")
            event.set_timestamp(WebhookEventTimestamp.FinishedProcessingWithError)
        finally:
            await self._event_queues[path].commit()
            if handler:
                handler.teardown()
            self._log_processing_completion(event)

        return handler

    async def _execute_matching_handler(
        self, event: WebhookEvent, path: str
    ) -> AbstractWebhookHandler:
        """Find and execute the matching handler for an event."""
        matching_handlers = [
            reg.handler for reg in self._handlers[path] if reg.filter(event)
        ]

        if not matching_handlers:
            raise ValueError("No matching handlers found")

        handler = matching_handlers[0](event)
        try:
            await asyncio.wait_for(
                handler.process_request(),
                timeout=MAX_HANDLER_PROCESSING_SECONDS,
            )
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Handler processing timed out after {MAX_HANDLER_PROCESSING_SECONDS} seconds"
            )
        return handler

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
                timeout=MAX_WAIT_SECONDS_BEFORE_SHUTDOWN,
            )
        except asyncio.TimeoutError:
            logger.warning("Shutdown timed out waiting for queues to empty")

        for task in self._webhook_processor_tasks:
            task.cancel()

        if self._webhook_processor_tasks:
            await asyncio.gather(*self._webhook_processor_tasks, return_exceptions=True)
