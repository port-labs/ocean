from typing import Any, Dict
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.utils.async_iterators import stream_async_iterators_tasks
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from client import OctopusClient, ObjectKind

TRACKED_EVENTS = [
    "spaces",
    "projects",
    "deployments",
    "releases",
    "machines",
]


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean Octopus integration")
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return
    await setup_application()


async def init_client() -> OctopusClient:
    client = OctopusClient(
        ocean.integration_config["server_url"],
        ocean.integration_config["octopus_api_key"],
    )
    return client


async def setup_application() -> None:
    app_host = ocean.integration_config.get("app_host")
    if not app_host:
        logger.warning(
            "App host was not provided, skipping webhook creation. "
            "Without setting up the webhook, you will have to manually initiate resync to get updates from Octopus."
        )
        return
    octopus_client = await init_client()
    async for spaces in octopus_client.get_all_spaces():
        space_tasks = [
            (space.get("Id"), octopus_client.get_webhook_subscriptions(space.get("Id")))
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
                webhook_uri = f"{app_host}/integration/webhook"
                if webhook_uri in existing_webhook_uris:
                    logger.info(
                        f"Webhook already exists with URI: {webhook_uri} for space {space_id}"
                    )
                else:
                    await octopus_client.create_webhook_subscription(app_host, space_id)
                    logger.info(
                        f"Webhook created with URI: {webhook_uri} for space {space_id}"
                    )


@ocean.on_resync()
async def resync_resources(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    if kind == ObjectKind.SPACE:
        return
    octopus_client = await init_client()
    async for spaces in octopus_client.get_all_spaces():
        tasks = [
            octopus_client.get_paginated_resources(kind, path_parameter=space["Id"])
            for space in spaces
            if space["Id"]
        ]
        async for batch in stream_async_iterators_tasks(*tasks):
            yield batch


@ocean.on_resync(ObjectKind.SPACE)
async def resync_spaces(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    octopus_client = await init_client()
    async for spaces in octopus_client.get_all_spaces():
        logger.info(f"Received batch {len(spaces)} spaces")
        yield spaces


@ocean.router.post("/webhook")
async def handle_webhook_request(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle the webhook request from Octopus Deploy.
    """
    logger.debug(f"Received webhook event: {data}")
    payload = data.get("Payload", {}).get("Event", {})
    related_document_ids = payload.get("RelatedDocumentIds", [])
    event_category = payload.get("Category", "")
    space_id = payload["SpaceId"]
    client = await init_client()
    if event_category == "Deleted":
        resource_id = (
            payload.get("ChangeDetails", {}).get("DocumentContext", {}).get("Id")
        )
        if resource_id and resource_id.split("-")[0].lower() in TRACKED_EVENTS:
            kind = ObjectKind(resource_id.split("-")[0].lower().rstrip("s"))
            await ocean.unregister_raw(kind, [{"Id": resource_id}])
    else:
        for resource_id in related_document_ids:
            logger.info(f"Received webhook event with ID: {resource_id}")
            resource_prefix = resource_id.split("-")[0].lower()
            if resource_prefix in TRACKED_EVENTS:
                if resource_prefix == ObjectKind.SPACE:
                    await client.get_single_space(space_id)
                    return {"ok": True}
                kind = ObjectKind(resource_prefix.rstrip("s"))
                try:
                    resource_data = await client.get_single_resource(
                        resource_prefix, resource_id, space_id
                    )
                    await ocean.register_raw(kind, [resource_data])
                except Exception as e:
                    logger.error(f"Failed to process resource {resource_id}: {e}")
    logger.info("Webhook event processed")
    return {"ok": True}
