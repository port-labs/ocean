import asyncio
import json
import signal
import sys
from typing import Any, Callable, Awaitable

from confluent_kafka import Consumer, KafkaException, Message  # type: ignore
from loguru import logger
from pydantic import BaseModel

from port_ocean.consumers.base_consumer import BaseConsumer


class KafkaConsumerConfig(BaseModel):
    brokers: str
    username: str | None = None
    password: str | None = None
    group_name: str | None = None
    security_protocol: str
    authentication_mechanism: str
    kafka_security_enabled: bool
    consumer_poll_timeout: int


class KafkaConsumer(BaseConsumer):
    def __init__(
        self,
        msg_process: Callable[[dict[Any, Any], str], Awaitable[None]],
        config: KafkaConsumerConfig,
        org_id: str,
    ) -> None:
        self.running = False
        self.org_id = org_id
        self.config = config

        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

        self.msg_process = msg_process
        if config.kafka_security_enabled:
            kafka_config = {
                "bootstrap.servers": config.brokers,
                "security.protocol": config.security_protocol,
                "sasl.mechanism": config.authentication_mechanism,
                "sasl.username": config.username,
                "sasl.password": config.password,
                "group.id": f"{self.org_id}.{config.group_name}",
                "enable.auto.commit": "false",
            }
        else:
            kafka_config = {
                "bootstrap.servers": config.brokers,
                "group.id": "no-security",
                "enable.auto.commit": "false",
            }

        self.consumer = Consumer(kafka_config)

    def _handle_message(self, raw_msg: Message) -> None:
        message = json.loads(raw_msg.value().decode())
        topic = raw_msg.topic()

        async def try_wrapper() -> None:
            try:
                await self.msg_process(message, topic)
            except Exception as e:
                _type, _, tb = sys.exc_info()
                logger.opt(exception=(_type, None, tb)).error(
                    f"Failed to process message: {str(e)}"
                )

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(try_wrapper())

    def start(self) -> None:
        try:
            logger.info("Start consumer...")

            self.consumer.subscribe(
                [f"{self.org_id}.change.log"],
                on_assign=lambda _, partitions: logger.info(
                    f"Assignment: {partitions}"
                ),
            )
            logger.info("Subscribed to topics")
            self.running = True
            while self.running:
                try:
                    msg = self.consumer.poll(timeout=self.config.consumer_poll_timeout)
                    if msg is None:
                        continue
                    if msg.error():
                        raise KafkaException(msg.error())
                    else:
                        try:
                            logger.info(
                                "Process message "
                                f"from topic {msg.topic()}, partition {msg.partition()}, offset {msg.offset()}"
                            )
                            self._handle_message(msg)
                        except Exception as process_error:
                            logger.exception(
                                "Failed process message"
                                f" from topic {msg.topic()}, partition {msg.partition()}, offset {msg.offset()}: {str(process_error)}"
                            )
                        finally:
                            self.consumer.commit(asynchronous=False)
                except Exception as message_error:
                    logger.error(str(message_error))
        finally:
            self.exit_gracefully()

    def exit_gracefully(self, *_: Any) -> None:
        logger.info("Exiting gracefully...")
        self.running = False
        self.consumer.close()
