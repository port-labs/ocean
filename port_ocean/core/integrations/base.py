import asyncio

from loguru import logger

from port_ocean.context.event import (
    event_context,
    EventType,
)
from port_ocean.context.ocean import PortOceanContext
from port_ocean.core.event_listener.factory import (
    EventListenerFactory,
)
from port_ocean.core.integrations.mixins import SyncRawMixin, SyncMixin
from port_ocean.exceptions.core import IntegrationAlreadyStartedException


class BaseIntegration(SyncRawMixin, SyncMixin):
    """
    This is the default integration class that Ocean initializes when no custom integration class is
    provided.

    This class provides a foundation for implementing various integration types. It inherits from
    both SyncRawMixin and SyncMixin, which provide synchronization and event handling functionality.

    Parameters:
        context (PortOceanContext): The PortOceanContext object providing the necessary context
            for the integration.

    Attributes:
        started (bool): Flag indicating whether the integration has been started.
        context (PortOceanContext): The PortOceanContext object containing integration context.
        event_listener_factory (EventListenerFactory): Factory to create event listeners for
            handling integration events.

    Raises:
        IntegrationAlreadyStartedException: Raised if the integration is attempted to be started
            more than once.
        NotImplementedError: Raised if the `on_resync` method is not implemented, and the event
            strategy does not have a custom implementation for resync events.
    """

    def __init__(self, context: PortOceanContext):
        SyncRawMixin.__init__(self)
        SyncMixin.__init__(self)
        self.started = False
        self.context = context
        self.event_listener_factory = EventListenerFactory(
            context,
            self.context.config.integration.identifier,
            {"on_resync": self.sync_raw_all},
        )

    async def start(self) -> None:
        """
        Initializes handlers, establishes integration at the specified port, and starts the event listener.
        """
        logger.info(
            "Starting integration",
            integration_type=self.context.config.integration.type,
        )
        if self.started:
            raise IntegrationAlreadyStartedException("Integration already started")

        if (
            not self.event_strategy["resync"]
            and self.__class__._on_resync == BaseIntegration._on_resync
            and self.context.config.event_listener.should_resync
        ):
            raise NotImplementedError("on_resync is not implemented")

        await self.initialize_handlers()

        self.started = True

        async with event_context(
            EventType.START,
            trigger_type="machine",
        ):
            await asyncio.gather(
                *(listener() for listener in self.event_strategy["start"])
            )

        logger.info("Initializing event listener")
        event_listener = await self.event_listener_factory.create_event_listener()
        await event_listener.start()
