from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.utils.async_iterators import stream_async_iterators_tasks
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from client import ObjectKind
from init_client import init_octopus_client
from webhook_processors.space_webhook_processor import SpaceWebhookProcessor
from webhook_processors.resource_webhook_processor import ResourceWebhookProcessor


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean Octopus integration")

    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    await setup_application()


async def setup_application() -> None:
    client = init_octopus_client()
    app_host = ocean.integration_config.get("app_host")
    base_url = app_host or ocean.app.base_url
    if not base_url:
        logger.warning("Base url was not provided, skipping webhook creation")
        return

    async for spaces in client.get_all_spaces():
        space_tasks = [
            (space.get("Id"), client.get_webhook_subscriptions(space.get("Id")))
            for space in spaces
            if space.get("Id")
        ]

        for space_id, task in space_tasks:
            async for subscriptions in task:
                existing_webhook_uris = {
                    subscription.get("EventNotificationSubscription", {}).get(
                        "WebhookURI"
                    )
                    for subscription in subscriptions
                }
                webhook_uri = f"{base_url}/integration/webhook"
                if webhook_uri in existing_webhook_uris:
                    logger.info(f"Webhook already exists for space {space_id}")
                else:
                    await client.create_webhook_subscription(base_url, space_id)
                    logger.info(f"Webhook created for space {space_id}")


@ocean.on_resync()
async def resync_resources(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    if kind == ObjectKind.SPACE:
        return
    client = init_octopus_client()
    async for spaces in client.get_all_spaces():
        tasks = [
            client.get_paginated_resources(kind, path_parameter=space["Id"])
            for space in spaces
            if space["Id"]
        ]
        async for batch in stream_async_iterators_tasks(*tasks):
            yield batch


@ocean.on_resync(ObjectKind.SPACE)
async def resync_spaces(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = init_octopus_client()
    async for spaces in client.get_all_spaces():
        logger.info(f"Received batch {len(spaces)} spaces")
        yield spaces


ocean.add_webhook_processor("/webhook", SpaceWebhookProcessor)
ocean.add_webhook_processor("/webhook", ResourceWebhookProcessor)
