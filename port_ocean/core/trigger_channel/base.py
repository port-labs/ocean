from abc import abstractmethod
from typing import TypedDict, Callable, Dict, Any, Awaitable, TypeVar, Generic

from port_ocean.core.trigger_channel.settings import TriggerChannelSettings


class TriggerChannelEvents(TypedDict):
    on_resync: Callable[[Dict[Any, Any]], Awaitable[None]]
    on_action: Callable[[Dict[Any, Any]], Awaitable[None]]


T = TypeVar("T", bound=TriggerChannelSettings)


class BaseTriggerChannel(Generic[T]):
    def __init__(
        self,
        events: TriggerChannelEvents,
        trigger_channel_config: T,
    ):
        self.events = events
        self.trigger_channel_config = trigger_channel_config

    @abstractmethod
    async def start(self) -> None:
        pass
