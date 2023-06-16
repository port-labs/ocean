from typing import Callable, Dict, Any, Awaitable

from port_ocean.consumers.kafka_consumer import KafkaConsumerConfig
from port_ocean.core.base import BaseWithContext
from port_ocean.core.trigger_channel.base_trigger_channel import (
    BaseTriggerChannel,
    TriggerEventEvents,
)
from port_ocean.core.trigger_channel.kafka_trigger_channel import KafkaTriggerChannel

from port_ocean.context.integration import PortOceanContext


class TriggerChannelFactory(BaseWithContext):
    def __init__(
        self,
        context: PortOceanContext,
        installation_id: str,
        trigger_channel_type: str,
        events: TriggerEventEvents,
    ):
        super().__init__(context)
        self.installation_id = installation_id
        self.trigger_channel_type = trigger_channel_type
        self._trigger_channel: BaseTriggerChannel | None = None
        self.events = events

    def on_event(
        self, callback: Callable[[Dict[Any, Any]], Awaitable[None]]
    ) -> Callable[[Dict[Any, Any]], Awaitable[None]]:
        async def wrapper(event: Dict[Any, Any]) -> None:
            integration_identifier = (
                event.get("diff", {}).get("after", {}).get("identifier")
            )

            if integration_identifier == self.installation_id:
                await callback(event)

        return wrapper

    async def create_trigger_channel(self) -> None:
        if self.trigger_channel_type.lower() == "kafka":
            kafka_creds = await self.context.port_client.get_kafka_creds()
            org_id = await self.context.port_client.get_org_id()
            self._trigger_channel = KafkaTriggerChannel(
                {
                    "on_resync": self.on_event(self.events["on_resync"]),
                    "on_action": self.on_event(self.events["on_action"]),
                },
                KafkaConsumerConfig(
                    username=kafka_creds["username"],
                    password=kafka_creds["password"],
                    brokers=self.context.config.trigger_channel.brokers,
                    security_protocol=self.context.config.trigger_channel.security_protocol,
                    authentication_mechanism=self.context.config.trigger_channel.authentication_mechanism,
                    kafka_security_enabled=self.context.config.trigger_channel.kafka_security_enabled,
                ),
                org_id,
            )
        else:
            raise Exception(
                f"Trigger channel {self.trigger_channel_type} not supported"
            )

        self._trigger_channel.start()
