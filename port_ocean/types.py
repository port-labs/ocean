from typing import (
    Awaitable,
    Callable,
    TypedDict,
    List,
    Dict,
    Any,
    Union,
    Generic,
    TypeVar,
)

from port_ocean.core.models import Blueprint, Entity


class RawObjectDiff(TypedDict):
    before: List[Dict[Any, Any]]
    after: List[Dict[Any, Any]]


T = TypeVar("T", bound=Union[Entity, Blueprint])


class ObjectDiff(TypedDict, Generic[T]):
    before: List[T]
    after: List[T]


RESYNC_EVENT_LISTENER = Callable[[str], Awaitable[RawObjectDiff]]
START_EVENT_LISTENER = Callable[[], Awaitable]


class IntegrationEventsCallbacks(TypedDict):
    start: List[START_EVENT_LISTENER]
    resync: List[RESYNC_EVENT_LISTENER]
