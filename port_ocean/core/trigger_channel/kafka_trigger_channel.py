import threading
from typing import Dict, Any, Callable

from port_ocean.consumers.kafka_consumer import KafkaConsumer, KafkaConsumerConfig
from port_ocean.context.ocean import (
    PortOceanContext,
    initialize_port_ocean_context,
    ocean,
)
from port_ocean.core.trigger_channel.base_trigger_channel import (
    BaseTriggerChannel,
    TriggerEventEvents,
)


class KafkaTriggerChannel(BaseTriggerChannel):
    def __init__(
        self,
        events: TriggerEventEvents,
        kafka_credentials: KafkaConsumerConfig,
        org_id: str,
    ):
        super().__init__(events)
        self.kafka_credentials = kafka_credentials
        self.org_id = org_id

    def should_be_processed(self, msg_value: Dict[Any, Any], topic: str) -> bool:
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

    async def _handle_message(self, message: Dict[Any, Any], topic: str) -> None:
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

    def start(self) -> None:
        consumer = KafkaConsumer(
            msg_process=self._handle_message,
            org_id=self.org_id,
            config=self.kafka_credentials,
        )
        threading.Thread(
            name="ocean_kafka_consumer",
            target=self.wrapped_start(ocean, consumer.start),
        ).start()
