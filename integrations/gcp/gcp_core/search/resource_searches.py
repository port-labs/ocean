from typing import Any
import typing

from google.api_core.exceptions import NotFound, PermissionDenied
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
from gcp_core.helpers.ratelimiter.fixed_window import FixedWindowLimiter
from gcp_core.helpers.retry.async_retry import async_retry
from gcp_core.clients import (
    get_asset_client,
    get_projects_client,
    get_folders_client,
    get_organizations_client,
    get_publisher_client,
    get_subscriber_client,
)

from asyncio import BoundedSemaphore
from gcp_core.overrides import ProtoConfig

DEFAULT_SEMAPHORE = BoundedSemaphore(MAXIMUM_CONCURRENT_REQUESTS)

# searchAllIamPolicies caps pageSize at 500. Larger pages spend fewer of the
# per-project quota units, which matters because each policy expands into one
# entity per binding member.
_IAM_POLICY_SEARCH_PAGE_SIZE = 500
_IAM_POLICY_BINDING_BATCH_SIZE = 100
_FOLDER_SCOPE_FIELD = "__folder"
_ORGANIZATION_SCOPE_FIELD = "__organization"


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
        latest_resources = []
        for asset in assets:
            try:
                latest_resources.append(
                    {
                        **parse_latest_resource_from_asset(asset),
                        EXTRA_PROJECT_FIELD: project,
                    }
                )
            except ResourceNotFoundError as e:
                logger.warning(
                    f"Skipping unparsable {asset_type} asset "
                    f"{asset.get('name') or asset.get('asset_type')!r} "
                    f"in project {project_name}: {e}"
                )
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

        async_assets_client = get_asset_client()
        try:
            async for assets in paginated_query(
                async_assets_client,
                "search_all_resources",
                search_all_resources_request,
                parse_asset_response,
                kwargs.get("rate_limiter"),
            ):
                yield assets

        except PermissionDenied as e:
            logger.error(
                f"Service account doesn't have permissions to search all resources within project {project_name} for kind {asset_type}. Error: {str(e.message)}"
            )
        except NotFound as e:
            logger.info(
                f"Couldn't perform search_all_resources on project {project_name} since it's deleted. Error: {str(e)}"
            )
        except Exception:
            logger.exception(
                f"Unexpected error while searching for {asset_type}'s in project {project_name}"
            )
            raise
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
    async_publisher_client = get_publisher_client()
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
    except PermissionDenied as e:
        logger.error(
            f"Service account doesn't have permissions to list topics from project {project_name}. Error: {str(e.message)}"
        )
    except NotFound as e:
        logger.info(
            f"Couldn't perform list_topics on project {project_name} since it's deleted. Error: {str(e)}"
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
    async_subscriber_client = get_subscriber_client()
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
    except PermissionDenied as e:
        logger.error(
            f"Service account doesn't have permissions to list subscriptions from project {project_name}. Error: {str(e.message)}"
        )
    except NotFound as e:
        logger.info(
            f"Couldn't perform list_subscriptions on project {project_name} since it's deleted. Error: {str(e)}"
        )
    else:
        logger.info(
            f"Successfully listed all subscriptions within project {project_name}"
        )


@cache_iterator_result()
async def search_all_projects() -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info("Searching projects")
    projects_client = get_projects_client()
    async for projects in paginated_query(
        projects_client,
        "search_projects",
        {},
        lambda response: parse_protobuf_messages(response.projects),
    ):
        yield projects


async def search_all_folders() -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info("Searching folders")
    folders_client = get_folders_client()
    async for folders in paginated_query(
        folders_client,
        "search_folders",
        {},
        lambda response: parse_protobuf_messages(response.folders),
    ):
        yield folders


async def search_all_organizations() -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info("Searching organizations")
    organizations_client = get_organizations_client()
    async for organizations in paginated_query(
        organizations_client,
        "search_organizations",
        {},
        lambda response: parse_protobuf_messages(response.organizations),
    ):
        yield organizations


async def get_single_project(
    project_name: str,
    rate_limiter: FixedWindowLimiter,
    semaphore: BoundedSemaphore,
    config: ProtoConfig,
) -> RAW_ITEM:
    projects_client = get_projects_client()
    async with semaphore:
        async with rate_limiter:
            logger.debug(
                f"Executing get_single_project. Current rate limit: {rate_limiter.max_rate} requests per {rate_limiter.time_period} seconds."
            )
            result: RAW_ITEM = parse_protobuf_message(
                await projects_client.get_project(name=project_name, retry=async_retry),
                config,
            )
    return result


async def get_single_folder(folder_name: str, config: ProtoConfig) -> RAW_ITEM:
    folders_client = get_folders_client()
    return parse_protobuf_message(
        await folders_client.get_folder(
            name=folder_name, timeout=DEFAULT_REQUEST_TIMEOUT
        ),
        config,
    )


async def get_single_organization(
    organization_name: str, config: ProtoConfig
) -> RAW_ITEM:
    organizations_client = get_organizations_client()
    return parse_protobuf_message(
        await organizations_client.get_organization(
            name=organization_name, timeout=DEFAULT_REQUEST_TIMEOUT
        ),
        config,
    )


async def get_single_topic(
    topic_id: str,
    config: ProtoConfig,
) -> RAW_ITEM:
    """
    The Topics are handled specifically due to lacks of data in the asset itself within the asset inventory- e.g. some properties missing.
    Here the PublisherAsyncClient is used, ignoring state in assets inventory
    """
    async_publisher_client = get_publisher_client()
    return parse_protobuf_message(
        await async_publisher_client.get_topic(
            topic=topic_id, timeout=DEFAULT_REQUEST_TIMEOUT
        ),
        config,
    )


async def get_single_subscription(
    subscription_id: str,
    config: ProtoConfig,
) -> RAW_ITEM:
    """
    Subscriptions are handled specifically due to lacks of data in the asset itself within the asset inventory- e.g. some properties missing.
    Here the SubscriberAsyncClient is used, ignoring state in assets inventory
    """
    async_subscriber_client = get_subscriber_client()
    return parse_protobuf_message(
        await async_subscriber_client.get_subscription(
            subscription=subscription_id, timeout=DEFAULT_REQUEST_TIMEOUT
        ),
        config,
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
    asset_type: str,
    asset_name: str,
    project_id: str,
    asset_data: dict[str, Any],
    project_rate_limiter: FixedWindowLimiter,
    project_semaphore: BoundedSemaphore,
    config: ProtoConfig,
) -> RAW_ITEM:
    resource = None
    if asset_data.get("deleted") is True:
        resource = asset_data["priorAsset"]["resource"]["data"]
        resource[EXTRA_PROJECT_FIELD] = await get_single_project(
            project_id, project_rate_limiter, project_semaphore, config
        )
    else:
        match asset_type:
            case AssetTypesWithSpecialHandling.TOPIC:
                topic_name = asset_name.replace("//pubsub.googleapis.com/", "")
                resource = await get_single_topic(topic_name, config)
                resource[EXTRA_PROJECT_FIELD] = await get_single_project(
                    project_id, project_rate_limiter, project_semaphore, config
                )
            case AssetTypesWithSpecialHandling.SUBSCRIPTION:
                topic_name = asset_name.replace("//pubsub.googleapis.com/", "")
                resource = await get_single_subscription(topic_name, config)
                resource[EXTRA_PROJECT_FIELD] = await get_single_project(
                    project_id, project_rate_limiter, project_semaphore, config
                )
            case AssetTypesWithSpecialHandling.FOLDER:
                folder_id = asset_name.replace(
                    "//cloudresourcemanager.googleapis.com/", ""
                )
                resource = await get_single_folder(folder_id, config)
            case AssetTypesWithSpecialHandling.ORGANIZATION:
                organization_id = asset_name.replace(
                    "//cloudresourcemanager.googleapis.com/", ""
                )
                resource = await get_single_organization(organization_id, config)
            case AssetTypesWithSpecialHandling.PROJECT:
                resource = await get_single_project(
                    project_id, project_rate_limiter, project_semaphore, config
                )
            case _:
                resource = asset_data["asset"]["resource"]["data"]
                resource[EXTRA_PROJECT_FIELD] = await get_single_project(
                    project_id, project_rate_limiter, project_semaphore, config
                )
    return resource


def partition_iam_policy_asset_types(
    asset_types: list[str],
) -> tuple[list[str], bool, bool]:
    """Split asset types by the scope that returns their explicit allow policies.

    Project scope returns policies on resources in that project. Folder and
    organization policies are not inside a project. Searching an organization
    for every asset type would also return policies on descendant projects, so
    those two asset types are searched only on their own scopes.
    """
    project_types: list[str] = []
    include_folders = False
    include_organizations = False
    for asset_type in asset_types:
        if asset_type == AssetTypesWithSpecialHandling.FOLDER:
            include_folders = True
        elif asset_type == AssetTypesWithSpecialHandling.ORGANIZATION:
            include_organizations = True
        else:
            project_types.append(asset_type)
    return project_types, include_folders, include_organizations


def _condition_or_none(binding: dict[str, Any]) -> dict[str, Any] | None:
    condition = binding.get("condition")
    if not isinstance(condition, dict):
        return None
    if not any(
        condition.get(key) for key in ("expression", "title", "description", "location")
    ):
        return None
    return {
        "expression": condition.get("expression") or "",
        "title": condition.get("title") or "",
        "description": condition.get("description") or "",
        "location": condition.get("location") or "",
    }


def _split_member(member: str) -> tuple[str, str]:
    if ":" not in member:
        return member, ""
    member_type, member_id = member.split(":", 1)
    return member_type, member_id


def expand_iam_policy_bindings(
    policies: list[dict[str, Any]],
    scope: dict[str, Any],
    scope_field: str,
) -> list[dict[str, Any]]:
    """Turn allow-policy search results into one raw item per binding member."""
    bindings: list[dict[str, Any]] = []
    for policy in policies:
        policy_body = policy.get("policy")
        if not isinstance(policy_body, dict):
            continue
        raw_bindings = policy_body.get("bindings") or []
        if not isinstance(raw_bindings, list):
            continue
        for binding in raw_bindings:
            if not isinstance(binding, dict):
                continue
            role = binding.get("role")
            if not isinstance(role, str) or not role:
                continue
            members = binding.get("members") or []
            if not isinstance(members, list):
                continue
            condition = _condition_or_none(binding)
            for member in members:
                if not isinstance(member, str) or not member:
                    continue
                member_type, member_id = _split_member(member)
                folders = policy.get("folders") or []
                bindings.append(
                    {
                        "resource": policy.get("resource") or "",
                        "asset_type": policy.get("asset_type")
                        or policy.get("assetType")
                        or "",
                        "project": policy.get("project") or "",
                        "folders": list(folders) if isinstance(folders, list) else [],
                        "organization": policy.get("organization") or "",
                        "role": role,
                        "member": member,
                        "member_type": member_type,
                        "member_id": member_id,
                        "condition": dict(condition) if condition is not None else None,
                        scope_field: scope,
                    }
                )
    return bindings


def _batched(
    items: list[dict[str, Any]], size: int
) -> typing.Iterator[list[dict[str, Any]]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


async def search_all_iam_policies_in_scope(
    scope: dict[str, Any],
    semaphore: BoundedSemaphore,
    asset_types: list[str],
    policy_query: str | None = None,
    rate_limiter: FixedWindowLimiter | None = None,
    scope_field: str = EXTRA_PROJECT_FIELD,
    asset_type: str | None = None,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Search explicit IAM allow policies within one project, folder, or organization.

    ``asset_type`` is accepted because project iteration passes it for logging.
    The Cloud Asset request uses ``asset_types``.
    """
    del asset_type  # logging context only; the request filters with asset_types

    def parse_policy_response(response: Any) -> list[dict[str, Any]]:
        return parse_protobuf_messages(response.results)

    scope_name = scope["name"]
    request: dict[str, Any] = {
        "scope": scope_name,
        "asset_types": list(asset_types),
    }
    if policy_query:
        request["query"] = policy_query

    async with semaphore:
        logger.info(
            f"Searching explicit IAM allow policies in {scope_name} "
            f"for asset types {asset_types}"
        )
        async_assets_client = get_asset_client()
        try:
            async for policies in paginated_query(
                async_assets_client,
                "search_all_iam_policies",
                request,
                parse_policy_response,
                rate_limiter,
                page_size=_IAM_POLICY_SEARCH_PAGE_SIZE,
            ):
                expanded = expand_iam_policy_bindings(policies, scope, scope_field)
                for batch in _batched(expanded, _IAM_POLICY_BINDING_BATCH_SIZE):
                    yield batch
        except PermissionDenied as e:
            logger.error(
                f"Service account doesn't have permission "
                f"cloudasset.assets.searchAllIamPolicies on scope {scope_name} "
                f"for asset types {asset_types}. Error: {str(e.message)}"
            )
        except NotFound as e:
            logger.info(
                f"Couldn't perform search_all_iam_policies on scope {scope_name} "
                f"since it wasn't found. Error: {str(e)}"
            )
        except Exception:
            logger.exception(
                f"Unexpected error while searching IAM allow policies in scope {scope_name}"
            )
            raise
        else:
            logger.info(
                f"Successfully searched IAM allow policies within scope {scope_name}"
            )


async def search_explicit_iam_policy_bindings(
    asset_types: list[str],
    policy_query: str | None,
    rate_limiter: FixedWindowLimiter,
    semaphore: BoundedSemaphore,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Read explicit allow-policy bindings for the selector's asset types.

    Project resources are searched once per accessible project. Folder and
    organization asset types are searched on those scopes only, so an
    organization search does not also return every descendant project policy.
    """
    (
        project_types,
        include_folders,
        include_organizations,
    ) = partition_iam_policy_asset_types(asset_types)

    if project_types:
        # Imported lazily: iterators imports search_all_projects from this module.
        from gcp_core.search.iterators import iterate_per_available_project

        async for batch in iterate_per_available_project(
            search_all_iam_policies_in_scope,
            asset_types=project_types,
            policy_query=policy_query,
            rate_limiter=rate_limiter,
            semaphore=semaphore,
            asset_type=AssetTypesWithSpecialHandling.IAM_POLICY,
        ):
            yield batch

    if include_folders:
        async for folders in search_all_folders():
            for folder in folders:
                async for batch in search_all_iam_policies_in_scope(
                    folder,
                    semaphore,
                    asset_types=[AssetTypesWithSpecialHandling.FOLDER],
                    policy_query=policy_query,
                    rate_limiter=rate_limiter,
                    scope_field=_FOLDER_SCOPE_FIELD,
                ):
                    yield batch

    if include_organizations:
        async for organizations in search_all_organizations():
            for organization in organizations:
                async for batch in search_all_iam_policies_in_scope(
                    organization,
                    semaphore,
                    asset_types=[AssetTypesWithSpecialHandling.ORGANIZATION],
                    policy_query=policy_query,
                    rate_limiter=rate_limiter,
                    scope_field=_ORGANIZATION_SCOPE_FIELD,
                ):
                    yield batch
