from fastapi import APIRouter

from port_ocean.context.ocean import ocean
from port_ocean.core.trigger_channel.base import (
    BaseTriggerChannel,
    TriggerChannelEvents,
)
from port_ocean.core.trigger_channel.settings import HttpTriggerChannelSettings


class HttpTriggerChannel(BaseTriggerChannel[HttpTriggerChannelSettings]):
    def __init__(
        self,
        events: TriggerChannelEvents,
        trigger_channel_config: HttpTriggerChannelSettings,
        org_id: str,
    ):
        super().__init__(events, trigger_channel_config)
        self.org_id = org_id

    async def start(self) -> None:
        target_channel_router = APIRouter()

        @target_channel_router.post("/resync")
        async def resync() -> None:
            await self.events["on_resync"]({})

        ocean.app.fast_api_app.include_router(target_channel_router)
