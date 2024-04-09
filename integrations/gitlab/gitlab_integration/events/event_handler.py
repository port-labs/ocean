import asyncio
from collections import defaultdict
from loguru import logger
from typing import Awaitable, Callable, Any, Type

from gitlab_integration.events.hooks.base import HookHandler
from gitlab_integration.gitlab_service import GitlabService

Observer = Callable[[str, dict[str, Any]], Awaitable[Any]]


class EventHandler:
    def __init__(self) -> None:
        self._observers: dict[str, list[Observer]] = defaultdict(list)

    def on(self, events: list[str], observer: Observer) -> None:
        for event in events:
            self._observers[event].append(observer)

    async def notify(self, event: str, body: dict[str, Any]) -> Awaitable[Any]:
        observers = asyncio.gather(
            *(observer(event, body) for observer in self._observers.get(event, []))
        )

        if not observers:
            logger.debug(f"event: {event} has no matching handler. the handlers available are for events: {self._observers.keys()}")

        return observers



class SystemEventHandler:
    def __init__(self) -> None:
        self._hook_handlers: dict[str, list[Type[HookHandler]]] = defaultdict(list)
        self._clients: list[GitlabService] = []

    def on(self, hook_handler: Type[HookHandler]) -> None:
        for system_event in hook_handler.system_events:
            self._hook_handlers[system_event].append(hook_handler)

    def add_client(self, client: GitlabService) -> None:
        self._clients.append(client)

    async def notify(self, event: str, body: dict[str, Any]) -> Awaitable[Any]:
        # best effort to notify using all clients, as we don't know which one of the clients have the permission to
        # access the project
        return asyncio.gather(
            *(
                hook_handler(client).on_hook(event, body)
                for client in self._clients
                for hook_handler in self._hook_handlers.get(event, [])
            ),
            return_exceptions=True,
        )
