from abc import abstractmethod
from typing import TypedDict, Callable, Any, Awaitable

from pydantic import BaseModel


class EventListenerEvents(TypedDict):
    on_resync: Callable[[dict[Any, Any]], Awaitable[None]]


class BaseEventListener:
    def __init__(
        self,
        events: EventListenerEvents,
    ):
        self.events = events

    @abstractmethod
    async def start(self) -> None:
        pass


class EventListenerSettings(BaseModel):
    type: str

    def to_request(self) -> dict[str, Any]:
        return {"type": self.type}
