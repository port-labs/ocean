from fastapi import APIRouter
from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.trigger_channel.base import (
    BaseTriggerChannel,
    TriggerChannelEvents,
)
from port_ocean.core.trigger_channel.settings import HttpTriggerChannelSettings


class HttpTriggerChannel(BaseTriggerChannel):
    def __init__(
        self,
        events: TriggerChannelEvents,
        trigger_channel_config: HttpTriggerChannelSettings,
    ):
        super().__init__(events)
        self.trigger_channel_config = trigger_channel_config

    async def start(self) -> None:
        logger.info("Setting up HTTP trigger channel")
        target_channel_router = APIRouter()

        @target_channel_router.post("/resync")
        async def resync() -> None:
            await self.events["on_resync"]({})

        ocean.app.fast_api_app.include_router(target_channel_router)
