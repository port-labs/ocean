import logging
import signal
from typing import Any, Callable

from confluent_kafka import Consumer, KafkaException, Message
from consumers.base import BaseConsumer

from config.config import settings

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

class KafkaConsumer(BaseConsumer):

    def __init__(
        self, msg_process: Callable[[Message], None], consumer: Consumer = None, kafka_creds: dict = None, org_id: str = None
    ) -> None:
        self.running = False
        self.org_id = org_id

        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

        self.msg_process = msg_process

        if consumer:
            self.consumer = consumer
        else:
            conf = {
                "bootstrap.servers": settings.KAFKA_CONSUMER_BROKERS,
                "security.protocol": settings.KAFKA_CONSUMER_SECURITY_PROTOCOL,
                "sasl.mechanism": settings.KAFKA_CONSUMER_AUTHENTICATION_MECHANISM,
                "sasl.username": kafka_creds['username'],
                "sasl.password": kafka_creds['password'],
                "group.id": kafka_creds['username'],
                "enable.auto.commit": "false",
            }
            self.consumer = Consumer(conf)

    def start(self) -> None:
        try:
            self.consumer.subscribe(
                [f"{self.org_id}.runs", f"{self.org_id}.change.log"],
                on_assign=lambda _, partitions: logger.info(
                    "Assignment: %s", partitions
                ),
            )
            self.running = True
            while self.running:
                try:
                    msg = self.consumer.poll(timeout=1.0)
                    if msg is None:
                        continue
                    if msg.error():
                        raise KafkaException(msg.error())
                    else:
                        try:
                            logger.info(
                                "Process message"
                                " from topic %s, partition %d, offset %d",
                                msg.topic(),
                                msg.partition(),
                                msg.offset(),
                            )
                            self.msg_process(msg)
                        except Exception as process_error:
                            logger.error(
                                "Failed process message"
                                " from topic %s, partition %d, offset %d: %s",
                                msg.topic(),
                                msg.partition(),
                                msg.offset(),
                                str(process_error),
                            )
                        finally:
                            self.consumer.commit(asynchronous=False)
                except Exception as message_error:
                    logger.error(str(message_error))
        finally:
            self.consumer.close()

    def exit_gracefully(self, *_: Any) -> None:
        logger.info("Exiting gracefully...")
        self.running = False