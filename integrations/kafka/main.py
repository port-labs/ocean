import re
from port_ocean.context.ocean import ocean

from kafka_integration.client import KafkaClient
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


def init_clients() -> list[KafkaClient]:
    return [
        KafkaClient(re.sub(r"[^A-Za-z0-9@_.:/=-]", "", cluster_name), conf)
        for cluster_name, conf in ocean.integration_config[
            "cluster_conf_mapping"
        ].items()
    ]


@ocean.on_resync("cluster")
async def resync_cluster(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    kafka_clients = init_clients()
    for kafka_client in kafka_clients:
        yield [await kafka_client.describe_cluster()]


@ocean.on_resync("broker")
async def resync_brokers(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    kafka_clients = init_clients()
    for kafka_client in kafka_clients:
        async for batch in kafka_client.describe_brokers():
            yield batch


@ocean.on_resync("topic")
async def resync_topics(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    kafka_clients = init_clients()
    for kafka_client in kafka_clients:
        async for batch in kafka_client.describe_topics():
            yield batch


@ocean.on_resync("consumer_group")
async def resync_consumer_groups(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    kafka_clients = init_clients()
    for kafka_client in kafka_clients:
        async for batch in kafka_client.describe_consumer_groups():
            yield batch
