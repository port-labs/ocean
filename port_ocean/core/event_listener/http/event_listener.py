from typing import Literal, Any

from fastapi import APIRouter
from loguru import logger
from pydantic import AnyHttpUrl

from port_ocean.context.ocean import ocean
from port_ocean.core.event_listener.base import (
    BaseEventListener,
    EventListenerEvents,
    EventListenerSettings,
)


class HttpEventListenerSettings(EventListenerSettings):
    type: Literal["WEBHOOK"]
    app_host: AnyHttpUrl

    def to_request(self) -> dict[str, Any]:
        return {
            **super().to_request(),
            "url": self.app_host + "/resync",
        }


class HttpEventListener(BaseEventListener):
    def __init__(
        self,
        events: EventListenerEvents,
        event_listener_config: HttpEventListenerSettings,
    ):
        super().__init__(events)
        self.event_listener_config = event_listener_config

    async def start(self) -> None:
        logger.info("Setting up HTTP Event Listener")
        target_channel_router = APIRouter()

        @target_channel_router.post("/resync")
        async def resync() -> None:
            await self.events["on_resync"]({})

        ocean.app.fast_api_app.include_router(target_channel_router)
