from typing import Any
import typing

from google.api_core.exceptions import NotFound, PermissionDenied
from google.cloud.asset_v1 import (
    AssetServiceAsyncClient,
)
from google.cloud.resourcemanager_v3 import (
    FoldersAsyncClient,
    OrganizationsAsyncClient,
    ProjectsAsyncClient,
)
from google.pubsub_v1.services.publisher import PublisherAsyncClient
from google.pubsub_v1.services.subscriber import SubscriberAsyncClient
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
from gcp_core.search.paginated_query import paginated_query, DEFAULT_REQUEST_TIMEOUT
from gcp_core.helpers.ratelimiter.base import MAXIMUM_CONCURRENT_REQUESTS
from asyncio import BoundedSemaphore

DEFAULT_SEMAPHORE = BoundedSemaphore(MAXIMUM_CONCURRENT_REQUESTS)


async def search_all_resources(
    project_data: dict[str, Any], asset_type: str, **kwargs: Any
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for resources in search_all_resources_in_project(
        project_data, asset_type, **kwargs
    ):
        yield resources


async def search_all_resources_in_project(
    project: dict[str, Any],
    asset_type: str,
    semaphore: BoundedSemaphore,
    asset_name: str | None = None,
    **kwargs: Any,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    List of supported assets: https://cloud.google.com/asset-inventory/docs/supported-asset-types
    Search for resources that the caller has ``cloudasset.assets.searchAllResources`` permission on within the project's scope.
    """

    def parse_asset_response(response: Any) -> list[dict[Any, Any]]:
        assets = typing.cast(list[AssetData], parse_protobuf_messages(response.results))
        latest_resources = [
            {
                **parse_latest_resource_from_asset(asset),
                EXTRA_PROJECT_FIELD: project,
            }
            for asset in assets
        ]
        return latest_resources

    async with semaphore:
        project_name = project["name"]
        logger.info(f"Searching all {asset_type}'s in project {project_name}")

        search_all_resources_request = {
            "scope": project_name,
            "asset_types": [asset_type],
            "read_mask": "*",
        }
        if asset_name:
            search_all_resources_request["query"] = f"name={asset_name}"

        async with AssetServiceAsyncClient() as async_assets_client:

            try:
                async for assets in paginated_query(
                    async_assets_client,
                    "search_all_resources",
                    search_all_resources_request,
                    parse_asset_response,
                    kwargs.get("rate_limiter"),
                ):
                    yield assets

            except PermissionDenied:
                logger.error(
                    f"Service account doesn't have permissions to search all resources within project {project_name} for kind {asset_type}"
                )
            except NotFound:
                logger.info(
                    f"Couldn't perform search_all_resources on project {project_name} since it's deleted."
                )
            else:
                logger.info(
                    f"Successfully searched all resources within project {project_name}"
                )


async def list_all_topics_per_project(
    project: dict[str, Any], **kwargs: Any
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    This lists all Topics under a certain project.
    The Topics are handled specifically due to lacks of data in the asset itselfwithin the asset inventory - e.g. some properties missing.
    The listing is being done via the PublisherAsyncClient, ignoring state in assets inventory
    """
    async with PublisherAsyncClient() as async_publisher_client:
        project_name = project["name"]
        logger.info(
            f"Searching all {AssetTypesWithSpecialHandling.TOPIC}'s in project {project_name}"
        )
        try:
            async for topics in paginated_query(
                async_publisher_client,
                "list_topics",
                {"project": project_name},
                lambda response: parse_protobuf_messages(response.topics),
                kwargs.get("rate_limiter"),
            ):
                for topic in topics:
                    topic[EXTRA_PROJECT_FIELD] = project
                yield topics
        except PermissionDenied:
            logger.error(
                f"Service account doesn't have permissions to list topics from project {project_name}"
            )
        except NotFound:
            logger.info(
                f"Couldn't perform list_topics on project {project_name} since it's deleted."
            )
        else:
            logger.info(f"Successfully listed all topics within project {project_name}")


async def list_all_subscriptions_per_project(
    project: dict[str, Any], **kwargs: Any
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    This lists all Topics under a certain project.
    The Subscriptions are handled specifically due to lacks of data in the asset itself within the asset inventory.
    The listing is being done via the PublisherAsyncClient, ignoring state in assets inventory
    """
    async with SubscriberAsyncClient() as async_subscriber_client:
        project_name = project["name"]
        logger.info(
            f"Searching all {AssetTypesWithSpecialHandling.SUBSCRIPTION}'s in project {project_name}"
        )
        try:
            async for subscriptions in paginated_query(
                async_subscriber_client,
                "list_subscriptions",
                {"project": project_name},
                lambda response: parse_protobuf_messages(response.subscriptions),
                kwargs.get("rate_limiter"),
            ):
                for subscription in subscriptions:
                    subscription[EXTRA_PROJECT_FIELD] = project
                yield subscriptions
        except PermissionDenied:
            logger.error(
                f"Service account doesn't have permissions to list subscriptions from project {project_name}"
            )
        except NotFound:
            logger.info(
                f"Couldn't perform list_subscriptions on project {project_name} since it's deleted."
            )
        else:
            logger.info(
                f"Successfully listed all subscriptions within project {project_name}"
            )


@cache_iterator_result()
async def search_all_projects() -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info("Searching projects")
    async with ProjectsAsyncClient() as projects_client:
        async for projects in paginated_query(
            projects_client,
            "search_projects",
            {},
            lambda response: parse_protobuf_messages(response.projects),
        ):
            yield projects


async def search_all_folders() -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info("Searching folders")
    async with FoldersAsyncClient() as folders_client:
        async for folders in paginated_query(
            folders_client,
            "search_folders",
            {},
            lambda response: parse_protobuf_messages(response.folders),
        ):
            yield folders


async def search_all_organizations() -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info("Searching organizations")
    async with OrganizationsAsyncClient() as organizations_client:
        async for organizations in paginated_query(
            organizations_client,
            "search_organizations",
            {},
            lambda response: parse_protobuf_messages(response.organizations),
        ):
            yield organizations


async def get_single_project(project_name: str) -> RAW_ITEM:
    async with ProjectsAsyncClient() as projects_client:
        return parse_protobuf_message(
            await projects_client.get_project(
                name=project_name, timeout=DEFAULT_REQUEST_TIMEOUT
            )
        )


async def get_single_folder(folder_name: str) -> RAW_ITEM:
    async with FoldersAsyncClient() as folders_client:
        return parse_protobuf_message(
            await folders_client.get_folder(
                name=folder_name, timeout=DEFAULT_REQUEST_TIMEOUT
            )
        )


async def get_single_organization(organization_name: str) -> RAW_ITEM:
    async with OrganizationsAsyncClient() as organizations_client:
        return parse_protobuf_message(
            await organizations_client.get_organization(
                name=organization_name, timeout=DEFAULT_REQUEST_TIMEOUT
            )
        )


async def get_single_topic(project_id: str, topic_id: str) -> RAW_ITEM:
    """
    The Topics are handled specifically due to lacks of data in the asset itself within the asset inventory- e.g. some properties missing.
    Here the PublisherAsyncClient is used, ignoring state in assets inventory
    """
    async with PublisherAsyncClient() as async_publisher_client:
        return parse_protobuf_message(
            await async_publisher_client.get_topic(
                topic=topic_id, timeout=DEFAULT_REQUEST_TIMEOUT
            )
        )


async def get_single_subscription(project_id: str, subscription_id: str) -> RAW_ITEM:
    """
    Subscriptions are handled specifically due to lacks of data in the asset itself within the asset inventory- e.g. some properties missing.
    Here the SubscriberAsyncClient is used, ignoring state in assets inventory
    """
    async with SubscriberAsyncClient() as async_subscriber_client:
        return parse_protobuf_message(
            await async_subscriber_client.get_subscription(
                subscription=subscription_id, timeout=DEFAULT_REQUEST_TIMEOUT
            )
        )


async def search_single_resource(
    project: dict[str, Any], asset_kind: str, asset_name: str
) -> RAW_ITEM:
    try:
        resource = [
            resources
            async for resources in search_all_resources_in_project(
                project,
                asset_kind,
                DEFAULT_SEMAPHORE,
                asset_name,
            )
        ][0][0]
    except IndexError:
        raise ResourceNotFoundError(
            f"Found no asset named {asset_name} with type {asset_kind}"
        )
    return resource


async def feed_event_to_resource(
    asset_type: str, asset_name: str, project_id: str, asset_data: dict[str, Any]
) -> RAW_ITEM:
    resource = None
    if asset_data.get("deleted") is True:
        resource = asset_data["priorAsset"]["resource"]["data"]
        resource[EXTRA_PROJECT_FIELD] = await get_single_project(project_id)
    else:
        match asset_type:
            case AssetTypesWithSpecialHandling.TOPIC:
                topic_name = asset_name.replace("//pubsub.googleapis.com/", "")
                resource = await get_single_topic(project_id, topic_name)
                resource[EXTRA_PROJECT_FIELD] = await get_single_project(project_id)
            case AssetTypesWithSpecialHandling.SUBSCRIPTION:
                topic_name = asset_name.replace("//pubsub.googleapis.com/", "")
                resource = await get_single_subscription(project_id, topic_name)
                resource[EXTRA_PROJECT_FIELD] = await get_single_project(project_id)
            case AssetTypesWithSpecialHandling.FOLDER:
                folder_id = asset_name.replace(
                    "//cloudresourcemanager.googleapis.com/", ""
                )
                resource = await get_single_folder(folder_id)
            case AssetTypesWithSpecialHandling.ORGANIZATION:
                organization_id = asset_name.replace(
                    "//cloudresourcemanager.googleapis.com/", ""
                )
                resource = await get_single_organization(organization_id)
            case AssetTypesWithSpecialHandling.PROJECT:
                resource = await get_single_project(project_id)
            case _:
                resource = asset_data["asset"]["resource"]["data"]
                resource[EXTRA_PROJECT_FIELD] = await get_single_project(project_id)
    return resource
