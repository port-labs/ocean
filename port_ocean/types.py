from typing import (
    Awaitable,
    Callable,
    TypedDict,
    Any,
)

from port_ocean.core.models import Entity


class RawEntityDiff(TypedDict):
    before: list[dict[Any, Any]]
    after: list[dict[Any, Any]]


class EntityDiff(TypedDict):
    before: list[Entity]
    after: list[Entity]


RESYNC_EVENT_LISTENER = Callable[[str], Awaitable[list[dict[Any, Any]]]]
START_EVENT_LISTENER = Callable[[], Awaitable]


class IntegrationEventsCallbacks(TypedDict):
    start: list[START_EVENT_LISTENER]
    resync: dict[str | None, list[RESYNC_EVENT_LISTENER]]
