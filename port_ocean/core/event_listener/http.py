from typing import Literal, Any

from fastapi import APIRouter
from loguru import logger
from pydantic import AnyHttpUrl
from pydantic.fields import Field

from port_ocean.context.ocean import ocean
from port_ocean.core.event_listener.base import (
    BaseEventListener,
    EventListenerEvents,
    EventListenerSettings,
)


class HttpEventListenerSettings(EventListenerSettings):
    """
    This class inherits from `EventListenerSettings`, which provides a foundation for defining event listener configurations.
    The `HttpEventListenerSettings` specifically includes settings related to the HTTP event listener (Webhook).

    Attributes:
        type (Literal["WEBHOOK"]): A literal indicating the type of the event listener, which is set to "WEBHOOK" for this class.
        app_host (AnyHttpUrl): The base URL of the application hosting the webhook.
                               The "AnyHttpUrl" type indicates that the value must be a valid HTTP/HTTPS URL.
    """

    type: Literal["WEBHOOK"]
    app_host: AnyHttpUrl = Field(..., sensitive=True)

    def get_changelog_destination_details(self) -> dict[str, Any]:
        """
        Returns the changelog destination configuration for the webhook event listener.
        For webhook event listeners, this specifies the URL where changelog events should be sent.

        Returns:
            dict[str, Any]: A dictionary with the webhook URL where changelog events should be sent,
                           constructed by appending "/resync" to the app_host.
        """
        return {
            "type": self.type,
            "url": self.app_host + "/resync",
        }


class HttpEventListener(BaseEventListener):
    """
    HTTP event listener that listens for webhook events and triggers "on_resync" event.

    This class inherits from `BaseEventListener`, which provides a foundation for creating event listeners.
    The `HttpEventListener` listens for HTTP POST requests to the `/resync` endpoint and triggers the "on_resync" event.

    Parameters:
        events (EventListenerEvents): A dictionary containing event types and their corresponding event handlers.
        event_listener_config (HttpEventListenerSettings): Configuration settings for the HTTP event listener.
    """

    def __init__(
        self,
        events: EventListenerEvents,
        event_listener_config: HttpEventListenerSettings,
    ):
        super().__init__(events)
        self.event_listener_config = event_listener_config

    async def _start(self) -> None:
        """
        Starts the HTTP event listener.
        It sets up an APIRouter to handle the `/resync` endpoint and registers the "on_resync" event handler.
        """
        logger.info("Setting up HTTP Event Listener")
        target_channel_router = APIRouter()

        @target_channel_router.post("/resync")
        async def resync() -> None:
            await self._resync({})

        ocean.app.fast_api_app.include_router(target_channel_router)
