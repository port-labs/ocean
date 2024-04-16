import enum
import proto  # type: ignore
from google.api_core.exceptions import PermissionDenied, NotFound
from google.cloud.asset_v1 import (
    AssetServiceAsyncClient,
)
from google.cloud.asset_v1.services.asset_service import pagers
from loguru import logger
from google.pubsub_v1.services.publisher import PublisherAsyncClient
from integrations.gcp.gcp_core.utils import parse_protobuf_messages
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM


class AssetTypesWithSpecialHandling(enum.StrEnum):
    TOPIC = "pubsub.googleapis.com/Topic"


TOPIC_PROJECT_FIELD = "__project_id"
GCP_RESOURCE_MANAGER_PROJECT_KIND = "cloudresourcemanager.googleapis.com/Project"


class ResourceNotFoundError(Exception):
    pass


class GCPClient:
    def __init__(self, parent: str, service_account_file: str) -> None:
        self.async_assets_client: AssetServiceAsyncClient = (
            AssetServiceAsyncClient.from_service_account_file(service_account_file)
        )
        self.async_publisher_client: PublisherAsyncClient = (
            PublisherAsyncClient.from_service_account_file(service_account_file)
        )
        self._parent = parent

    async def generate_topics(self) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for projects in self.generate_resources(
            GCP_RESOURCE_MANAGER_PROJECT_KIND
        ):
            for project in projects:
                project_id = project["project"]
                try:
                    list_topics_pagers = await self.async_publisher_client.list_topics(
                        project=project_id
                    )
                    async for paginated_response in list_topics_pagers.pages:
                        topics = parse_protobuf_messages(paginated_response.topics)
                        if topics:
                            logger.info(
                                f"Generating {len(topics)} {AssetTypesWithSpecialHandling.TOPIC}'s"
                            )
                            for topic in topics:
                                topic[TOPIC_PROJECT_FIELD] = project_id
                            yield topics
                except PermissionDenied:
                    logger.info(
                        f"Service account doesn't have permissions to list topics from project {project_id}"
                    )
                except NotFound:
                    logger.debug(f"Project {project_id} is deleted")
        return

    async def get_pubsub_topic(self, topic_id: str, project_id: str) -> RAW_ITEM:
        topic = await self.async_publisher_client.get_topic(topic=topic_id)
        raw_topic = proto.Message.to_dict(topic)
        raw_topic[TOPIC_PROJECT_FIELD] = project_id
        return raw_topic

    async def generate_resources(
        self, asset_type: str, asset_name: str | None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        search_all_resources_request = {
            "scope": self._parent,
            "asset_types": [asset_type],
            "read_mask": "*",
        }
        if asset_name:
            search_all_resources_request["query"] = f"name={asset_name}"
        try:
            paginated_responses: pagers.SearchAllResourcesAsyncPager = (
                await self.async_assets_client.search_all_resources(
                    search_all_resources_request
                )
            )
            async for paginated_response in paginated_responses.pages:
                resources = parse_protobuf_messages(paginated_response.results)
                if resources:
                    logger.info(f"Generating {len(resources)} {asset_type}'s")
                    yield resources
        except PermissionDenied as e:
            logger.error(f"Couldn't access the API to get kind {asset_type}: {str(e)}")
        return

    async def get_single_resource(self, asset_name: str, asset_type: str) -> RAW_ITEM:
        try:
            return [
                resources
                async for resources in self.generate_resources(asset_type, asset_name)
            ][0][0]
        except Exception:
            raise ResourceNotFoundError(
                f"Found not resource typed: {asset_type} named: {asset_name}"
            )
