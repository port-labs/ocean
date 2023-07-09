from typing import Callable, Any, Awaitable

from loguru import logger

from port_ocean.context.ocean import PortOceanContext
from port_ocean.core.base import BaseWithContext
from port_ocean.core.trigger_channel.base import (
    BaseTriggerChannel,
    TriggerChannelEvents,
)
from port_ocean.core.trigger_channel.http import (
    HttpTriggerChannel,
)
from port_ocean.core.trigger_channel.kafka import (
    KafkaTriggerChannel,
)
from port_ocean.core.trigger_channel.settings import (
    HttpTriggerChannelSettings,
    KafkaTriggerChannelSettings,
)
from port_ocean.exceptions.core import UnsupportedTriggerChannelException


class TriggerChannelFactory(BaseWithContext):
    def __init__(
        self,
        context: PortOceanContext,
        installation_id: str,
        events: TriggerChannelEvents,
    ):
        super().__init__(context)
        self.installation_id = installation_id
        self.events = events

    def on_event(
        self, callback: Callable[[dict[Any, Any]], Awaitable[None]]
    ) -> Callable[[dict[Any, Any]], Awaitable[None]]:
        async def wrapper(event: dict[Any, Any]) -> None:
            integration_identifier = (
                event.get("diff", {}).get("after", {}).get("identifier")
            )

            if integration_identifier == self.installation_id:
                await callback(event)

        return wrapper

    async def create_trigger_channel(self) -> BaseTriggerChannel:
        wrapped_events: TriggerChannelEvents = {
            "on_resync": self.on_event(self.events["on_resync"])
        }
        trigger_channel: BaseTriggerChannel
        config = self.context.config.trigger_channel
        _type = config.type.lower()
        assert_message = "Invalid trigger channel config, expected KafkaTriggerChannelSettings and got {0}"
        logger.info(f"Found trigger channel type: {_type}")

        match _type:
            case "kafka":
                assert isinstance(
                    config, KafkaTriggerChannelSettings
                ), assert_message.format(type(config))
                org_id = await self.context.port_client.get_org_id()
                trigger_channel = KafkaTriggerChannel(
                    wrapped_events,
                    config,
                    org_id,
                    self.context.config.integration.identifier,
                    self.context.config.integration.type,
                )

            case "webhook":
                assert isinstance(
                    config, HttpTriggerChannelSettings
                ), assert_message.format(type(config))
                trigger_channel = HttpTriggerChannel(wrapped_events, config)

            case _:
                raise UnsupportedTriggerChannelException(
                    f"Trigger channel {_type} not supported"
                )

        return trigger_channel
