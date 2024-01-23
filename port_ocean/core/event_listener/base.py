from abc import abstractmethod
from typing import TypedDict, Callable, Any, Awaitable

from pydantic import BaseModel, Extra

from port_ocean.utils.signal import register_signal_handler


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

    async def start(self):
        register_signal_handler(self._stop)
        await self._start()

    @abstractmethod
    async def _start(self) -> None:
        pass

    @abstractmethod
    async def _stop(self) -> None:
        pass


class EventListenerSettings(BaseModel, extra=Extra.allow):
    type: str

    def to_request(self) -> dict[str, Any]:
        """
        Converts the Settings object to a dictionary representation (request format).
        """
        return {"type": self.type}
