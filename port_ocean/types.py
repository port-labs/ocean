from typing import Awaitable, Callable, TypedDict, List, Dict, Any


class ObjectDiff(TypedDict):
    before: List[Dict[Any, Any]]
    after: List[Dict[Any, Any]]


RESYNC_EVENT_LISTENER = Callable[[str], Awaitable[ObjectDiff]]
START_EVENT_LISTENER = Callable[[], Awaitable]


class IntegrationEventsCallbacks(TypedDict):
    start: List[START_EVENT_LISTENER]
    resync: List[RESYNC_EVENT_LISTENER]
