from typing import Any, AsyncIterator
from anyio import to_thread

import confluent_kafka  # type: ignore

from confluent_kafka.admin import AdminClient, ConfigResource  # type: ignore
from loguru import logger


DEFAULT_BATCH_SIZE = 50


class KafkaClient:
    def __init__(self, cluster_name: str, conf: dict[str, Any]):
        self.cluster_name = cluster_name
        self.kafka_admin_client = AdminClient(conf)
        self.cluster_metadata = self.kafka_admin_client.list_topics()

    async def describe_cluster(self) -> dict[str, Any]:
        return {
            "name": self.cluster_name,
            "controller_id": self.cluster_metadata.controller_id,
        }

    async def describe_brokers(
        self, batch_size: int = DEFAULT_BATCH_SIZE
    ) -> AsyncIterator[list[dict[str, Any]]]:
        current_batch = []
        for broker in self.cluster_metadata.brokers.values():
            brokers_configs = await to_thread.run_sync(
                self.kafka_admin_client.describe_configs,
                [ConfigResource(confluent_kafka.admin.RESOURCE_BROKER, str(broker.id))],
            )
            for broker_config_resource, future in brokers_configs.items():
                broker_id = broker_config_resource.name
                try:
                    broker_config = {
                        key: value.value
                        for key, value in (
                            await to_thread.run_sync(future.result)
                        ).items()
                    }
                    current_batch.append(
                        {
                            "id": broker.id,
                            "address": str(broker),
                            "cluster_name": self.cluster_name,
                            "config": broker_config,
                        }
                    )

                    if len(current_batch) >= batch_size:
                        yield current_batch
                        current_batch = []
                except Exception as e:
                    logger.error(f"Failed to describe broker {broker_id}: {e}")
                    raise e

        if current_batch:  # Yield any remaining items
            yield current_batch

    async def describe_topics(
        self, batch_size: int = DEFAULT_BATCH_SIZE
    ) -> AsyncIterator[list[dict[str, Any]]]:
        current_batch = []
        topics_config_resources = []
        topics_metadata_dict = {}

        for topic in self.cluster_metadata.topics.values():
            topics_config_resources.append(
                ConfigResource(confluent_kafka.admin.RESOURCE_TOPIC, topic.topic)
            )
            topics_metadata_dict[topic.topic] = topic

        if not topics_config_resources:  # Add check for empty topics list
            logger.info("No topics found in the cluster")
            return

        topics_configs = await to_thread.run_sync(
            self.kafka_admin_client.describe_configs, topics_config_resources
        )
        for topic_config_resource, future in topics_configs.items():
            topic_name = topic_config_resource.name
            try:
                topic_config = {
                    key: value.value
                    for key, value in (await to_thread.run_sync(future.result)).items()
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
                current_batch.append(
                    {
                        "name": topic_name,
                        "cluster_name": self.cluster_name,
                        "partitions": partitions,
                        "config": topic_config,
                    }
                )

                if len(current_batch) >= batch_size:
                    yield current_batch
                    current_batch = []
            except Exception as e:
                logger.error(f"Failed to describe topic {topic_name}: {e}")
                raise e

        if current_batch:  # Yield any remaining items
            yield current_batch

    async def describe_consumer_groups(
        self, batch_size: int = DEFAULT_BATCH_SIZE
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Describe all consumer groups in the cluster."""
        from itertools import islice
        import asyncio

        groups_metadata = await to_thread.run_sync(
            self.kafka_admin_client.list_consumer_groups
        )
        groups_result = await to_thread.run_sync(groups_metadata.result)
        group_ids = [group.group_id for group in groups_result.valid]

        logger.info(f"Found {len(group_ids)} consumer groups")
        if not group_ids:
            return

        # Process group_ids in batches
        while group_ids:
            current_batch_ids = list(islice(group_ids, batch_size))
            group_ids = group_ids[batch_size:]
            
            groups_description = await to_thread.run_sync(
                self.kafka_admin_client.describe_consumer_groups, current_batch_ids
            )

            # Process all groups in the current batch concurrently
            tasks = []
            for group_id, future in groups_description.items():
                tasks.append(self._process_consumer_group(group_id, future))
            
            current_batch = []
            try:
                current_batch = await asyncio.gather(*tasks)
                yield [group for group in current_batch if group is not None]
            except Exception as e:
                logger.error(f"Failed to process batch of consumer groups: {e}")
                raise e

    async def _process_consumer_group(self, group_id: str, future: Any) -> dict[str, Any] | None:
        """Process a single consumer group and return its description."""
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

            return {
                "group_id": group_id,
                "state": group_info.state.name,
                "members": members,
                "cluster_name": self.cluster_name,
                "coordinator": group_info.coordinator.id,
                "partition_assignor": group_info.partition_assignor,
                "is_simple_consumer_group": group_info.is_simple_consumer_group,
                "authorized_operations": group_info.authorized_operations,
            }
        except Exception as e:
            logger.error(f"Failed to describe consumer group {group_id}: {e}")
            return None
