from typing import Awaitable, Callable, TypedDict, Dict, Any


class Events(TypedDict):
    on_resync: Callable[[Dict[Any, Any]], Awaitable[None]]
    on_action: Callable[[Dict[Any, Any]], Awaitable[None]]
