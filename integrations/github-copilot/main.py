from port_ocean.context.ocean import ocean
from clients.client_factory import create_github_client
from loguru import logger

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from kinds import ObjectKind


@ocean.on_resync(ObjectKind.ORGANIZATION_USAGE_METRICS)
async def on_resync_organization_usage_metrics(
    kind: str,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    github_client = create_github_client()
    if github_client.enterprise:
        logger.info(
            "Skipping organization-usage-metrics resync: integration is configured "
            "in enterprise mode. Use enterprise-usage-metrics instead."
        )
        return
    async for batch in github_client.fetch_organization_usage_metrics():
        yield batch


@ocean.on_resync(ObjectKind.USER_USAGE_METRICS)
@ocean.on_resync(ObjectKind.ORGANIZATION_USER_USAGE_METRICS)
async def on_resync_organization_user_usage_metrics(
    kind: str,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    github_client = create_github_client()
    if github_client.enterprise:
        logger.info(
            "Skipping organization-user-usage-metrics resync: integration is configured in "
            "enterprise mode. Use enterprise-user-usage-metrics instead."
        )
        return
    async for batch in github_client.fetch_users_usage_metrics():
        yield batch


@ocean.on_resync(ObjectKind.ENTERPRISE_USAGE_METRICS)
async def on_resync_enterprise_usage_metrics(
    kind: str,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    github_client = create_github_client()
    if not github_client.enterprise:
        logger.info(
            "Skipping enterprise-usage-metrics resync: integration is configured "
            "in organization mode. Use organization-usage-metrics instead."
        )
        return
    async for batch in github_client.fetch_enterprise_usage_metrics():
        yield batch


@ocean.on_resync(ObjectKind.ENTERPRISE_USER_USAGE_METRICS)
async def on_resync_enterprise_users_usage_metrics(
    kind: str,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    github_client = create_github_client()
    if not github_client.enterprise:
        logger.info(
            "Skipping enterprise-user-usage-metrics resync: integration is configured "
            "in organization mode. Use user-usage-metrics instead."
        )
        return
    async for batch in github_client.fetch_enterprise_users_usage_metrics():
        yield batch


@ocean.on_start()
async def on_start() -> None:
    github_client = create_github_client()
    mode = (
        f"enterprise mode (enterprise={github_client.enterprise})"
        if github_client.enterprise
        else "organization mode"
    )
    logger.info(f"Starting github-copilot integration in {mode}")
