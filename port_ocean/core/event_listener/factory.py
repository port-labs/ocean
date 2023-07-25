from loguru import logger

from port_ocean.context.ocean import PortOceanContext
from port_ocean.core.base import BaseWithContext
from port_ocean.core.event_listener import (
    HttpEventListener,
    KafkaEventListener,
    PollingEventListener,
)
from port_ocean.core.event_listener import (
    HttpEventListenerSettings,
    KafkaEventListenerSettings,
    PollingEventListenerSettings,
)
from port_ocean.core.event_listener.base import (
    BaseEventListener,
    EventListenerEvents,
)
from port_ocean.exceptions.core import UnsupportedEventListenerTypeException


class EventListenerFactory(BaseWithContext):
    def __init__(
        self,
        context: PortOceanContext,
        installation_id: str,
        events: EventListenerEvents,
    ):
        super().__init__(context)
        self.installation_id = installation_id
        self.events = events

    async def create_event_listener(self) -> BaseEventListener:
        wrapped_events: EventListenerEvents = {"on_resync": self.events["on_resync"]}
        event_listener: BaseEventListener
        config = self.context.config.event_listener
        _type = config.type.lower()
        assert_message = "Invalid event listener config, expected KafkaEventListenerSettings and got {0}"
        logger.info(f"Found event listener type: {_type}")

        match _type:
            case "kafka":
                assert isinstance(
                    config, KafkaEventListenerSettings
                ), assert_message.format(type(config))
                org_id = await self.context.port_client.get_org_id()
                event_listener = KafkaEventListener(
                    wrapped_events,
                    config,
                    org_id,
                    self.context.config.integration.identifier,
                    self.context.config.integration.type,
                )

            case "webhook":
                assert isinstance(
                    config, HttpEventListenerSettings
                ), assert_message.format(type(config))
                event_listener = HttpEventListener(wrapped_events, config)

            case "polling":
                assert isinstance(
                    config, PollingEventListenerSettings
                ), assert_message.format(type(config))
                event_listener = PollingEventListener(wrapped_events, config)

            case _:
                raise UnsupportedEventListenerTypeException(
                    f"Event listener {_type} not supported"
                )

        return event_listener
