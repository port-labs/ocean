import asyncio
from collections import defaultdict
from typing import Awaitable, Callable, Any, Type

import fastapi

from gitlab_integration.events.hooks.base import HookHandler
from gitlab_integration.gitlab_service import GitlabService

Observer = Callable[[str, dict[str, Any]], Awaitable[Any]]


class EventHandler:
    def __init__(self) -> None:
        self._observers: dict[str, list[Observer]] = defaultdict(list)

    def on(self, events: list[str], observer: Observer) -> None:
        for event in events:
            self._observers[event].append(observer)

    async def notify(self, request: fastapi.Request, group_id: str) -> Awaitable[Any]:
        event = f'{request.headers.get("X-Gitlab-Event")}:{group_id}'
        body = await request.json()
        return asyncio.gather(
            *(observer(event, body) for observer in self._observers.get(event, []))
        )


class SystemEventHandler:
    def __init__(self) -> None:
        self._hook_handlers: dict[str, list[Type[HookHandler]]] = defaultdict(list)
        self._clients: list[GitlabService] = []

    def on(self, hook_handler: Type[HookHandler]) -> None:
        for system_event in hook_handler.system_events:
            self._hook_handlers[system_event].append(hook_handler)

    def add_client(self, client: GitlabService) -> None:
        self._clients.append(client)

    async def notify(self, request: fastapi.Request) -> Awaitable[Any]:
        body = await request.json()
        # some system hooks have event_type instead of event_name in the body, such as merge_request events
        event_name = body.get("event_name") or body.get("event_type")
        # best effort to notify using all clients, as we don't know which one of the clients have the permission to
        # access the project
        return asyncio.gather(
            *(
                hook_handler(client).on_hook(event_name, body)
                for client in self._clients
                for hook_handler in self._hook_handlers.get(event_name, [])
            ),
            return_exceptions=True,
        )
