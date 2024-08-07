import datetime
import signal
from typing import Literal, Any

from loguru import logger

from port_ocean.core.event_listener.base import (
    BaseEventListener,
    EventListenerEvents,
    EventListenerSettings,
)
from port_ocean.utils.repeat import repeat_every
from port_ocean.context.ocean import ocean
from port_ocean.utils.misc import convert_str_to_datetime, convert_time_to_minutes


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
        self.cached_integration: dict[str, Any] | None = None

    async def get_current_integration_cached(self) -> dict[str, Any] | None:
        if self.cached_integration:
            return self.cached_integration

        try:
            self.cached_integration = await ocean.port_client.get_current_integration()
            return self.cached_integration
        except Exception:
            logger.exception("Error occurred while getting current integration")
            return None

    async def get_saas_integration_prediction_data(
        self,
    ) -> tuple[int | None, datetime.datetime | None]:
        if not ocean.app.is_saas():
            return (None, None)

        integration = await self.get_current_integration_cached()
        if not integration:
            return (None, None)

        integration = await ocean.port_client.get_current_integration()
        interval_str = (
            integration.get("spec", {})
            .get("appSpec", {})
            .get("scheduledResyncInterval")
        )

        if not interval_str:
            logger.error(
                "Integration scheduled resync interval not found for integration state update"
            )
            return (None, None)

        start_time_str = integration.get("statusInfo", {}).get("updatedAt")

        if not start_time_str:
            logger.error(
                "Integration creation time not found for integration state update"
            )
            return (None, None)

        return (
            convert_time_to_minutes(interval_str),
            convert_str_to_datetime(start_time_str),
        )

    async def _before_resync(self) -> None:
        if not ocean.app.is_saas():
            await super()._before_resync()
            return

        (interval, start_time) = await self.get_saas_integration_prediction_data()
        await ocean.app.update_state_before_scheduled_sync(interval, start_time)

    async def _after_resync(self) -> None:
        if not ocean.app.is_saas():
            await super()._before_resync()
            return

        (interval, start_time) = await self.get_saas_integration_prediction_data()
        await ocean.app.update_state_after_scheduled_sync(interval, start_time)

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
                await self._before_resync()
                await self.events["on_resync"]({})
                await self._after_resync()
            except Exception:
                # we catch all exceptions here to make sure the application will exit gracefully
                logger.exception("Error occurred while resyncing")
            logger.info("Once event listener finished")
            logger.info("Exiting application")
            signal.raise_signal(signal.SIGINT)

        await resync_and_exit()
