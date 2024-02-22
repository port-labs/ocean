from abc import abstractmethod
from asyncio import Task
from typing import TypedDict, Callable, Any, Awaitable

from pydantic import Extra

from port_ocean.config.base import BaseOceanModel
from port_ocean.utils.signal import signal_handler


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
        self._tasks_to_close: list[Task[Any]] = []

    async def start(self) -> None:
        signal_handler.register(self._stop)
        await self._start()

    @abstractmethod
    async def _start(self) -> None:
        pass

    def stop(self) -> None:
        self._stop()
        for task in self._tasks_to_close:
            task.cancel()

    def _stop(self) -> None:
        """
        Can be used for event listeners that need cleanup before exiting.
        """
        pass


class EventListenerSettings(BaseOceanModel, extra=Extra.allow):
    type: str

    def to_request(self) -> dict[str, Any]:
        """
        Converts the Settings object to a dictionary representation (request format).
        """
        return {"type": self.type}
