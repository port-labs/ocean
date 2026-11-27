import os
import tempfile
import typing
from typing import Any

from gcp_core.webhook.registry import register_webhook_processors
from google.api_core.exceptions import PermissionDenied
from loguru import logger

import gcp_core.clients as clients
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.core.probe import ProbeContext
from port_ocean.utils.signal import signal_handler

from gcp_core.audit_log import narrow_to_changed_projects
from gcp_core.cloud_function.resync import resync_cloud_function_resources
from gcp_core.overrides import (
    GCPCloudFunctionResourceConfig,
    GCPCloudResourceSelector,
    GCPIamPolicySelector,
)
from gcp_core.probe.probe import GcpPermissionProbe
from gcp_core.search.iterators import as_single_page, iterate_per_available_project
from gcp_core.search.resource_searches import (
    list_all_subscriptions_per_project,
    list_all_topics_per_project,
    search_all_folders,
    search_all_organizations,
    search_all_iam_policies_per_project,
    search_all_projects,
    search_all_resources,
)
from gcp_core.utils import (
    AssetTypesWithSpecialHandling,
    get_current_resource_config,
    get_credentials_json,
    resolve_request_controllers,
)


async def _resolve_resync_method_for_resource(
    kind: str,
    projects: list[dict[str, Any]] | None = None,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Which API this kind is fetched from, over which projects.

    `projects` is the scope, not a mode: `None` means every available project, a list
    means only those. A full resync passes nothing and an incremental run passes the
    projects that changed, so both get the same fetch for a given kind - which is the
    point of resolving it in one place.
    """
    match kind:
        case AssetTypesWithSpecialHandling.TOPIC:
            topic_rate_limiter, _ = await resolve_request_controllers(kind)
            return iterate_per_available_project(
                list_all_topics_per_project,
                asset_type=kind,
                projects=projects,
                rate_limiter=topic_rate_limiter,
            )
        case AssetTypesWithSpecialHandling.SUBSCRIPTION:
            subscription_rate_limiter, _ = await resolve_request_controllers(kind)
            return iterate_per_available_project(
                list_all_subscriptions_per_project,
                asset_type=kind,
                projects=projects,
                rate_limiter=subscription_rate_limiter,
            )
        case AssetTypesWithSpecialHandling.FOLDER:
            return search_all_folders()
        case AssetTypesWithSpecialHandling.ORGANIZATION:
            return search_all_organizations()
        case AssetTypesWithSpecialHandling.PROJECT:
            # The project objects *are* this kind's entities, so a narrowed run has
            # nothing left to fetch and only needs them in a generator's shape.
            if projects is not None:
                return as_single_page(projects)
            return search_all_projects()
        case _:
            asset_rate_limiter, asset_semaphore = await resolve_request_controllers(
                kind
            )
            return iterate_per_available_project(
                search_all_resources,
                asset_type=kind,
                projects=projects,
                rate_limiter=asset_rate_limiter,
                semaphore=asset_semaphore,
            )


@ocean.on_start()
async def setup_application_default_credentials() -> None:
    signal_handler.register(clients.close)

    if not ocean.integration_config["encoded_adc_configuration"]:
        logger.info(
            "Using integration's environment Application Default Credentials configuration"
        )
        return
    credentials_json = get_credentials_json()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as temp_file:
        temp_file.write(credentials_json.encode("utf-8"))
        credentials_path = temp_file.name

    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
    logger.info("Created Application Default Credentials configuration")


@ocean.on_probe()
async def probe(context: ProbeContext) -> ProbeContext:
    logger.info(
        f"Probing GCP permissions for {len(context.available_kinds)} resource kinds"
    )
    await setup_application_default_credentials()
    await GcpPermissionProbe(context).run()
    return context


@ocean.on_resync(kind=AssetTypesWithSpecialHandling.FOLDER)
async def resync_folders(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for batch in search_all_folders():
        yield batch


@ocean.on_resync(kind=AssetTypesWithSpecialHandling.ORGANIZATION)
async def resync_organizations(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for batch in search_all_organizations():
        yield batch


@ocean.on_incremental_resync(kind=AssetTypesWithSpecialHandling.PROJECT)
@ocean.on_resync(kind=AssetTypesWithSpecialHandling.PROJECT)
async def resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    iterator_resync_method = await _resolve_resync_method_for_resource(
        kind, projects=await narrow_to_changed_projects()
    )
    async for batch in iterator_resync_method:
        yield batch


@ocean.on_incremental_resync(kind=AssetTypesWithSpecialHandling.TOPIC)
@ocean.on_resync(kind=AssetTypesWithSpecialHandling.TOPIC)
async def resync_topics(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    topic_rate_limiter, _ = await resolve_request_controllers(kind)
    async for batch in iterate_per_available_project(
        list_all_topics_per_project,
        asset_type=kind,
        projects=await narrow_to_changed_projects(),
        topic_rate_limiter=topic_rate_limiter,
    ):
        yield batch


@ocean.on_incremental_resync(kind=AssetTypesWithSpecialHandling.SUBSCRIPTION)
@ocean.on_resync(kind=AssetTypesWithSpecialHandling.SUBSCRIPTION)
async def resync_subscriptions(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    topic_rate_limiter, _ = await resolve_request_controllers(kind)
    async for batch in iterate_per_available_project(
        list_all_subscriptions_per_project,
        asset_type=kind,
        projects=await narrow_to_changed_projects(),
        topic_rate_limiter=topic_rate_limiter,
    ):
        yield batch


@ocean.on_resync(kind=AssetTypesWithSpecialHandling.CLOUD_FUNCTION)
async def resync_cloud_function(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    config = typing.cast(GCPCloudFunctionResourceConfig, get_current_resource_config())
    integration_id = getattr(ocean.config.integration, "identifier", "gcp-integration")
    agent = f"gcp/{integration_id}"
    secrets = ocean.integration_config.get("cloud_function_secret", {})
    async for page in resync_cloud_function_resources(config, agent, secrets):
        yield page


@ocean.on_incremental_resync()
@ocean.on_resync()
async def resync_resources(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    if kind in AssetTypesWithSpecialHandling:
        logger.debug("Kind already has a specific handling, skipping")
        return
    asset_rate_limiter, asset_semaphore = await resolve_request_controllers(kind)
    async for batch in iterate_per_available_project(
        search_all_resources,
        asset_type=kind,
        projects=await narrow_to_changed_projects(),
        rate_limiter=asset_rate_limiter,
        semaphore=asset_semaphore,
    ):
        yield batch


@ocean.on_incremental_resync(kind=AssetTypesWithSpecialHandling.CLOUD_RESOURCE)
@ocean.on_resync(kind=AssetTypesWithSpecialHandling.CLOUD_RESOURCE)
async def resync_cloud_resources(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    resource_kinds = typing.cast(
        GCPCloudResourceSelector, get_current_resource_config().selector
    ).resource_kinds
    projects = await narrow_to_changed_projects()
    for resource_kind in resource_kinds:
        logger.info(
            f"Found Cloud Resource kind {resource_kind}, finding relevant resources.."
        )
        iterator_resync_method = await _resolve_resync_method_for_resource(
            resource_kind, projects=projects
        )
        async for resources_batch in iterator_resync_method:
            yield resources_batch


@ocean.on_incremental_resync(kind=AssetTypesWithSpecialHandling.IAM_POLICY)
@ocean.on_resync(kind=AssetTypesWithSpecialHandling.IAM_POLICY)
async def resync_iam_policies(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = typing.cast(GCPIamPolicySelector, get_current_resource_config().selector)
    rate_limiter, semaphore = await resolve_request_controllers(kind)
    projects = await narrow_to_changed_projects()
    try:
        async for batch in iterate_per_available_project(
            search_all_iam_policies_per_project,
            asset_type=kind,
            projects=projects,
            asset_types=selector.asset_types,
            policy_query=selector.policy_query,
            rate_limiter=rate_limiter,
            semaphore=semaphore,
        ):
            yield batch

    except ExceptionGroup as project_errors:
        _, not_denied = project_errors.split(PermissionDenied)
        if projects is None or not_denied is not None:
            raise
        logger.error(
            f"Service account doesn't have permissions to search IAM policies within "
            f"{len(project_errors.exceptions)} of {len(projects)} project(s) for kind {kind}. "
            "Grant cloudasset.assets.searchAllIamPolicies on every project in scope. "
            "Each project is named in the errors above, and their grants are not "
            "refreshed until the next full resync"
        )


register_webhook_processors()
