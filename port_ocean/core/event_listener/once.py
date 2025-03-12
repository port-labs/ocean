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
from port_ocean.utils.time import convert_str_to_utc_datetime, convert_to_minutes
from port_ocean.utils.misc import IntegrationStateStatus


class OnceEventListenerSettings(EventListenerSettings):
    """
    Once event listener configuration settings.
    This class inherits from `EventListenerSettings`, which provides a foundation for creating event listener settings.
    """

    type: Literal["ONCE"]


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
        self.cached_integration: dict[str, Any] | None = None

    async def get_current_integration_cached(self) -> dict[str, Any]:
        if self.cached_integration:
            return self.cached_integration

        self.cached_integration = await ocean.port_client.get_current_integration()
        return self.cached_integration

    async def get_saas_resync_initialization_and_interval(
        self,
    ) -> tuple[int | None, datetime.datetime | None]:
        """
        Get the scheduled resync interval and the last updated time of the integration config for the saas application.
        interval is the saas configured resync interval time.
        start_time is the last updated time of the integration config.
        return: (interval, start_time)
        """
        if not ocean.app.is_saas():
            return (None, None)

        try:
            integration = await self.get_current_integration_cached()
        except Exception as e:
            logger.exception(f"Error occurred while getting current integration {e}")
            return (None, None)

        interval_str = (
            integration.get("spec", {})
            .get("appSpec", {})
            .get("scheduledResyncInterval")
        )

        if not interval_str:
            logger.error(
                "Unexpected: scheduledResyncInterval not found for Saas integration, Cannot predict the next resync"
            )
            return (None, None)

        last_updated_saas_integration_config_str = integration.get(
            "statusInfo", {}
        ).get("updatedAt")

        # we use the last updated time of the integration config as the start time since in saas application the interval is configured by the user from the portal
        if not last_updated_saas_integration_config_str:
            logger.error(
                "Unexpected: updatedAt not found for Saas integration, Cannot predict the next resync"
            )
            return (None, None)

        return (
            convert_to_minutes(interval_str),
            convert_str_to_utc_datetime(last_updated_saas_integration_config_str),
        )

    async def _before_resync(self) -> None:
        if not ocean.app.is_saas():
            # in case of non-saas, we still want to update the state before and after the resync
            await super()._before_resync()
            return

        (interval, start_time) = (
            await self.get_saas_resync_initialization_and_interval()
        )
        await ocean.app.resync_state_updater.update_before_resync(interval, start_time)

    async def _after_resync(self) -> None:
        if not ocean.app.is_saas():
            # in case of non-saas, we still want to update the state before and after the resync
            await super()._after_resync()
            return

        (interval, start_time) = (
            await self.get_saas_resync_initialization_and_interval()
        )
        await ocean.app.resync_state_updater.update_after_resync(
            IntegrationStateStatus.Completed, interval, start_time
        )

    async def _on_resync_failure(self, e: Exception) -> None:
        if not ocean.app.is_saas():
            # in case of non-saas, we still want to update the state before and after the resync
            await super()._after_resync()
            return

        (interval, start_time) = (
            await self.get_saas_resync_initialization_and_interval()
        )
        await ocean.app.resync_state_updater.update_after_resync(
            IntegrationStateStatus.Failed, interval, start_time
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
                await self._resync({})
            except Exception:
                # we catch all exceptions here to make sure the application will exit gracefully
                logger.exception("Error occurred while resyncing")
            logger.info("Once event listener finished")
            logger.info("Exiting application")
            signal.raise_signal(signal.SIGINT)

        await resync_and_exit()
