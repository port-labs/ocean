import os
import tempfile
import typing
from asyncio import BoundedSemaphore
from gcp_core.webhook.registry import register_webhook_processors
from loguru import logger

import gcp_core.clients as clients
from gcp_core.helpers.ratelimiter.fixed_window import FixedWindowLimiter
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.signal import signal_handler

from gcp_core.overrides import (
    GCPCloudResourceSelector,
)
from gcp_core.search.iterators import iterate_per_available_project
from gcp_core.search.resource_searches import (
    list_all_subscriptions_per_project,
    list_all_topics_per_project,
    search_all_folders,
    search_all_organizations,
    search_all_projects,
    search_all_resources,
)
from gcp_core.utils import (
    AssetTypesWithSpecialHandling,
    get_current_resource_config,
    get_credentials_json,
    resolve_request_controllers,
)

RATE_LIMITER_TIME_PERIOD_SECONDS: float = 60.0

PROJECT_V3_GET_REQUESTS_RATE_LIMITER: FixedWindowLimiter
PROJECT_V3_GET_REQUESTS_BOUNDED_SEMAPHORE: BoundedSemaphore
BACKGROUND_TASK_THRESHOLD: float


async def _resolve_resync_method_for_resource(
    kind: str,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    match kind:
        case AssetTypesWithSpecialHandling.TOPIC:
            topic_rate_limiter, _ = await resolve_request_controllers(kind)
            return iterate_per_available_project(
                list_all_topics_per_project,
                asset_type=kind,
                rate_limiter=topic_rate_limiter,
            )
        case AssetTypesWithSpecialHandling.SUBSCRIPTION:
            subscription_rate_limiter, _ = await resolve_request_controllers(kind)
            return iterate_per_available_project(
                list_all_subscriptions_per_project,
                asset_type=kind,
                rate_limiter=subscription_rate_limiter,
            )
        case AssetTypesWithSpecialHandling.FOLDER:
            return search_all_folders()
        case AssetTypesWithSpecialHandling.ORGANIZATION:
            return search_all_organizations()
        case AssetTypesWithSpecialHandling.PROJECT:
            return search_all_projects()
        case _:
            asset_rate_limiter, asset_semaphore = await resolve_request_controllers(
                kind
            )
            return iterate_per_available_project(
                search_all_resources,
                asset_type=kind,
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


@ocean.on_resync(kind=AssetTypesWithSpecialHandling.FOLDER)
async def resync_folders(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for batch in search_all_folders():
        yield batch


@ocean.on_resync(kind=AssetTypesWithSpecialHandling.ORGANIZATION)
async def resync_organizations(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for batch in search_all_organizations():
        yield batch


@ocean.on_resync(kind=AssetTypesWithSpecialHandling.PROJECT)
async def resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for batch in search_all_projects():
        yield batch


@ocean.on_resync(kind=AssetTypesWithSpecialHandling.TOPIC)
async def resync_topics(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    topic_rate_limiter, _ = await resolve_request_controllers(kind)
    async for batch in iterate_per_available_project(
        list_all_topics_per_project,
        asset_type=kind,
        topic_rate_limiter=topic_rate_limiter,
    ):
        yield batch


@ocean.on_resync(kind=AssetTypesWithSpecialHandling.SUBSCRIPTION)
async def resync_subscriptions(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    topic_rate_limiter, _ = await resolve_request_controllers(kind)
    async for batch in iterate_per_available_project(
        list_all_subscriptions_per_project,
        asset_type=kind,
        topic_rate_limiter=topic_rate_limiter,
    ):
        yield batch


@ocean.on_resync()
async def resync_resources(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    if kind in AssetTypesWithSpecialHandling:
        logger.debug("Kind already has a specific handling, skipping")
        return
    asset_rate_limiter, asset_semaphore = await resolve_request_controllers(kind)
    async for batch in iterate_per_available_project(
        search_all_resources,
        asset_type=kind,
        rate_limiter=asset_rate_limiter,
        semaphore=asset_semaphore,
    ):
        yield batch


@ocean.on_resync(kind=AssetTypesWithSpecialHandling.CLOUD_RESOURCE)
async def resync_cloud_resources(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    resource_kinds = typing.cast(
        GCPCloudResourceSelector, get_current_resource_config().selector
    ).resource_kinds
    for resource_kind in resource_kinds:
        logger.info(
            f"Found Cloud Resource kind {resource_kind}, finding relevant resources.."
        )
        iterator_resync_method = await _resolve_resync_method_for_resource(
            resource_kind
        )
        async for resources_batch in iterator_resync_method:
            yield resources_batch


register_webhook_processors()
