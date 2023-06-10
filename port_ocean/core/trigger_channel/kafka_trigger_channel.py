import json
from port_ocean.consumers.kafka_consumer import KafkaConsumer
from port_ocean.core.trigger_channel.base_trigger_channel import BaseTriggerChannel
from port_ocean.port.port import PortClient
from port_ocean.config.config import settings


class KafkaTriggerChannel(BaseTriggerChannel):
    def __init__(self, on_action: callable, on_changelog_event: callable):
        self.on_action = on_action
        self.on_changelog_event = on_changelog_event

    def should_be_processed(self, msg_value: dict, topic: str) -> dict:
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

    def _handle_message(self, raw_msg):
        message = json.loads(raw_msg.value().decode())
        topic = raw_msg.topic()

        if not self.should_be_processed(message, topic):
            return

        if "runs" in topic:
            self.on_action(message)
            return

        if "change.log" in topic:
            self.on_changelog_event()
            return

    def start(self) -> None:
        self.port_client = PortClient(
            settings.PORT_CLIENT_ID,
            settings.PORT_CLIENT_SECRET,
            "interation-port_ocean",
        )
        kafka_creds = self.port_client.get_kafka_creds()["credentials"]
        org_id = self.port_client.get_org_id()

        # starting kafka consumer
        KafkaConsumer(
            msg_process=self._handle_message, org_id=org_id, kafka_creds=kafka_creds
        ).start()
