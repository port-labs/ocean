import asyncio
import inspect
from abc import abstractmethod, ABC
from asyncio import Queue
from collections import defaultdict
from copy import deepcopy

from loguru import logger
from typing import Awaitable, Callable, Any, Type

from gitlab_integration.events.hooks.base import HookHandler
from gitlab_integration.gitlab_service import GitlabService
from port_ocean.context.event import (
    event as current_event_context,
    event_context,
    EventContext,
)

Observer = Callable[[str, dict[str, Any]], Awaitable[Any]]


class BaseEventHandler(ABC):
    def __init__(self) -> None:
        self.webhook_tasks_queue: Queue[tuple[EventContext, str, dict[str, Any]]] = (
            Queue()
        )

    async def _start_event_processor(self) -> None:
        logger.info(f"Started {self.__class__.__name__} worker")
        while True:
            event_ctx, event_id, body = await self.webhook_tasks_queue.get()
            logger.debug(f"Retrieved event: {event_id} from Queue, notifying observers")
            try:
                async with event_context(
                    "gitlab_http_event_async_worker", parent_override=event_ctx
                ):
                    await self._notify(event_id, body)
            except Exception as e:
                logger.error(
                    f"Error notifying observers for event: {event_id}, error: {e}"
                )
            finally:
                logger.info(
                    f"Processed event {event_id}",
                    event_id=event_id,
                    event_context=event_ctx.id,
                )
                self.webhook_tasks_queue.task_done()

    async def start_event_processor(self) -> None:
        asyncio.create_task(self._start_event_processor())

    @abstractmethod
    async def _notify(self, event_id: str, body: dict[str, Any]) -> None:
        pass

    async def notify(self, event_id: str, body: dict[str, Any]) -> None:
        logger.debug(
            f"Received event: {event_id}, putting it in Queue for processing",
            event_context=current_event_context.id,
        )
        await self.webhook_tasks_queue.put(
            (
                deepcopy(current_event_context),
                event_id,
                body,
            )
        )


class EventHandler(BaseEventHandler):
    def __init__(self) -> None:
        super().__init__()
        self._observers: dict[str, list[Observer]] = defaultdict(list)

    def on(self, events: list[str], observer: Observer) -> None:
        for event in events:
            self._observers[event].append(observer)

    async def _notify(self, event_id: str, body: dict[str, Any]) -> None:
        observers_list = self._observers.get(event_id, [])
        if not observers_list:
            logger.info(
                f"event: {event_id} has no matching handler. the handlers available are for events: {self._observers.keys()}"
            )
            return
        for observer in observers_list:
            if asyncio.iscoroutinefunction(observer):
                if inspect.ismethod(observer):
                    handler = observer.__self__.__class__.__name__
                    logger.debug(
                        f"Notifying observer: {handler}, for event: {event_id}",
                        event_id=event_id,
                        handler=handler,
                    )
                asyncio.create_task(observer(event_id, body))  # type: ignore


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

    async def _notify(self, event_id: str, body: dict[str, Any]) -> None:
        # best effort to notify using all clients, as we don't know which one of the clients have the permission to
        # access the project
        await asyncio.gather(
            *(
                hook_handler(client).on_hook(event_id, body)
                for client in self._clients
                for hook_handler in self._hook_handlers.get(event_id, [])
            ),
            return_exceptions=True,
        )
