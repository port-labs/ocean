from typing import Any
from anyio import to_thread

import confluent_kafka  # type: ignore

from confluent_kafka.admin import AdminClient, ConfigResource  # type: ignore
from loguru import logger


class KafkaClient:
    def __init__(self, cluster_name: str, conf: dict[str, Any]):
        self.cluster_name = cluster_name
        self.kafka_admin_client = AdminClient(conf)
        self.cluster_metadata = self.kafka_admin_client.list_topics()

    def describe_cluster(self) -> dict[str, Any]:
        return {
            "name": self.cluster_name,
            "controller_id": self.cluster_metadata.controller_id,
        }

    def describe_brokers(self) -> list[dict[str, Any]]:
        result_brokers = []
        for broker in self.cluster_metadata.brokers.values():
            brokers_configs = self.kafka_admin_client.describe_configs(
                [ConfigResource(confluent_kafka.admin.RESOURCE_BROKER, str(broker.id))]
            )
            for broker_config_resource, future in brokers_configs.items():
                broker_id = broker_config_resource.name
                try:
                    broker_config = {
                        key: value.value for key, value in future.result().items()
                    }
                    result_brokers.append(
                        {
                            "id": broker.id,
                            "address": str(broker),
                            "cluster_name": self.cluster_name,
                            "config": broker_config,
                        }
                    )
                except Exception as e:
                    logger.error(f"Failed to describe broker {broker_id}: {e}")
                    raise e
        return result_brokers

    def describe_topics(self) -> list[dict[str, Any]]:
        result_topics = []
        topics_config_resources = []
        topics_metadata_dict = {}

        for topic in self.cluster_metadata.topics.values():
            topics_config_resources.append(
                ConfigResource(confluent_kafka.admin.RESOURCE_TOPIC, topic.topic)
            )
            topics_metadata_dict[topic.topic] = topic

        topics_configs = self.kafka_admin_client.describe_configs(
            topics_config_resources
        )
        for topic_config_resource, future in topics_configs.items():
            topic_name = topic_config_resource.name
            try:
                topic_config = {
                    key: value.value for key, value in future.result().items()
                }
                partitions = [
                    {
                        "id": partition.id,
                        "leader": partition.leader,
                        "replicas": partition.replicas,
                        "isrs": partition.isrs,
                    }
                    for partition in topics_metadata_dict[
                        topic_name
                    ].partitions.values()
                ]
                result_topics.append(
                    {
                        "name": topic_name,
                        "cluster_name": self.cluster_name,
                        "partitions": partitions,
                        "config": topic_config,
                    }
                )
            except Exception as e:
                logger.error(f"Failed to describe topic {topic_name}: {e}")
                raise e
        return result_topics

    async def describe_consumer_groups(self) -> list[dict[str, Any]]:
        """Describe all consumer groups in the cluster."""
        result_groups: list[dict[str, Any]] = []

        # List all consumer groups and wait for the future to complete
        groups_metadata = await to_thread.run_sync(
            self.kafka_admin_client.list_consumer_groups
        )
        groups_result = await to_thread.run_sync(groups_metadata.result)
        group_ids = [group.group_id for group in groups_result.valid]

        logger.info(f"Found {len(group_ids)} consumer groups")
        if not group_ids:
            return result_groups

        # Describe the consumer groups
        groups_description = await to_thread.run_sync(
            self.kafka_admin_client.describe_consumer_groups, group_ids
        )

        for group_id, future in groups_description.items():
            try:
                group_info = await to_thread.run_sync(future.result)
                members = [
                    {
                        "id": member.member_id,
                        "client_id": member.client_id,
                        "host": member.host,
                        "assignment": {
                            "topic_partitions": [
                                {"topic": tp.topic, "partition": tp.partition}
                                for tp in member.assignment.topic_partitions
                            ]
                        },
                    }
                    for member in group_info.members
                ]

                result_groups.append(
                    {
                        "group_id": group_id,
                        "state": group_info.state.name,
                        "members": members,
                        "cluster_name": self.cluster_name,
                        "coordinator": group_info.coordinator.id,
                        "partition_assignor": group_info.partition_assignor,
                        "is_simple_consumer_group": group_info.is_simple_consumer_group,
                        "authorized_operations": group_info.authorized_operations,
                    }
                )
            except Exception as e:
                logger.error(f"Failed to describe consumer group {group_id}: {e}")
                raise e

        return result_groups
