import functools
import signal
import threading
from asyncio import get_running_loop
from typing import Any, Callable

from confluent_kafka import Consumer, KafkaException, Message  # type: ignore
from loguru import logger
from pydantic import BaseModel


class KafkaConsumerConfig(BaseModel):
    brokers: str
    username: str | None = None
    password: str | None = None
    group_name: str | None = None
    security_protocol: str
    authentication_mechanism: str
    kafka_security_enabled: bool
    consumer_poll_timeout: int


class KafkaConsumer:
    def __init__(
        self,
        msg_process: Callable[[Message], None],
        config: KafkaConsumerConfig,
        org_id: str,
    ) -> None:
        self.running = False
        self.org_id = org_id
        self.config = config

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

    def _handle_partitions_assignment(self, _, partitions: list[str]) -> None:
        logger.info(f"Assignment: {partitions}")
        if not partitions:
            logger.error(
                "No partitions assigned. This usually means that there is"
                " already another integration from the same type and with"
                " the same identifier running. Two integrations of the same"
                " type and identifier cannot run at the same time."
            )
            signal.raise_signal(signal.SIGINT)

    async def start(self, event: threading.Event) -> None:
        self.running = True
        logger.info("Start consumer...")

        self.consumer.subscribe(
            [f"{self.org_id}.change.log"],
            on_assign=self._handle_partitions_assignment,
        )
        logger.info("Subscribed to topics")

        loop = get_running_loop()
        poll = functools.partial(
            self.consumer.poll, timeout=self.config.consumer_poll_timeout
        )
        try:
            while self.running and not event.is_set():
                try:
                    msg = await loop.run_in_executor(None, poll)
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
                            self.msg_process(msg)

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
            logger.info("Closing consumer...")
            self.exit_gracefully()

    def exit_gracefully(self, *_: Any) -> None:
        logger.info("Exiting gracefully...")
        self.running = False
        self.consumer.close()
