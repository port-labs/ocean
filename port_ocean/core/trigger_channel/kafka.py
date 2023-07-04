import threading
from typing import Any, Callable

from loguru import logger

from port_ocean.consumers.kafka_consumer import KafkaConsumer, KafkaConsumerConfig
from port_ocean.context.ocean import (
    PortOceanContext,
    initialize_port_ocean_context,
    ocean,
)
from port_ocean.core.trigger_channel.base import (
    BaseTriggerChannel,
    TriggerChannelEvents,
)
from port_ocean.core.trigger_channel.settings import KafkaTriggerChannelSettings


class KafkaTriggerChannel(BaseTriggerChannel):
    def __init__(
        self,
        events: TriggerChannelEvents,
        trigger_channel_config: KafkaTriggerChannelSettings,
        org_id: str,
        integration_identifier: str,
        integration_type: str,
    ):
        super().__init__(events)
        self.trigger_channel_config = trigger_channel_config
        self.org_id = org_id
        self.integration_identifier = integration_identifier
        self.integration_type = integration_type

    async def _get_kafka_config(self) -> KafkaConsumerConfig:
        if self.trigger_channel_config.kafka_security_enabled:
            creds = await ocean.port_client.get_kafka_creds()
            return KafkaConsumerConfig(
                username=creds.get("username"),
                password=creds.get("password"),
                brokers=self.trigger_channel_config.brokers,
                security_protocol=self.trigger_channel_config.security_protocol,
                authentication_mechanism=self.trigger_channel_config.authentication_mechanism,
                kafka_security_enabled=self.trigger_channel_config.kafka_security_enabled,
                group_name=f"{self.integration_type}.{self.integration_identifier}",
            )

        return KafkaConsumerConfig(
            brokers=self.trigger_channel_config.brokers,
            security_protocol=self.trigger_channel_config.security_protocol,
            authentication_mechanism=self.trigger_channel_config.authentication_mechanism,
            kafka_security_enabled=self.trigger_channel_config.kafka_security_enabled,
        )

    def should_be_processed(self, msg_value: dict[Any, Any], topic: str) -> bool:
        if "runs" in topic:
            return (
                msg_value.get("payload", {})
                .get("action", {})
                .get("invocationMethod", {})
                .get("type", "")
                == "KAFKA"
            )

        if "change.log" in topic:
            return msg_value.get("changelogDestination", {}).get("type", "") == "KAFKA"

        return False

    async def _handle_message(self, message: dict[Any, Any], topic: str) -> None:
        if not self.should_be_processed(message, topic):
            return

        if "change.log" in topic:
            await self.events["on_resync"](message)

        if "runs" in topic:
            await self.events["on_action"](message)

    def wrapped_start(
        self, context: PortOceanContext, func: Callable[[], None]
    ) -> Callable[[], None]:
        ocean_app = context.app

        def wrapper() -> None:
            initialize_port_ocean_context(ocean_app=ocean_app)
            func()

        return wrapper

    async def start(self) -> None:
        consumer = KafkaConsumer(
            msg_process=self._handle_message,
            config=await self._get_kafka_config(),
            org_id=self.org_id,
        )
        logger.info("Starting Kafka consumer")
        threading.Thread(
            name="ocean_kafka_consumer",
            target=self.wrapped_start(ocean, consumer.start),
        ).start()
