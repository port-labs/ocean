from abc import abstractmethod
from typing import TypedDict, Callable, Any, Awaitable


class TriggerChannelEvents(TypedDict):
    on_resync: Callable[[dict[Any, Any]], Awaitable[None]]
    on_action: Callable[[dict[Any, Any]], Awaitable[None]]


class BaseTriggerChannel:
    def __init__(
        self,
        events: TriggerChannelEvents,
    ):
        self.events = events

    @abstractmethod
    async def start(self) -> None:
        pass
