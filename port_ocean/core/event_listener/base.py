from abc import abstractmethod
from typing import TypedDict, Callable, Any, Awaitable

from pydantic import Extra

from port_ocean.config.base import BaseOceanModel
from port_ocean.utils.signal import signal_handler
from port_ocean.context.ocean import ocean


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

    async def start(self) -> None:
        signal_handler.register(self._stop)
        await self._start()

    @abstractmethod
    async def _start(self) -> None:
        pass

    def _stop(self) -> None:
        """
        Can be used for event listeners that need cleanup before exiting.
        """
        pass

    async def _before_resync(self) -> None:
        """
        Can be used for event listeners that need to perform some action before resync.
        """
        await ocean.app.update_state_before_scheduled_sync()

    async def _after_resync(self) -> None:
        """
        Can be used for event listeners that need to perform some action after resync.
        """
        await ocean.app.update_state_after_scheduled_sync()

    async def _on_resync_failure(self, e: Exception) -> None:
        """
        Can be used for event listeners that need to handle resync failures.
        """
        await ocean.app.update_state_after_scheduled_sync("failed")

    async def _resync(
        self,
        resync_args: dict[Any, Any],
    ) -> None:
        """
        Triggers the "on_resync" event.
        """
        await self._before_resync()
        try:
            await self.events["on_resync"](resync_args)
            await self._after_resync()
        except Exception as e:
            await self._on_resync_failure(e)
            raise e


class EventListenerSettings(BaseOceanModel, extra=Extra.allow):
    type: str

    def to_request(self) -> dict[str, Any]:
        """
        Converts the Settings object to a dictionary representation (request format).
        """
        return {"type": self.type}
