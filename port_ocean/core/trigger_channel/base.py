from abc import abstractmethod
from typing import TypedDict, Callable, Any, Awaitable

from pydantic import BaseSettings


class TriggerChannelEvents(TypedDict):
    on_resync: Callable[[dict[Any, Any]], Awaitable[None]]


class BaseTriggerChannel:
    def __init__(
        self,
        events: TriggerChannelEvents,
    ):
        self.events = events

    @abstractmethod
    async def start(self) -> None:
        pass


class TriggerChannelSettings(BaseSettings):
    type: str

    def to_request(self) -> dict[str, Any]:
        return {"type": self.type}
