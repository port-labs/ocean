from typing import Dict, Any

from port_ocean.consumers.kafka_consumer import KafkaConsumer, KafkaConsumerConfig
from port_ocean.core.trigger_channel.base_trigger_channel import BaseTriggerChannel
from port_ocean.core.trigger_channel.models import Events


class KafkaTriggerChannel(BaseTriggerChannel):
    def __init__(
        self,
        events: Events,
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

        match topic:
            case "runs":
                # await self.on_action(message)
                await self.events["on_action"](message)

            case "change.log":
                await self.events["on_resync"](message)

    def start(self) -> None:
        KafkaConsumer(
            msg_process=self._handle_message,
            org_id=self.org_id,
            config=self.kafka_credentials,
        ).start()
