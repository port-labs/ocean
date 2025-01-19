from typing import Dict, Type, Set
from fastapi import APIRouter, Request
from loguru import logger
import asyncio

from .abstract_webhook_handler import AbstractWebhookHandler
from port_ocean.utils.signal import signal_handler


class WebhookHandlerManager:
    """Manages webhook handlers and their routes."""

    def __init__(self, router: APIRouter) -> None:
        self._router = router
        self._handlers: Dict[str, Type[AbstractWebhookHandler]] = {}
        self._message_queues: Dict[str, asyncio.Queue[Request]] = {}
        self._webhook_processor_tasks: Set[asyncio.Task[None]] = set()
        signal_handler.register(self.shutdown)

    async def handle_webhook(self, request: Request, path: str) -> Dict[str, str]:
        """Handle incoming webhook requests for a specific path."""
        try:
            await self._message_queues[path].put(request)
            return {"status": "ok"}
        except Exception as e:
            logger.exception(f"Error processing webhook: {str(e)}")
            return {"status": "error", "message": str(e)}

    async def process_queue(self, path: str) -> None:
        """Process events for a specific path in order."""
        while True:
            try:
                # Only get request from queue
                request = await self._message_queues[path].get()
                try:
                    handler = self._handlers[path]()
                    await handler.process_request(request)
                except Exception as e:
                    logger.exception(
                        f"Error processing queued webhook for {path}: {str(e)}"
                    )
                finally:
                    self._message_queues[path].task_done()
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
        self._message_queues[path] = asyncio.Queue()

        # Start queue processor for this path
        task = asyncio.create_task(self.process_queue(path))
        self._webhook_processor_tasks.add(task)
        # Remove the task from set when done
        task.add_done_callback(self._webhook_processor_tasks.discard)

        self._router.add_api_route(
            path,
            lambda request: self.handle_webhook(request, path),
            methods=["POST"],
        )

    async def shutdown(self) -> None:
        """Gracefully shutdown all queue processors."""
        try:
            # Wait for all queues to be empty with a timeout
            await asyncio.wait_for(
                asyncio.gather(
                    *(queue.join() for queue in self._message_queues.values())
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
# Wrap event to add metadata - add timestamp when event arrived to to each queue
# add ttl to event processing
# facade away the queue handling
# separate event handling per kind as well as per route
