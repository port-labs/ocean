from typing import TypedDict, Any, AsyncIterator, Callable, Awaitable

from port_ocean.core.models import Entity


class RawEntityDiff(TypedDict):
    before: list[dict[Any, Any]]
    after: list[dict[Any, Any]]


class EntityDiff(TypedDict):
    before: list[Entity]
    after: list[Entity]


RAW_ITEM = dict[Any, Any]
RAW_RESULT = list[RAW_ITEM]
ASYNC_GENERATOR_RESYNC_TYPE = AsyncIterator[RAW_RESULT]
RESYNC_RESULT = list[RAW_ITEM | ASYNC_GENERATOR_RESYNC_TYPE]

LISTENER_RESULT = Awaitable[RAW_RESULT] | ASYNC_GENERATOR_RESYNC_TYPE
RESYNC_EVENT_LISTENER = Callable[[str], LISTENER_RESULT]
START_EVENT_LISTENER = Callable[[], Awaitable[None]]


class IntegrationEventsCallbacks(TypedDict):
    start: list[START_EVENT_LISTENER]
    resync: dict[str | None, list[RESYNC_EVENT_LISTENER]]
