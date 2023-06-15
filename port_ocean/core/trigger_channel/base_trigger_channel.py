from abc import abstractmethod
from typing import TypedDict, Callable, Dict, Any, Awaitable


class TriggerEventEvents(TypedDict):
    on_resync: Callable[[Dict[Any, Any]], Awaitable[None]]
    on_action: Callable[[Dict[Any, Any]], Awaitable[None]]


class BaseTriggerChannel:
    def __init__(
        self,
        events: TriggerEventEvents,
    ):
        self.events = events

    @abstractmethod
    def start(self) -> None:
        pass
