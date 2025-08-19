import asyncio
import json
import sys
from asyncio import ensure_future, Task
from typing import Any, Literal

from confluent_kafka import Message  # type: ignore
from loguru import logger

from port_ocean.consumers.kafka_consumer import KafkaConsumer, KafkaConsumerConfig
from port_ocean.context.ocean import (
    ocean,
)
from port_ocean.core.event_listener.base import (
    BaseEventListener,
    EventListenerEvents,
    EventListenerSettings,
)
from pydantic import validator


class KafkaEventListenerSettings(EventListenerSettings):
    """
    This class inherits from `EventListenerSettings`, which provides a foundation for defining event listener configurations.
    The `KafkaEventListenerSettings` specifically includes settings related to the Kafka event listener.

    Attributes:
        type (Literal["KAFKA"]): A literal indicating the type of the event listener, which is set to "KAFKA" for this class.
        brokers (str): The comma-separated list of Kafka broker URLs to connect to.
        security_protocol (str): The security protocol used for communication with Kafka brokers.
                                 The default value is "SASL_SSL".
        authentication_mechanism (str): The authentication mechanism used for secure access to Kafka brokers.
                                        The default value is "SCRAM-SHA-512".
        kafka_security_enabled (bool): A flag indicating whether Kafka security is enabled.
                                       If True, credentials and security settings are used to connect to Kafka.
                                       The default value is True.
        consumer_poll_timeout (int): The maximum time in seconds to wait for messages during a poll.
                                     The default value is 1 second.
    """

    type: Literal["KAFKA"]
    brokers: str = (
        "b-1-public.publicclusterprod.t9rw6w.c1.kafka.eu-west-1.amazonaws.com:9196,b-2-public.publicclusterprod.t9rw6w.c1.kafka.eu-west-1.amazonaws.com:9196,b-3-public.publicclusterprod.t9rw6w.c1.kafka.eu-west-1.amazonaws.com:9196"
    )
    security_protocol: str = "SASL_SSL"
    authentication_mechanism: str = "SCRAM-SHA-512"
    kafka_security_enabled: bool = True
    consumer_poll_timeout: int = 1

    @validator("brokers")
    @classmethod
    def parse_brokers(cls, v: str) -> str:
        # If it's a JSON array string, parse and join
        if v.strip().startswith("[") and v.strip().endswith("]"):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return ",".join(parsed)
            except json.JSONDecodeError:
                pass
        return v

    def get_changelog_destination_details(self) -> dict[str, Any]:
        """
        Returns the changelog destination configuration for the Kafka event listener.
        For Kafka event listeners, this specifies that changelog events should be sent via Kafka.

        Returns:
            dict[str, Any]: A dictionary with type "KAFKA" to indicate that changelog events
                           should be sent through the Kafka message bus.
        """
        return {
            "type": self.type,
        }


class KafkaEventListener(BaseEventListener):
    """
    The `KafkaEventListener` specifically listens for messages from a Kafka consumer related to changes in an integration.

    Parameters:
        events (EventListenerEvents): A dictionary containing event types and their corresponding event handlers.
        event_listener_config (KafkaEventListenerSettings): Configuration settings for the Kafka event listener.
        org_id (str): The identifier of the organization associated with the integration.
        integration_identifier (str): The identifier of the integration being monitored.
        integration_type (str): The type of the integration being monitored.
    """

    def __init__(
        self,
        events: EventListenerEvents,
        event_listener_config: KafkaEventListenerSettings,
        org_id: str,
        integration_identifier: str,
        integration_type: str,
    ):
        super().__init__(events)
        self.event_listener_config = event_listener_config
        self.org_id = org_id
        self.integration_identifier = integration_identifier
        self.integration_type = integration_type
        self._running_task: Task[Any] | None = None
        self.consumer: KafkaConsumer | None = None

    async def _get_kafka_config(self) -> KafkaConsumerConfig:
        """
        A private method that returns the Kafka consumer configuration based on the provided settings.
        If Kafka security is enabled, it fetches Kafka credentials using the ocean.port_client.get_kafka_creds() method.
        Otherwise, it returns the KafkaConsumerConfig object parsed from the event_listener_config.
        """
        if self.event_listener_config.kafka_security_enabled:
            creds = await ocean.port_client.get_kafka_creds()
            return KafkaConsumerConfig(
                **self.event_listener_config.dict(),
                username=creds.get("username"),
                password=creds.get("password"),
                group_name=f"{self.integration_type}.{self.integration_identifier}",
            )

        return KafkaConsumerConfig.parse_obj(self.event_listener_config.dict())

    def _should_be_processed(self, msg_value: dict[Any, Any], topic: str) -> bool:
        after = msg_value.get("diff", {}).get("after", {})
        # handles delete events from change log where there is no after
        if after is None:
            return False

        integration_identifier = after.get("identifier")
        if integration_identifier != self.integration_identifier:
            return False

        if after.get("updatedAt") == after.get("resyncState", {}).get("updatedAt"):
            return False

        if "change.log" in topic:
            return msg_value.get("changelogDestination", {}).get("type", "") == "KAFKA"

        return False

    async def _handle_message(self, raw_msg: Message) -> None:
        """
        A private method that handles incoming Kafka messages.
        If the message should be processed (determined by `_should_be_processed`), it triggers the corresponding event handler.

        Spawning a thread to handle the message allows the Kafka consumer to continue polling for new messages.
        Using wrap_method_with_context ensures that the thread has access to the current context.
        """
        message = json.loads(raw_msg.value().decode())
        topic = raw_msg.topic()

        if not self._should_be_processed(message, topic):
            return

        if "change.log" in topic and message is not None:
            try:
                await self._resync(message)
            except Exception as e:
                _type, _, tb = sys.exc_info()
                logger.opt(exception=(_type, None, tb)).error(
                    f"Failed to process message: {str(e)}"
                )

    async def _start(self) -> None:
        """
        The main method that starts the Kafka consumer.
        It creates a KafkaConsumer instance with the given configuration and starts it in a separate thread.
        """
        self.consumer = KafkaConsumer(
            msg_process=self._handle_message,
            config=await self._get_kafka_config(),
            org_id=self.org_id,
        )
        logger.info("Starting Kafka consumer")

        # We are running the consumer with asyncio.create_task to ensure that it runs in the background and not blocking
        # the integration's main event loop from finishing the startup process.
        self._running_task = asyncio.create_task(self.consumer.start())
        ensure_future(self._running_task)

    def _stop(self) -> None:
        if self.consumer:
            self.consumer.exit_gracefully()
        if self._running_task:
            self._running_task.cancel()
