import signal
from typing import Literal, Any

from loguru import logger

from port_ocean.core.event_listener.base import (
    BaseEventListener,
    EventListenerEvents,
    EventListenerSettings,
)
from port_ocean.utils.repeat import repeat_every


class OnceEventListenerSettings(EventListenerSettings):
    """
    Once event listener configuration settings.
    This class inherits from `EventListenerSettings`, which provides a foundation for creating event listener settings.
    """

    type: Literal["ONCE"]

    def to_request(self) -> dict[str, Any]:
        return {}


class OnceEventListener(BaseEventListener):
    """
    Once event listener.

    This event listener is used to trigger a resync immediately.

    Parameters:
        events (EventListenerEvents): A dictionary containing event types and their corresponding event handlers.
        event_listener_config (OnceEventListenerSettings): The event listener configuration settings.
    """

    def __init__(
        self,
        events: EventListenerEvents,
        event_listener_config: OnceEventListenerSettings,
    ):
        super().__init__(events)
        self.event_listener_config = event_listener_config

    async def _start(self) -> None:
        """
        Starts the resync process, and exits the application once finished.
        """

        # we use the `repeat_every` decorator to make sure the resync will be triggered, but won't stuck the application
        # from finishing the startup process which is required to close the application gracefully
        @repeat_every(seconds=0, max_repetitions=1)
        async def resync_and_exit() -> None:
            logger.info("Once event listener started")
            try:
                await self.events["on_resync"]({})
            except Exception:
                # we catch all exceptions here to make sure the application will exit gracefully
                logger.exception("Error occurred while resyncing")
            logger.info("Once event listener finished")
            logger.info("Exiting application")
            signal.raise_signal(signal.SIGINT)

        await resync_and_exit()
