from enum import StrEnum
from typing import Any, Dict
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from client import OctopusClient


class ObjectKind(StrEnum):
    PROJECT = "project"
    DEPLOYMENT = "deployment"
    RELEASE = "release"
    TARGET = "target"


async def init_client() -> OctopusClient:
    client = OctopusClient(
        ocean.integration_config["octopus_api_key"],
        ocean.integration_config["octopus_url"],
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
    existing_subscriptions = await octopus_client.get_subscriptions()
    existing_webhook_uris = {
        subscription.get("EventNotificationSubscription", {}).get("WebhookURI")
        for subscription in existing_subscriptions
    }
    webhook_uri = f"{app_host}/integration/webhook"
    if webhook_uri in existing_webhook_uris:
        logger.info(f"Webhook already exists with URI: {webhook_uri}")
    else:
        await octopus_client.create_subscription(app_host)
        logger.info(f"Webhook created with URI: {webhook_uri}")


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    octopus_client = await init_client()
    async for projects in octopus_client.get_projects():
        logger.info(f"Received project batch with {len(projects)} projects")
        yield projects


@ocean.on_resync(ObjectKind.DEPLOYMENT)
async def on_resync_deployments(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    octopus_client = await init_client()
    async for deployments in octopus_client.get_deployments():
        logger.info(f"Received deployment batch with {len(deployments)} deployments")
        yield deployments


@ocean.on_resync(ObjectKind.RELEASE)
async def on_resync_releases(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    octopus_client = await init_client()
    async for releases in octopus_client.get_releases():
        logger.info(f"Received release batch with {len(releases)} releases")
        yield releases


@ocean.on_resync(ObjectKind.TARGET)
async def on_resync_machines(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    octopus_client = await init_client()
    async for machines in octopus_client.get_targets():
        logger.info(f"Received machine batch with {len(machines)} machines")
        yield machines


@ocean.router.post("/webhook")
async def handle_webhook_request(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle the webhook request from Octopus Deploy.
    """
    logger.info(f"Received webhook event: {data}")
    payload = data.get("Payload", {}).get("Event", {})
    related_document_ids = payload.get("RelatedDocumentIds", [])
    event_category = payload.get("Category", "")
    action = "unregister" if "Deleted" in event_category else "register"
    client = await init_client()
    for entity_id in related_document_ids:
        logger.info(f"{action.capitalize()}ing entity with ID: {entity_id}")
        entity_prefix = entity_id.split("-")[0].lower()
        if entity_prefix == "machines":
            kind = ObjectKind.TARGET
        else:
            kind = ObjectKind(entity_prefix)
        try:
            entity_data = await client.get_single_entity(entity_prefix, entity_id)
            if action == "register":
                await ocean.register_raw(kind, [entity_data])
            else:
                await ocean.unregister_raw(kind, [{"id": entity_id}])
        except Exception as e:
            logger.error(f"Failed to process entity {entity_id}: {e}")
    logger.info("Webhook event processed")
    return {"ok": True}


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean Octopus integration")
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return
    await setup_application()
