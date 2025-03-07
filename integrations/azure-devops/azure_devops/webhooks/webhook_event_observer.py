import asyncio
from collections import defaultdict
from typing import Any, Awaitable, Callable

from loguru import logger

from .webhook_event import WebhookEvent

Observer = Callable[[dict[str, Any]], Awaitable[Any]]


class WebhookEventObserver:
    def __init__(self) -> None:
        self._observers: dict[str, list[Observer]] = defaultdict(list)

    def on(self, events: list[WebhookEvent], observer: Observer) -> None:
        for event in events:
            self._observers[self._get_observer_key_from_webhook_event(event)].append(
                observer
            )

    async def notify(self, event: WebhookEvent, body: dict[str, Any]) -> None:
        event_key = self._get_observer_key_from_webhook_event(event)
        tasks = [observer(body) for observer in self._observers.get(event_key, [])]

        logger.info(f"Got event {event_key}, notifying {len(tasks)} listeners..")
        results_with_error = await asyncio.gather(*(tasks), return_exceptions=True)
        errors = [
            result for result in results_with_error if isinstance(result, Exception)
        ]
        logger.info(
            f"Triggered {len(tasks)} tasks for event {event_key}, failed: {len(errors)}"
        )
        for error in errors:
            logger.error(
                f"Got error while handling webhook event {event_key}: {str(error)}"
            )

    def _get_observer_key_from_webhook_event(self, event: WebhookEvent) -> str:
        return f"{event.publisherId}:{event.eventType}"
