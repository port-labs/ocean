from enum import StrEnum
from typing import Any
from loguru import logger

from client import StatusPageClient
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


class ObjectKind(StrEnum):
    PAGE = "statuspage"
    COMPONENT_GROUPS = "component_group"
    COMPONENT = "component"
    INCIDENT = "incident"
    INCIDENT_UPDATE = "incident_update"


def init_client() -> StatusPageClient:
    return StatusPageClient(
        statuspage_host=ocean.integration_config["statuspage_host"],
        statuspage_api_key=ocean.integration_config["statuspage_api_key"],
        statuspage_ids=ocean.integration_config.get("statuspage_ids"),
    )


@ocean.on_resync(ObjectKind.PAGE)
async def resync_statuspage(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = init_client()
    pages = await client.get_pages()
    logger.info(f"Found {len(pages)} status pages")
    yield pages


@ocean.on_resync(ObjectKind.COMPONENT_GROUPS)
async def resync_component_groups(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = init_client()

    async for component_groups in client.get_component_groups():
        logger.info(
            f"Received component group batch with {len(component_groups)} component groups"
        )
        yield component_groups


@ocean.on_resync(ObjectKind.COMPONENT)
async def resync_components(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = init_client()

    async for components in client.get_components():
        logger.info(f"Received component batch with {len(components)} components")
        yield components


@ocean.on_resync(ObjectKind.INCIDENT)
async def resync_incidents(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = init_client()

    async for incidents in client.get_incidents():
        logger.info(f"Received incident batch with {len(incidents)} incidents")
        yield incidents


@ocean.on_resync(ObjectKind.INCIDENT_UPDATE)
async def resync_incident_updates(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = init_client()

    async for incident_updates in client.get_incident_updates():
        logger.info(
            f"Received incident update batch with {len(incident_updates)} incident updates"
        )
        yield incident_updates


@ocean.router.post("/webhook")
async def handle_webhook_request(data: dict[str, Any]) -> dict[str, Any]:
    """Handles incoming Statuspage webhook events, registers relevant data with ocean."""

    logger.info(f"Received Statuspage webhook event: {data}")
    client = init_client()

    if "page" in data:
        page_id = data["page"]["id"]
        page = await client.get_page_by_id(page_id)
        logger.debug(f"Received page: {page}")
        await ocean.register_raw(ObjectKind.PAGE, [{**data["page"], **page}])

    if "incident" in data:
        await ocean.register_raw(ObjectKind.INCIDENT, [data["incident"]])

        if "incident_updates" in data["incident"]:
            await ocean.register_raw(
                ObjectKind.INCIDENT_UPDATE, data["incident"]["incident_updates"]
            )

    return {"ok": True}


@ocean.on_start()
async def on_start() -> None:
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    # Verify the presence of app_host, essential for creating subscriptions.
    # If not provided, skip webhook subscription creation.
    app_host = ocean.integration_config.get("app_host")
    page_ids = ocean.integration_config.get("statuspage_ids")

    if not app_host:
        logger.error("App host is not provided. Skipping webhook creation.")
        return
    client = init_client()

    logger.info(f"App host: {app_host}")
    logger.info(f"Page IDs: {page_ids}")

    await client.create_webhooks_for_all_pages(app_host)
