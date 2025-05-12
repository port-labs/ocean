from typing import Literal

from loguru import logger

from port_ocean.core.event_listener.base import (
    BaseEventListener,
    EventListenerEvents,
    EventListenerSettings,
)


class TaskEventListenerSettings(EventListenerSettings):
    """
    This class inherits from `EventListenerSettings`, which provides a foundation for creating event listener settings.
    """

    type: Literal["TASK"]


class TaskEventListener(BaseEventListener):
    """
    No resync event listener.

    It is used to handle events exclusively through webhooks without supporting resync events.

    Parameters:
        events (EventListenerEvents): A dictionary containing event types and their corresponding event handlers.
        event_listener_config (OnceEventListenerSettings): The event listener configuration settings.
    """

    def __init__(
        self,
        events: EventListenerEvents,
        event_listener_config: TaskEventListenerSettings,
    ):
        super().__init__(events)
        self.event_listener_config = event_listener_config

    async def _start(self) -> None:
        logger.info("Starting Task event listener")
