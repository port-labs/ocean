import json
import re
from typing import Any

from loguru import logger

from port_ocean.context.ocean import ocean

from kafka_integration.client import KafkaClient
from kafka_integration.exceptions import IntegrationMissingConfigError
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


def get_cluster_conf_mapping() -> dict[str, Any]:
    """Get cluster configuration mapping from either object or string parameter."""
    config = ocean.integration_config

    cluster_conf = config.get("cluster_conf_mapping")
    if isinstance(cluster_conf, dict) and cluster_conf:
        return cluster_conf

    cluster_conf_string = config.get("cluster_conf_mapping_string")
    if cluster_conf_string:
        try:
            parsed = json.loads(cluster_conf_string)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse cluster_conf_mapping_string: {e}")
            raise IntegrationMissingConfigError(
                f"Invalid JSON in cluster_conf_mapping_string: {e}"
            ) from e

    raise IntegrationMissingConfigError(
        "Either clusterConfMapping (object) or clusterConfMappingString (JSON string) must be provided"
    )


def init_clients() -> list[KafkaClient]:
    cluster_conf_mapping = get_cluster_conf_mapping()
    return [
        KafkaClient(re.sub(r"[^A-Za-z0-9@_.:/=-]", "", cluster_name), conf)
        for cluster_name, conf in cluster_conf_mapping.items()
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
