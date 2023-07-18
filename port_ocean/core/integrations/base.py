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
from port_ocean.core.integrations.mixins.sync import SyncRawMixin, SyncMixin
from port_ocean.exceptions.core import IntegrationAlreadyStartedException


class BaseIntegration(SyncRawMixin, SyncMixin):
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
        logger.info("Starting integration")
        if self.started:
            raise IntegrationAlreadyStartedException("Integration already started")

        if (
            not self.event_strategy["resync"]
            and self.__class__._on_resync == BaseIntegration._on_resync
        ):
            raise NotImplementedError("on_resync is not implemented")

        await self.initialize_handlers()

        logger.info("Initializing integration at port")
        await self.context.port_client.initialize_integration(
            self.context.config.integration.type,
            self.context.config.event_listener.to_request(),
        )

        self.started = True

        async with event_context(EventType.START, trigger_type="machine"):
            await asyncio.gather(
                *(listener() for listener in self.event_strategy["start"])
            )

        logger.info("Initializing event listener")
        event_listener = await self.event_listener_factory.create_event_listener()
        await event_listener.start()
