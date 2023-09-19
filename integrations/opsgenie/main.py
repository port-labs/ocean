from typing import Any
from loguru import logger
import asyncio
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.context.ocean import ocean
from client import OpsGenieClient
from utils import ObjectKind

CONCURRENT_REQUESTS = 5


def init_client() -> OpsGenieClient:
    return OpsGenieClient(
        ocean.integration_config["api_token"],
        ocean.integration_config["api_url"],
    )


async def enrich_services_with_team_data(
    opsgenie_client: OpsGenieClient,
    semaphore: asyncio.Semaphore,
    service: dict[str, Any],
) -> dict[str, Any]:
    async with semaphore:
        team_data = await opsgenie_client.get_oncall_team(service["teamId"])
        service["__team"] = team_data
        return service


@ocean.on_resync(ObjectKind.SERVICE)
async def on_service_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    opsgenie_client = init_client()
    semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)

    async for service_batch in opsgenie_client.get_paginated_resources(
        resource_type=ObjectKind.SERVICE
    ):
        logger.info(f"Received batch with {len(service_batch)} services")
        tasks = [
            enrich_services_with_team_data(opsgenie_client, semaphore, service)
            for service in service_batch
        ]
        enriched_services = await asyncio.gather(*tasks)
        yield enriched_services


@ocean.on_resync(ObjectKind.ALERT)
async def on_alert_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    opsgenie_client = init_client()
    async for alerts in opsgenie_client.get_paginated_resources(
        resource_type=ObjectKind.ALERT
    ):
        logger.info(f"Received batch with {len(alerts)} alerts")
        yield alerts


@ocean.router.post("/webhook")
async def on_alert_webhook_handler(data: dict[str, Any]) -> None:
    opsgenie_client = init_client()
    event_type = data.get("action")

    logger.info(f"Processing OpsGenie webhook for event type: {event_type}")

    if event_type in opsgenie_client.delete_alert_events:
        alert_data = data.get("alert", {})
        alert_data["id"] = alert_data.pop("alertId")
        await ocean.unregister_raw(ObjectKind.ALERT, [alert_data])
    else:
        alert_id = data.get("alert", {}).get("alertId")
        alert_data = await opsgenie_client.get_alert(identifier=alert_id)
        await ocean.register_raw(ObjectKind.ALERT, [alert_data])
