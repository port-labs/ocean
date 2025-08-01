from loguru import logger

from port_ocean.context.ocean import PortOceanContext
from port_ocean.core.ocean_types import EventListenerType
from port_ocean.core.event_listener import (
    KafkaEventListener,
    PollingEventListener,
    OnceEventListenerSettings,
    OnceEventListener,
)
from port_ocean.core.event_listener import (
    KafkaEventListenerSettings,
    PollingEventListenerSettings,
)
from port_ocean.core.event_listener.base import (
    BaseEventListener,
    EventListenerEvents,
)
from port_ocean.core.event_listener.webhooks_only import (
    WebhooksOnlyEventListener,
    WebhooksOnlyEventListenerSettings,
)
from port_ocean.exceptions.core import UnsupportedEventListenerTypeException


class EventListenerFactory:
    """
    This class is responsible for creating different types of event listeners based on the provided configuration.
    The factory takes a PortOceanContext, installation_id, and events dictionary as parameters.

    Parameters:
        context (PortOceanContext): The PortOceanContext object containing information about the current application context.
        installation_id (str): The identifier of the installation associated with the event listener.
        events (EventListenerEvents): A dictionary containing event types and their corresponding event handlers.

    """

    def __init__(
        self,
        context: PortOceanContext,
        installation_id: str,
        events: EventListenerEvents,
    ):
        self.context = context
        self.installation_id = installation_id
        self.events = events

    async def create_event_listener(self) -> BaseEventListener:
        """
        Creates and returns a specific event listener based on the provided configuration.
        The event listener is wrapped with the events provided in the factory's initialization.

        Raises:
            UnsupportedEventListenerTypeException: If the event listener type is not supported.
        """
        wrapped_events: EventListenerEvents = {"on_resync": self.events["on_resync"]}
        event_listener: BaseEventListener
        config = self.context.config.event_listener
        _type = config.type.lower()
        assert_message = "Invalid event listener config, expected KafkaEventListenerSettings and got {0}"
        logger.info(
            "Creating event listener",
            type=_type,
            integration_id=self.installation_id,
            integration_type=self.context.config.integration.type,
        )

        match _type:
            case EventListenerType.KAFKA.lower():
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
                logger.info(
                    "Initialized Kafka event listener with configuration",
                    brokers=config.brokers,
                    security_enabled=config.kafka_security_enabled,
                )

            case EventListenerType.POLLING.lower():
                assert isinstance(
                    config, PollingEventListenerSettings
                ), assert_message.format(type(config))
                event_listener = PollingEventListener(wrapped_events, config)
                logger.info(
                    "Initialized Polling event listener with configuration",
                    interval=config.interval,
                    resync_on_start=config.resync_on_start,
                )

            case EventListenerType.ONCE.lower():
                assert isinstance(
                    config, OnceEventListenerSettings
                ), assert_message.format(type(config))
                event_listener = OnceEventListener(wrapped_events, config)
                logger.info("Initialized Once event listener")

            case EventListenerType.WEBHOOKS_ONLY.lower():
                assert isinstance(
                    config, WebhooksOnlyEventListenerSettings
                ), assert_message.format(type(config))
                event_listener = WebhooksOnlyEventListener(wrapped_events, config)
                logger.info("Initialized Webhooks-only event listener")

            case _:
                raise UnsupportedEventListenerTypeException(
                    f"Event listener {_type} not supported"
                )

        return event_listener
