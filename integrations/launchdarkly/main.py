from loguru import logger
from port_ocean.context.ocean import ocean
from client import LaunchDarklyClient, ResourceKindsWithSpecialHandling, ObjectKind
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from typing import Any


def initialize_client() -> LaunchDarklyClient:
    return LaunchDarklyClient(
        launchdarkly_url=ocean.integration_config["launchdarkly_host"],
        api_token=ocean.integration_config["launchdarkly_token"],
    )


@ocean.on_resync()
async def on_resources_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing Lauchdarkly resource: {kind}")
    launchdarkly_client = initialize_client()

    if kind in iter(ObjectKind):
        async for items in launchdarkly_client.get_paginated_resource(kind):
            logger.info(f"Received {kind} batch with {len(items)} items")
            yield items

    else:
        logger.info(f"Kind {kind} has a special handling. Skipping...")
        yield []


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.FEATURE_FLAG)
async def on_resync_flags(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing Lauchdarkly resource: {kind}")
    launchdarkly_client = initialize_client()
    async for flags in launchdarkly_client.get_paginated_feature_flags(kind):
        yield flags


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.ENVIRONMENT)
async def on_resync_environments(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing Lauchdarkly resource: {kind}")
    launchdarkly_client = initialize_client()
    async for environments in launchdarkly_client.get_paginated_environments(kind):
        yield environments


@ocean.router.post("/webhook")
async def handle_launchdarkly_webhook_request(data: dict[str, Any]) -> dict[str, Any]:
    launchdarkly_client = initialize_client()

    kind = data["kind"]

    if kind in iter(ObjectKind):
        logger.info(f"Received webhook event for {kind}")
        item = await launchdarkly_client.get_single_resource(data)
        await ocean.register_raw(kind, [item])

    elif kind == ResourceKindsWithSpecialHandling.FEATURE_FLAG:
        logger.info("Received webhook event for feature flag")
        flag = await launchdarkly_client.get_single_feature_flag(data)
        await ocean.register_raw(kind, [flag])

    elif kind == ResourceKindsWithSpecialHandling.ENVIRONMENT:
        logger.info("Received webhook event for environment")
        environment = await launchdarkly_client.get_single_environment(data)
        await ocean.register_raw(kind, [environment])

    logger.info("Launchdarkly webhook event processed")
    return {"ok": True}


@ocean.on_start()
async def on_start() -> None:
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    if not ocean.integration_config.get("app_host"):
        logger.warning(
            "No app host provided, skipping webhook creation. "
            "Without setting up the webhook, the integration will not export live changes from Launchdarkly"
        )
        return
    launchdarkly_client = initialize_client()
    await launchdarkly_client.create_launchdarkly_webhook(
        ocean.integration_config["app_host"]
    )
