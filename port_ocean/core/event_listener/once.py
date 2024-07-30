import datetime
import signal
from typing import Literal, Any

from loguru import logger

from port_ocean.core.models import Runtime
from port_ocean.core.event_listener.base import (
    BaseEventListener,
    EventListenerEvents,
    EventListenerSettings,
)
from port_ocean.utils.repeat import repeat_every
from port_ocean.context.ocean import ocean
from port_ocean.utils.misc import convert_time_to_minutes


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
        self.resync_start_time: datetime.datetime | None = None
        self.resync_interval: int | None = None

    async def get_scheduled_resync_interval(self) -> int | None:
        if not self.is_saas():
            return None

        if self.resync_interval:
            return self.resync_interval

        try:
            integration = await ocean.port_client.get_current_integration()
            interval_str = (
                integration.get("spec", {})
                .get("appSpec", {})
                .get("scheduledResyncInterval")
            )
            self.resync_interval = convert_time_to_minutes(interval_str)
            return self.resync_interval
        except Exception:
            logger.exception("Error occurred while calculating next resync")
            return None

    def is_saas(self) -> bool:
        return ocean.config.runtime == Runtime.Saas

    async def before_resync(self) -> None:
        if self.is_saas():
            interval = await self.get_scheduled_resync_interval()
            self.resync_start_time = await ocean.app.update_state_before_scheduled_sync(
                interval
            )

    async def after_resync(self) -> None:
        if self.is_saas() and self.resync_start_time:
            interval = await self.get_scheduled_resync_interval()
            await ocean.app.update_state_after_scheduled_sync(
                self.resync_start_time, interval
            )

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
                await self.before_resync()
                await self.events["on_resync"]({})
                await self.after_resync()
            except Exception:
                # we catch all exceptions here to make sure the application will exit gracefully
                logger.exception("Error occurred while resyncing")
            logger.info("Once event listener finished")
            logger.info("Exiting application")
            signal.raise_signal(signal.SIGINT)

        await resync_and_exit()
