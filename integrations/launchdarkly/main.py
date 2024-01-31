from loguru import logger
from port_ocean.context.ocean import ocean
from client import LaunchDarklyClient,ResourceKindsWithSpecialHandling
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from enum import StrEnum
from typing import Any


class ObjectKind(StrEnum):
    PROJECT = "project"
    AUDITLOG = "auditlog"


def initialize_client() -> LaunchDarklyClient:
    return LaunchDarklyClient(
        launchdarkly_url=ocean.integration_config["launchdarkly_host"],
        api_token=ocean.integration_config["launchdarkly_token"],
    )


@ocean.on_resync()
async def on_resources_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing Lauchdarkly resource: {kind}")
    launchdarkly_client = initialize_client()

    if kind in iter(ResourceKindsWithSpecialHandling):
        logger.info(f"Kind {kind} has a special handling. Skipping...")
        yield []

    else:
        async for items in launchdarkly_client.get_paginated_resource(resource_kind=kind):
            logger.info(f"Received {kind} batch with {len(items)} items")
            print(kind.upper(), items)
            yield items


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.FEATURE_FLAGS)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing Lauchdarkly resource: {kind}")
    launchdarkly_client = initialize_client()
    async for items in launchdarkly_client.get_paginated_feature_flags(kind):
        yield items


@ocean.router.post("/webhook")
async def handle_launchdarkly_webhook_request(data: dict[str, Any]) -> dict[str, Any]:
    print("WEBHOOK DATA",data)
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

