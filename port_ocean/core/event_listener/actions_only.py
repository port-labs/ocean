from typing import Literal
from loguru import logger

from port_ocean.core.event_listener.base import (
    BaseEventListener,
    EventListenerEvents,
    EventListenerSettings,
)
from port_ocean.core.models import EventListenerType


class ActionsOnlyEventListenerSettings(EventListenerSettings):
    """
    This class inherits from `EventListenerSettings`, which provides a foundation for creating event listener settings.
    """

    type: Literal[EventListenerType.ACTIONS_ONLY]
    should_resync: bool = False
    should_process_webhooks: bool = False


class ActionsOnlyEventListener(BaseEventListener):
    """
    No resync event listener.

    It is used to handle events exclusively through actions without supporting resync events.

    Parameters:
        events (EventListenerEvents): A dictionary containing event types and their corresponding event handlers.
        event_listener_config (ActionsOnlyEventListenerSettings): The event listener configuration settings.
    """

    def __init__(
        self,
        events: EventListenerEvents,
        event_listener_config: ActionsOnlyEventListenerSettings,
    ):
        super().__init__(events)
        self.event_listener_config = event_listener_config

    async def _start(self) -> None:
        logger.info("Starting Actions-only event listener")
