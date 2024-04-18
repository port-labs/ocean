from typing import Any

from google.api_core.exceptions import NotFound, PermissionDenied
from google.cloud.asset_v1 import (
    AssetServiceAsyncClient,
)
from google.cloud.asset_v1.services.asset_service import pagers
from google.cloud.resourcemanager_v3 import (
    FoldersAsyncClient,
    OrganizationsAsyncClient,
    ProjectsAsyncClient,
)
from google.pubsub_v1.services.publisher import PublisherAsyncClient
from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from port_ocean.utils.cache import cache_iterator_result

from gcp_core.utils import (
    EXTRA_PROJECT_FIELD,
    AssetTypesWithSpecialHandling,
    parse_protobuf_message,
    parse_protobuf_messages,
)


async def search_all_resources(
    project_data: dict[str, Any], asset_type: str
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    project_name = project_data["name"]
    async for resources in search_all_resources_in_project(project_name, asset_type):
        yield resources


async def search_all_resources_in_project(
    project_name: str, asset_type: str, asset_name: str | None = None
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    List of supported assets: https://cloud.google.com/asset-inventory/docs/supported-asset-types
    Search for resources that the caller has ``cloudasset.assets.searchAllResources`` permission on within the project's scope.
    The format to get the most updated value of a resource's property in the port app config is:

        .versioned_resources | max_by(.version).resource | <resource_property>

    for example, to get the object retention load of a bucket the currect way of getting that is:

        .versioned_resources | max_by(.version).resource | .objectRetention.mode

    """
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
            logger.exception(f"Couldn't access the API Cloud Assets to get kind {asset_type}. Please set cloudasset.assets.searchAllResources permissions for project {project_name}")
            raise e


async def list_all_topics_per_project(
    project: dict[str, Any],
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    This lists all Topics under a certain project.
    The Topics are handled specifically due to lacks of data in the asset itselfwithin the asset inventory - e.g. some properties missing.
    The listing is being done via the PublisherAsyncClient, ignoring state in assets inventory
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


async def get_project(project_name: str) -> RAW_ITEM:
    async with ProjectsAsyncClient() as projects_client:
        return parse_protobuf_message(
            await projects_client.get_project(name=project_name)
        )


async def get_folder(folder_name: str) -> RAW_ITEM:
    async with FoldersAsyncClient() as folders_client:
        return parse_protobuf_message(await folders_client.get_folder(name=folder_name))


async def get_organization(organization_name: str) -> RAW_ITEM:
    async with OrganizationsAsyncClient() as organizations_client:
        return parse_protobuf_message(
            await organizations_client.get_organization(name=organization_name)
        )


async def get_topic(topic_id: str) -> RAW_ITEM:
    """
    The Topics are handled specifically due to lacks of data in the asset itself within the asset inventory- e.g. some properties missing.
    Here the PublisherAsyncClient is used, ignoring state in assets inventory
    """
    async with PublisherAsyncClient() as async_publisher_client:
        return parse_protobuf_message(
            await async_publisher_client.get_topic(topic=topic_id)
        )


class ResourceNotFoundError(Exception):
    pass


async def search_resource(
    project_id: str, asset_kind: str, asset_name: str
) -> RAW_ITEM:
    try:
        resource = [
            resources
            async for resources in search_all_resources_in_project(
                project_id, asset_kind, asset_name
            )
        ][0][0]
    except IndexError:
        raise ResourceNotFoundError(
            f"Found no asset named {asset_name} with type {asset_kind}"
        )
    return resource
