import signal
from typing import Literal, Any

from loguru import logger

from port_ocean.core.event_listener.base import (
    BaseEventListener,
    EventListenerEvents,
    EventListenerSettings,
)
from port_ocean.utils import repeat_every


class ImmediateEventListenerSettings(EventListenerSettings):
    """
    Immediate event listener configuration settings.
    This class inherits from `EventListenerSettings`, which provides a foundation for creating event listener settings.
    """

    type: Literal["IMMEDIATE"]

    def to_request(self) -> dict[str, Any]:
        return {}


class ImmediateEventListener(BaseEventListener):
    """
    Immediate event listener.

    This event listener is used to trigger a resync immediately.

    Parameters:
        events (EventListenerEvents): A dictionary containing event types and their corresponding event handlers.
        event_listener_config (ImmediateEventListenerSettings): The event listener configuration settings.
    """

    def __init__(
        self,
        events: EventListenerEvents,
        event_listener_config: ImmediateEventListenerSettings,
    ):
        super().__init__(events)
        self.event_listener_config = event_listener_config

    async def start(self) -> None:
        """
        Starts the resync process, and exits the application once finished.
        """

        @repeat_every(seconds=0)
        async def resync_and_exit() -> None:
            logger.info("Immediate event listener started")
            await self.events["on_resync"]({})
            logger.info("Immediate event listener finished")
            logger.info("Exiting application")
            signal.raise_signal(signal.SIGINT)

        await resync_and_exit()
