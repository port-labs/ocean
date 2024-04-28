import asyncio
from abc import abstractmethod, ABC
from asyncio import Queue
from collections import defaultdict
from loguru import logger
from typing import Awaitable, Callable, Any, Type

from gitlab_integration.events.hooks.base import HookHandler
from gitlab_integration.gitlab_service import GitlabService

Observer = Callable[[str, dict[str, Any]], Awaitable[Any]]


class BaseEventHandler(ABC):
    def __init__(self) -> None:
        self.webhook_tasks_queue: Queue = Queue()

    async def start_event_processor(self) -> None:
        logger.info(f"Started {self.__class__.__name__} worker")
        while True:
            event_id, body = await self.webhook_tasks_queue.get()
            try:
                # Needed to free the event loop so the webhook response could be returned without waiting
                # for the blocking self._notify method
                await asyncio.sleep(10)
                await self._notify(event_id, body)
            finally:
                self.webhook_tasks_queue.task_done()

    @abstractmethod
    async def _notify(self, event: str, body: dict[str, Any]) -> None:
        pass

    async def notify(self, event: str, body: dict[str, Any]) -> None:
        await self.webhook_tasks_queue.put((event, body))


class EventHandler(BaseEventHandler):
    def __init__(self) -> None:
        super().__init__()
        self._observers: dict[str, list[Observer]] = defaultdict(list)

    def on(self, events: list[str], observer: Observer) -> None:
        for event in events:
            self._observers[event].append(observer)

    async def _notify(self, event: str, body: dict[str, Any]) -> None:
        observers = asyncio.gather(
            *(observer(event, body) for observer in self._observers.get(event, []))
        )

        if not observers:
            logger.debug(
                f"event: {event} has no matching handler. the handlers available are for events: {self._observers.keys()}"
            )


class SystemEventHandler(BaseEventHandler):
    def __init__(self) -> None:
        super().__init__()
        self._hook_handlers: dict[str, list[Type[HookHandler]]] = defaultdict(list)
        self._clients: list[GitlabService] = []

    def on(self, hook_handler: Type[HookHandler]) -> None:
        for system_event in hook_handler.system_events:
            self._hook_handlers[system_event].append(hook_handler)

    def add_client(self, client: GitlabService) -> None:
        self._clients.append(client)

    async def _notify(self, event: str, body: dict[str, Any]) -> None:
        # best effort to notify using all clients, as we don't know which one of the clients have the permission to
        # access the project
        asyncio.gather(
            *(
                hook_handler(client).on_hook(event, body)
                for client in self._clients
                for hook_handler in self._hook_handlers.get(event, [])
            ),
            return_exceptions=True,
        )
