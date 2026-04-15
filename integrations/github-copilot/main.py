from enum import StrEnum

from port_ocean.context.ocean import ocean
from clients.client_factory import create_github_client
from loguru import logger

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


class ObjectKind(StrEnum):
    ORGANIZATION_USAGE_METRICS = "organization-usage-metrics"
    USER_USAGE_METRICS = "user-usage-metrics"


@ocean.on_resync(ObjectKind.ORGANIZATION_USAGE_METRICS)
async def on_resync_organization_usage_metrics(
    kind: str,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    github_client = create_github_client()
    async for batch in github_client.fetch_organization_usage_metrics():
        yield batch


@ocean.on_resync(ObjectKind.USER_USAGE_METRICS)
async def on_resync_copilot_users_usage_metrics(
    kind: str,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    github_client = create_github_client()
    async for batch in github_client.fetch_users_usage_metrics():
        yield batch


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting github-copilot integration")
