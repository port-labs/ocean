from asyncio import Task, get_event_loop
from typing import Literal, Any

from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.event_listener.base import (
    BaseEventListener,
    EventListenerEvents,
    EventListenerSettings,
)
from port_ocean.utils.repeat import repeat_every
from port_ocean.utils.signal import signal_handler


class PollingEventListenerSettings(EventListenerSettings):
    """
    Attributes:
        type (Literal["POLLING"]): A literal indicating the type of the event listener, which is set to "POLLING" for this class.
        resync_on_start (bool): A flag indicating whether to trigger a resync event on the start of the polling event listener.
                                If True, the "on_resync" event will be triggered immediately when the polling listener starts.
        interval (int): The interval in seconds at which the polling event listener checks for changes in the integration.
                        The default interval is set to 60 seconds.
    """

    type: Literal["POLLING"]
    resync_on_start: bool = True
    interval: int = 60


class PollingEventListener(BaseEventListener):
    """
    Polling event listener that checks for changes in the integration every `interval` seconds.

    The `PollingEventListener` periodically checks for changes in the integration and triggers the "on_resync" event if changes are detected.

    Parameters:
        events (EventListenerEvents): A dictionary containing event types and their corresponding event handlers.
        event_listener_config (PollingEventListenerSettings): Configuration settings for the Polling event listener.
    """

    def __init__(
        self,
        events: EventListenerEvents,
        event_listener_config: PollingEventListenerSettings,
    ):
        super().__init__(events)
        self.event_listener_config = event_listener_config

    def should_resync(self, last_updated_at: str) -> bool:
        _last_updated_at = (
            ocean.app.resync_state_updater.last_integration_state_updated_at
        )

        if _last_updated_at is None:
            return self.event_listener_config.resync_on_start

        return _last_updated_at != last_updated_at

    async def _start(self) -> None:
        """
        Starts the polling event listener.
        It registers the "on_resync" event to be called every `interval` seconds specified in the `event_listener_config`.
        The `on_resync` event is triggered if the integration has changed since the last update.
        """
        logger.info(
            f"Setting up Polling event listener with interval: {self.event_listener_config.interval}"
        )

        @repeat_every(seconds=self.event_listener_config.interval)
        async def resync() -> None:
            logger.info(
                f"Polling event listener iteration after {self.event_listener_config.interval}. Checking for changes"
            )
            integration = await ocean.app.port_client.get_current_integration()
            last_updated_at = integration["updatedAt"]

            if self.should_resync(last_updated_at):
                logger.info("Detected change in integration, resyncing")
                ocean.app.resync_state_updater.last_integration_state_updated_at = (
                    last_updated_at
                )
                running_task: Task[Any] = get_event_loop().create_task(self._resync({}))
                signal_handler.register(running_task.cancel)

                await running_task

        # Execute resync repeatedly task
        await resync()
