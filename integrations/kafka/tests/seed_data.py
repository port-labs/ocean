"""
Kafka Load Testing Script

This script creates a test environment with multiple topics, consumer groups, and active message production
to help test the Kafka integration under load.

Setup:
    1. Ensure Kafka is running locally (default: localhost:9092)
    2. Install required packages:
       pip install confluent-kafka

Usage:
    python integrations/kafka/tests/seed_data.py

Configuration (modify constants at top of file):
    - NUM_TOPICS: Number of topics to create (default: 50)
    - PARTITIONS_PER_TOPIC: Partitions per topic (default: 3)
    - NUM_CONSUMER_GROUPS: Number of consumer groups (default: 20)
    - CONSUMERS_PER_GROUP: Number of consumers per group (default: 3)
    - KAFKA_BOOTSTRAP_SERVERS: Kafka broker address (default: 'localhost:9092')

The script will:
    1. Create multiple topics with specified partitions
    2. Start a producer continuously sending messages to random topics
    3. Create multiple consumer groups with multiple consumers each
    4. Process messages in each consumer group

To stop:
    Press CTRL+C for graceful shutdown

Example:
    # This will create:
    # - 50 topics with 3 partitions each
    # - 20 consumer groups with 3 consumers each (60 total consumers)
    # - 1 producer sending messages to random topics
    python integrations/kafka/tests/seed_data.py
"""

import random
import string
from typing import List, Any, NoReturn
import time
import threading
import signal
import sys

from confluent_kafka import Consumer, Producer, KafkaError  # type: ignore
from confluent_kafka.admin import AdminClient, NewTopic  # type: ignore


class KafkaLoadTest:
    def __init__(self) -> None:
        self.running = threading.Event()
        self.producer_thread: threading.Thread | None = None
        self.consumer_threads: List[threading.Thread] = []

        # Set up signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def signal_handler(self, signum: int, frame: Any) -> NoReturn:
        """Handle shutdown signals"""
        print("\nShutting down...")
        self.running.clear()
        if self.producer_thread:
            self.producer_thread.join()
        for thread in self.consumer_threads:
            thread.join()
        sys.exit(0)

    def run(self) -> None:
        """Main function to set up and run the Kafka load test"""
        # Create topics
        admin_config = {"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS}
        admin_client = AdminClient(admin_config)

        # Generate topic names
        topic_names = [f"load-test-topic-{i}" for i in range(NUM_TOPICS)]
        create_topics(admin_client, topic_names)

        # Create running event for graceful shutdown
        self.running.set()

        # Start producer thread
        self.producer_thread = threading.Thread(
            target=produce_messages, args=(topic_names, self.running)
        )
        self.producer_thread.start()

        # Start consumer threads
        for group_num in range(NUM_CONSUMER_GROUPS):
            group_id = f"load-test-group-{group_num}"
            for consumer_num in range(CONSUMERS_PER_GROUP):
                thread = threading.Thread(
                    target=start_consumer, args=(group_id, topic_names, self.running)
                )
                thread.start()
                self.consumer_threads.append(thread)

        # Keep main thread alive
        while True:
            time.sleep(1)


KAFKA_SERVERS_ARRAY = [
    "localhost:19092",
    "localhost:9092",
    "localhost:9093",
    "localhost:9094",
]
# Configuration
NUM_TOPICS = 50
PARTITIONS_PER_TOPIC = 3
KAFKA_BOOTSTRAP_SERVERS = ",".join(KAFKA_SERVERS_ARRAY)
REPLICATION_FACTOR = 1
NUM_CONSUMER_GROUPS = 40
CONSUMERS_PER_GROUP = 5


def create_topics(admin_client: AdminClient, topic_names: List[str]) -> None:
    """Create multiple topics"""
    new_topics = [
        NewTopic(
            topic,
            num_partitions=PARTITIONS_PER_TOPIC,
            replication_factor=REPLICATION_FACTOR,
        )
        for topic in topic_names
    ]

    futures = admin_client.create_topics(new_topics)
    for topic, future in futures.items():
        try:
            future.result()
            print(f"Topic {topic} created")
        except Exception as e:
            print(f"Failed to create topic {topic}: {e}")


def generate_random_string(length: int = 8) -> str:
    """Generate a random string of fixed length"""
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def delivery_report(err: Any, msg: Any) -> None:
    """Callback for message delivery reports"""
    if err is not None:
        print(f"Message delivery failed: {err}")


def produce_messages(topic_names: List[str], running: threading.Event) -> None:
    """Continuously produce messages to topics"""
    producer_config = {"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS}
    producer = Producer(producer_config)

    counter = 0
    while running.is_set():
        topic = random.choice(topic_names)
        message = f"message-{counter}-{generate_random_string()}"
        producer.produce(topic, message.encode("utf-8"), callback=delivery_report)
        counter += 1

        if counter % 1000 == 0:
            print(f"Produced {counter} messages")

        producer.poll(0)
        time.sleep(0.001)  # Small delay to prevent overwhelming

    producer.flush()


def start_consumer(
    group_id: str, topic_names: List[str], running: threading.Event
) -> None:
    """Start a consumer in a consumer group"""
    consumer_config = {
        "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
        "group.id": group_id,
        "auto.offset.reset": "earliest",
    }

    consumer = Consumer(consumer_config)
    consumer.subscribe(topic_names)

    try:
        while running.is_set():
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                else:
                    print(f"Consumer error: {msg.error()}")
                    break

            # Process the message (in this case, we just continue)
            continue

    finally:
        consumer.close()


if __name__ == "__main__":
    load_test = KafkaLoadTest()
    load_test.run()
