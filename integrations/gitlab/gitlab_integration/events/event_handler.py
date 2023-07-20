import asyncio
from collections import defaultdict
from typing import Awaitable, Callable, Any


Observer = Callable[[str, str, dict[str, Any]], Awaitable[Any]]


class EventHandler:
    def __init__(self) -> None:
        self._observers: dict[str, list[Observer]] = defaultdict(list)

    def on(self, events: list[str], observer: Observer) -> None:
        for event in events:
            self._observers[event].append(observer)

    async def notify(
        self, event: str, group_id: str, body: dict[str, Any]
    ) -> Awaitable[Any]:
        return asyncio.gather(
            *(observer(event, group_id, body) for observer in self._observers[event])
        )
