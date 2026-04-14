from typing import Literal

from pydantic import Field

from kinds import ObjectKind
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
)
from port_ocean.core.integrations.base import BaseIntegration


class ClusterResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.CLUSTER] = Field(
        title="Kafka Cluster",
        description="Kafka cluster resource kind.",
    )


class BrokerResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.BROKER] = Field(
        title="Kafka Broker",
        description="Kafka broker resource kind.",
    )


class TopicResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.TOPIC] = Field(
        title="Kafka Topic",
        description="Kafka topic resource kind.",
    )


class ConsumerGroupResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.CONSUMER_GROUP] = Field(
        title="Kafka Consumer Group",
        description="Kafka consumer group resource kind.",
    )


class KafkaPortAppConfig(PortAppConfig):
    resources: list[
        ClusterResourceConfig
        | BrokerResourceConfig
        | TopicResourceConfig
        | ConsumerGroupResourceConfig
    ] = Field(
        default_factory=list,
    )  # type: ignore[assignment]


class KafkaIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = KafkaPortAppConfig
