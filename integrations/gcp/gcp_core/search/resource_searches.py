from typing import Any
import typing

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

from gcp_core.errors import ResourceNotFoundError
from gcp_core.utils import (
    EXTRA_PROJECT_FIELD,
    AssetData,
    AssetTypesWithSpecialHandling,
    parse_protobuf_message,
    parse_protobuf_messages,
    parse_latest_resource_from_asset,
)


async def search_all_resources(
    project_data: dict[str, Any], asset_type: str
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for resources in search_all_resources_in_project(project_data, asset_type):
        yield resources


async def search_all_resources_in_project(
    project: dict[str, Any], asset_type: str, asset_name: str | None = None
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    List of supported assets: https://cloud.google.com/asset-inventory/docs/supported-asset-types
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
                raw_assets = parse_protobuf_messages(paginated_response.results)
                assets = typing.cast(list[AssetData], raw_assets)
                if assets:
                    logger.info(f"Found {len(assets)} {asset_type}'s")
                    latest_resources = []
                    for asset in assets:
                        latest_resource = parse_latest_resource_from_asset(asset)
                        latest_resource[EXTRA_PROJECT_FIELD] = project
                        latest_resources.append(latest_resource)
                    yield latest_resources
        except PermissionDenied as e:
            logger.exception(
                f"Couldn't access the API Cloud Assets to get kind {asset_type}. Please set cloudasset.assets.searchAllResources permissions for project {project_name}"
            )
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
                        f"Found {len(topics)} {AssetTypesWithSpecialHandling.TOPIC}'s"
                    )
                    for topic in topics:
                        topic[EXTRA_PROJECT_FIELD] = project
                    yield topics
        except PermissionDenied as e:
            logger.exception(
                f"Service account doesn't have permissions to list topics from project {project_name}"
            )
            raise e
        except NotFound:
            logger.debug(
                f"Couldn't perform list_topics on project {project_name} since it's deleted."
            )


@cache_iterator_result()
async def search_all_projects() -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Search for projects that the caller has ``resourcemanager.projects.get`` permission on
    """
    logger.info("Searching projects")
    async with ProjectsAsyncClient() as projects_client:
        search_projects_pager = await projects_client.search_projects()
        async for projects_page in search_projects_pager.pages:
            raw_projects = projects_page.projects
            logger.info(f"Found {len(raw_projects)} Projects")
            yield parse_protobuf_messages(raw_projects)


async def search_all_folders() -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Search for folders that the caller has ``resourcemanager.folders.get`` permission on
    """
    logger.info("Searching folders")
    async with FoldersAsyncClient() as folders_client:
        search_folders_pager = await folders_client.search_folders()
        async for folders_page in search_folders_pager.pages:
            raw_folders = folders_page.folders
            logger.info(f"Found {len(raw_folders)} Folders")
            yield parse_protobuf_messages(raw_folders)


async def search_all_organizations() -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Search for organizations that the caller has ``resourcemanager.organizations.get``` permission on
    """
    logger.info("Searching organizations")
    async with OrganizationsAsyncClient() as organizations_client:
        search_organizations_pager = await organizations_client.search_organizations()
        async for organizations_page in search_organizations_pager.pages:
            raw_orgs = organizations_page.organizations
            logger.info(f"Found {len(raw_orgs)} organizations")
            yield parse_protobuf_messages(raw_orgs)


async def get_single_project(project_name: str) -> RAW_ITEM:
    async with ProjectsAsyncClient() as projects_client:
        return parse_protobuf_message(
            await projects_client.get_project(name=project_name)
        )


async def get_single_folder(folder_name: str) -> RAW_ITEM:
    async with FoldersAsyncClient() as folders_client:
        return parse_protobuf_message(await folders_client.get_folder(name=folder_name))


async def get_single_organization(organization_name: str) -> RAW_ITEM:
    async with OrganizationsAsyncClient() as organizations_client:
        return parse_protobuf_message(
            await organizations_client.get_organization(name=organization_name)
        )


async def get_single_topic(topic_id: str) -> RAW_ITEM:
    """
    The Topics are handled specifically due to lacks of data in the asset itself within the asset inventory- e.g. some properties missing.
    Here the PublisherAsyncClient is used, ignoring state in assets inventory
    """
    async with PublisherAsyncClient() as async_publisher_client:
        return parse_protobuf_message(
            await async_publisher_client.get_topic(topic=topic_id)
        )


async def search_single_resource(
    project: dict[str, Any], asset_kind: str, asset_name: str
) -> RAW_ITEM:
    try:
        resource = [
            resources
            async for resources in search_all_resources_in_project(
                project, asset_kind, asset_name
            )
        ][0][0]
    except IndexError:
        raise ResourceNotFoundError(
            f"Found no asset named {asset_name} with type {asset_kind}"
        )
    return resource


async def feed_event_to_resource(
    asset_type: str, asset_name: str, project_id: str
) -> RAW_ITEM:
    resource = None
    match asset_type:
        case AssetTypesWithSpecialHandling.TOPIC:
            topic_name = asset_name.replace("//pubsub.googleapis.com/", "")
            resource = await get_single_topic(topic_name)
            resource[EXTRA_PROJECT_FIELD] = await get_single_project(project_id)
        case AssetTypesWithSpecialHandling.FOLDER:
            folder_id = asset_name.replace("//cloudresourcemanager.googleapis.com/", "")
            resource = await get_single_folder(folder_id)
        case AssetTypesWithSpecialHandling.ORGANIZATION:
            organization_id = asset_name.replace(
                "//cloudresourcemanager.googleapis.com/", ""
            )
            resource = await get_single_organization(organization_id)
        case AssetTypesWithSpecialHandling.PROJECT:
            resource = await get_single_project(project_id)
        case _:
            project = await get_single_project(project_id)
            resource = await search_single_resource(project, asset_type, asset_name)
    return resource
