import threading
from typing import Any, Callable, Literal

from loguru import logger

from port_ocean.consumers.kafka_consumer import KafkaConsumer, KafkaConsumerConfig
from port_ocean.context.ocean import (
    PortOceanContext,
    initialize_port_ocean_context,
    ocean,
)
from port_ocean.core.event_listener.base import (
    BaseEventListener,
    EventListenerEvents,
    EventListenerSettings,
)


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
    brokers: str = "b-1-public.publicclusterprod.t9rw6w.c1.kafka.eu-west-1.amazonaws.com:9196,b-2-public.publicclusterprod.t9rw6w.c1.kafka.eu-west-1.amazonaws.com:9196,b-3-public.publicclusterprod.t9rw6w.c1.kafka.eu-west-1.amazonaws.com:9196"
    security_protocol: str = "SASL_SSL"
    authentication_mechanism: str = "SCRAM-SHA-512"
    kafka_security_enabled: bool = True
    consumer_poll_timeout: int = 1


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
        if integration_identifier == self.integration_identifier and (
            "change.log" in topic
        ):
            return msg_value.get("changelogDestination", {}).get("type", "") == "KAFKA"

        return False

    async def _handle_message(self, message: dict[Any, Any], topic: str) -> None:
        """
        A private method that handles incoming Kafka messages.
        If the message should be processed (determined by `_should_be_processed`), it triggers the corresponding event handler.
        """
        if not self._should_be_processed(message, topic):
            return

        if "change.log" in topic and message is not None:
            await self.events["on_resync"](message)

    def _wrapped_start(
        self, context: PortOceanContext, func: Callable[[], None]
    ) -> Callable[[], None]:
        """
        A method that wraps the `start` method, initializing the PortOceanContext and invoking the given function.
        """
        ocean_app = context.app

        def wrapper() -> None:
            initialize_port_ocean_context(ocean_app=ocean_app)
            func()

        return wrapper

    async def start(self) -> None:
        """
        The main method that starts the Kafka consumer.
        It creates a KafkaConsumer instance with the given configuration and starts it in a separate thread.
        """
        consumer = KafkaConsumer(
            msg_process=self._handle_message,
            config=await self._get_kafka_config(),
            org_id=self.org_id,
        )
        logger.info("Starting Kafka consumer")
        threading.Thread(
            name="ocean_kafka_consumer",
            target=self._wrapped_start(ocean, consumer.start),
        ).start()
