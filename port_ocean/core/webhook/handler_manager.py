import datetime
from typing import Dict, Type, Set
from fastapi import APIRouter, Request
from loguru import logger
import asyncio

from .event import WebhookEvent, WebhookEventTimestamp


from .abstract_webhook_handler import AbstractWebhookHandler
from port_ocean.utils.signal import signal_handler


class WebhookHandlerManager:
    """Manages webhook handlers and their routes."""

    def __init__(self, router: APIRouter) -> None:
        self._router = router
        self._handlers: Dict[str, Type[AbstractWebhookHandler]] = {}
        self._event_queues: Dict[str, asyncio.Queue[WebhookEvent]] = {}
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
            try:
                event = await self._event_queues[path].get()
                with logger.contextualize(webhook_path=path, trace_id=event.trace_id):
                    try:
                        logger.debug("start Processing queued webhook")
                        event.set_timestamp(WebhookEventTimestamp.StartedProcessing)
                        handler = self._handlers[path](event)
                        await handler.process_request()
                    except Exception as e:
                        logger.exception(
                            f"Error processing queued webhook for {path}: {str(e)}"
                        )
                    finally:
                        logger.debug(
                            "Finished processing queued webhook",
                            arrived_at_queue=event.get_timestamp(
                                WebhookEventTimestamp.AddedToQueue
                            ),
                            started_processing=event.get_timestamp(
                                WebhookEventTimestamp.StartedProcessing
                            ),
                            done_processing=datetime.datetime.now(),
                        )
                        self._event_queues[path].task_done()
            except asyncio.CancelledError:
                logger.info(f"Queue processor for {path} is shutting down")
                break
            except Exception as e:
                logger.exception(
                    f"Unexpected error in queue processor for {path}: {str(e)}"
                )

    def register_handler(
        self,
        path: str,
        handler: Type[AbstractWebhookHandler],
    ) -> None:
        """Register a webhook handler for a specific path."""
        self._handlers[path] = handler
        self._event_queues[path] = asyncio.Queue()

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
            # Wait for all queues to be empty with a timeout
            await asyncio.wait_for(
                asyncio.gather(
                    *(queue.join() for queue in self._event_queues.values())
                ),
                timeout=5.0,  # 10 seconds timeout
            )
        except asyncio.TimeoutError:
            logger.warning("Shutdown timed out waiting for queues to empty")

        # Cancel all queue processors
        for task in self._webhook_processor_tasks:
            task.cancel()

        # Wait for all tasks to be cancelled
        if self._webhook_processor_tasks:
            await asyncio.gather(*self._webhook_processor_tasks, return_exceptions=True)


# check of asyncio maintains order
# Wrap event to add metadata - add timestamp when event arrived to to each queue - Done
# add ttl to event processing
# facade away the queue handling
# separate event handling per kind as well as per route
# add on_cancel method to handler
