from abc import abstractmethod
from typing import TypedDict, Callable, Any, Awaitable

from pydantic import BaseModel, Extra


class EventListenerEvents(TypedDict):
    """
    A dictionary containing event types and their corresponding event handlers.
    """

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


class EventListenerSettings(BaseModel, extra=Extra.allow):
    type: str

    def to_request(self) -> dict[str, Any]:
        """
        Converts the Settings object to a dictionary representation (request format).
        """
        return {"type": self.type}
