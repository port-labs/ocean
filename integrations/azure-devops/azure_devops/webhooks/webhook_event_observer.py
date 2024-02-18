import asyncio
from collections import defaultdict
from typing import Any, Awaitable, Callable
from .webhook_event import WebhookEvent

Observer = Callable[[dict[str, Any]], Awaitable[Any]]


class WebhookEventObserver:
    def __init__(self) -> None:
        self._observers: dict[str, list[Observer]] = defaultdict(list)

    def on(self, events: list[WebhookEvent], observer: Observer) -> None:
        for event in events:
            self._observers[self._get_event_key_from_event(event)].append(observer)

    async def notify(self, event: WebhookEvent, body: dict[str, Any]) -> Awaitable[Any]:
        return asyncio.gather(
            *(
                observer(body)
                for observer in self._observers.get(
                    self._get_event_key_from_event(event), []
                )
            )
        )

    def _get_event_key_from_event(self, event: WebhookEvent) -> str:
        return f"{event.publisherId}:{event.consumerId}"
