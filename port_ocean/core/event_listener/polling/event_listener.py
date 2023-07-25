from typing import Literal, Any

from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.event_listener.base import (
    BaseEventListener,
    EventListenerEvents,
    EventListenerSettings,
)
from port_ocean.core.event_listener.polling.utils import repeat_every


class PollingEventListenerSettings(EventListenerSettings):
    type: Literal["POLLING"]
    resync_on_start: bool = True
    interval: int = 60

    def to_request(self) -> dict[str, Any]:
        return {}


class PollingEventListener(BaseEventListener):
    def __init__(
        self,
        events: EventListenerEvents,
        event_listener_config: PollingEventListenerSettings,
    ):
        super().__init__(events)
        self.event_listener_config = event_listener_config
        self._last_updated_at = None

    async def start(self) -> None:
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

            should_resync = (
                self._last_updated_at is not None
                or self.event_listener_config.resync_on_start
            ) and self._last_updated_at != last_updated_at

            if should_resync:
                logger.info("Detected change in integration, resyncing")
                self._last_updated_at = last_updated_at
                await self.events["on_resync"]({})

        # Execute resync repeatedly task
        await resync()
