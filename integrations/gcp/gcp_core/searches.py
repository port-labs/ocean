from typing import Any
from google.api_core.exceptions import PermissionDenied, NotFound
from google.cloud.asset_v1 import (
    AssetServiceAsyncClient,
)
from google.pubsub_v1.services.publisher import PublisherAsyncClient
from google.cloud.resourcemanager_v3 import (
    ProjectsAsyncClient,
    FoldersAsyncClient,
    OrganizationsAsyncClient,
)

from google.cloud.asset_v1.services.asset_service import pagers
from loguru import logger
from gcp_core.utils import (
    AssetTypesWithSpecialHandling,
    parse_protobuf_messages,
)
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.cache import cache_iterator_result

EXTRA_PROJECT_FIELD = "__project"


async def search_all_resources(
    project: dict[str, Any], asset_type: str, asset_name: str | None = None
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Search for resources that the caller has ``cloudasset.assets.searchAllResources`` permission on within the project's scope.
    """
    project_name = project["name"]
    logger.info(f"Searching all {asset_type}'s in project {project_name}")
    async with AssetServiceAsyncClient() as async_assets_client:
        search_all_resources_request = {
            "scope": project_name,
            "asset_types": [asset_type],
            "read_mask": "*",
        }
        if asset_name:
            search_all_resources_request["query"] = f"name={asset_name}"
        try:
            paginated_responses: pagers.SearchAllResourcesAsyncPager = (
                await async_assets_client.search_all_resources(
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


async def search_all_topics(project: dict[str, Any]) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Search for topics that the caller has ``pubsub.topics.list`` permission on within the project's scope.
    """
    project_name = project["name"]
    logger.info(
        f"Searching all {AssetTypesWithSpecialHandling.TOPIC}'s in project {project_name}"
    )
    async with PublisherAsyncClient() as async_publisher_client:
        try:
            list_topics_pagers = await async_publisher_client.list_topics(
                project=project_name
            )
            async for paginated_response in list_topics_pagers.pages:
                topics = parse_protobuf_messages(paginated_response.topics)
                if topics:
                    logger.info(
                        f"Generating {len(topics)} {AssetTypesWithSpecialHandling.TOPIC}'s"
                    )
                    for topic in topics:
                        topic[EXTRA_PROJECT_FIELD] = project
                    yield topics
        except PermissionDenied:
            logger.info(
                f"Service account doesn't have permissions to list topics from project {project_name}"
            )
        except NotFound:
            logger.debug(f"Project {project_name} is deleted")


@cache_iterator_result()
async def search_all_projects() -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Search for projects that the caller has ``resourcemanager.projects.get`` permission on
    """
    async with ProjectsAsyncClient() as projects_client:
        search_projects_pager = await projects_client.search_projects()
        async for projects_page in search_projects_pager.pages:
            yield parse_protobuf_messages(projects_page.projects)


async def search_all_folders() -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Search for folders that the caller has ``resourcemanager.folders.get`` permission on
    """
    async with FoldersAsyncClient() as folders_client:
        search_folders_pager = await folders_client.search_folders()
        async for folders_page in search_folders_pager.pages:
            yield parse_protobuf_messages(folders_page.folders)


async def search_all_organizations() -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Search for organizations that the caller has ``resourcemanager.organizations.get``` permission on
    """
    async with OrganizationsAsyncClient() as organizations_client:
        search_organizations_pager = await organizations_client.search_organizations()
        async for organizations_page in search_organizations_pager.pages:
            yield parse_protobuf_messages(organizations_page.organizations)
