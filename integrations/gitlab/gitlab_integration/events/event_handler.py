import asyncio
from abc import abstractmethod, ABC
from collections import defaultdict
from loguru import logger
from typing import Awaitable, Callable, Any, Type

from gitlab_integration.events.hooks.base import HookHandler
from gitlab_integration.gitlab_service import GitlabService

Observer = Callable[[str, dict[str, Any]], Awaitable[Any]]


class BaseEventHandler(ABC):
    def __init__(self) -> None:
        self._webhook_handling_concurrency = asyncio.Semaphore(20)
        self.webhook_tasks_queue: asyncio.Queue = asyncio.Queue()

    async def start_event_processor(self) -> None:
        logger.error(f"Started {self.__class__.__name__} worker")
        while True:
            event_id, body = await self.webhook_tasks_queue.get()
            await asyncio.sleep(3)
            try:
                async with self._webhook_handling_concurrency:
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
