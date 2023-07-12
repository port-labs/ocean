from typing import Literal, Any

from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.trigger_channel.base import (
    BaseTriggerChannel,
    TriggerChannelEvents,
    TriggerChannelSettings,
)
from port_ocean.core.trigger_channel.sample.utils import repeat_every


class SampleTriggerChannelSettings(TriggerChannelSettings):
    type: Literal["SAMPLE"]
    resync_on_start: bool = True
    interval: int = 60

    def to_request(self) -> dict[str, Any]:
        return {}


class SampleTriggerChannel(BaseTriggerChannel):
    def __init__(
        self,
        events: TriggerChannelEvents,
        trigger_channel_config: SampleTriggerChannelSettings,
    ):
        super().__init__(events)
        self.trigger_channel_config = trigger_channel_config
        self._last_updated_at = None

    async def start(self) -> None:
        logger.info(
            f"Setting up Sample trigger channel with interval: {self.trigger_channel_config.interval}"
        )

        @repeat_every(seconds=self.trigger_channel_config.interval)
        async def resync() -> None:
            logger.info(
                f"Sample trigger channel iteration after {self.trigger_channel_config.interval}. Checking for changes"
            )
            integration = await ocean.app.port_client.get_current_integration()
            last_updated_at = integration["updatedAt"]

            should_resync = (
                self._last_updated_at is not None
                or self.trigger_channel_config.resync_on_start
            ) and self._last_updated_at != last_updated_at

            if should_resync:
                logger.info("Detected change in integration, resyncing")
                self._last_updated_at = last_updated_at
                await ocean.sync_raw_all()

        # Execute resync repeatedly task
        await resync()
