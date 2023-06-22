from typing import (
    Awaitable,
    Callable,
    TypedDict,
    List,
    Dict,
    Any,
)

from port_ocean.core.models import Entity


class EntityRawDiff(TypedDict):
    before: List[Dict[Any, Any]]
    after: List[Dict[Any, Any]]


class EntityDiff(TypedDict):
    before: List[Entity]
    after: List[Entity]


RESYNC_EVENT_LISTENER = Callable[[str], Awaitable[List[Dict[Any, Any]]]]
START_EVENT_LISTENER = Callable[[], Awaitable]


class IntegrationEventsCallbacks(TypedDict):
    start: List[START_EVENT_LISTENER]
    resync: Dict[str | None, List[RESYNC_EVENT_LISTENER]]
