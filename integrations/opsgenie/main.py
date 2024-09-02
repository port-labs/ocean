from typing import Any, cast
from loguru import logger
import asyncio
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from client import OpsGenieClient
from utils import ObjectKind

from integration import AlertAndIncidentResourceConfig

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
        team_data, schedule = await asyncio.gather(
            opsgenie_client.get_oncall_team(service["teamId"]),
            opsgenie_client.get_schedule_by_team(service["teamId"]),
        )

        service["__team"] = team_data
        if schedule:
            service["__oncalls"] = await opsgenie_client.get_oncall_user(schedule["id"])
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
        yield service_batch


@ocean.on_resync(ObjectKind.INCIDENT)
async def on_incident_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    opsgenie_client = init_client()

    selector = cast(AlertAndIncidentResourceConfig, event.resource_config).selector
    async for incident_batch in opsgenie_client.get_paginated_resources(
        resource_type=ObjectKind.INCIDENT,
        query_params=selector.api_query_params.generate_request_params()
        if selector.api_query_params
        else None,
    ):
        logger.info(f"Received batch with {len(incident_batch)} incidents")
        yield incident_batch


@ocean.on_resync(ObjectKind.ALERT)
async def on_alert_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    opsgenie_client = init_client()

    selector = cast(AlertAndIncidentResourceConfig, event.resource_config).selector
    async for alerts_batch in opsgenie_client.get_paginated_resources(
        resource_type=ObjectKind.ALERT,
        query_params=selector.api_query_params.generate_request_params()
        if selector.api_query_params
        else None,
    ):
        logger.info(f"Received batch with {len(alerts_batch)} alerts")
        yield alerts_batch


@ocean.router.post("/webhook")
async def on_alert_webhook_handler(data: dict[str, Any]) -> None:
    opsgenie_client = init_client()
    event_type = data.get("action")

    logger.info(f"Processing OpsGenie webhook for event type: {event_type}")

    if event_type == "Delete":
        alert_data = data["alert"]
        alert_data["id"] = alert_data.pop("alertId")
        await ocean.unregister_raw(ObjectKind.ALERT, [alert_data])
    else:
        alert_id = data["alert"]["alertId"]
        alert_data = await opsgenie_client.get_alert(identifier=alert_id)
        await ocean.register_raw(ObjectKind.ALERT, [alert_data])
