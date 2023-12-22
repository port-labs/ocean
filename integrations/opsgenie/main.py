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
        team_data, schedule = await asyncio.gather(
            opsgenie_client.get_oncall_team(service["teamId"]),
            opsgenie_client.get_schedule_by_team(service["teamId"]),
        )

        service["__team"] = team_data
        if schedule:
            service["__oncalls"] = await opsgenie_client.get_oncall_user(schedule["id"])
        return service


async def enrich_incident_with_alert_data(
    opsgenie_client: OpsGenieClient,
    semaphore: asyncio.Semaphore,
    incident: dict[str, Any],
) -> dict[str, Any]:
    async with semaphore:
        if not incident["impactedServices"]:
            return incident
        impacted_services = await opsgenie_client.get_impacted_services(
            incident["impactedServices"]
        )
        incident["__impactedServices"] = impacted_services
        return incident


async def enrich_alert_with_related_Incident_data(
    opsgenie_client: OpsGenieClient,
    semaphore: asyncio.Semaphore,
    alert: dict[str, Any],
) -> dict[str, Any]:
    async with semaphore:
        alert_with_related_incident = (
            await opsgenie_client.get_related_incident_by_alert(alert)
        )
        return alert_with_related_incident


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


@ocean.on_resync(ObjectKind.INCIDENT)
async def on_incident_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    opsgenie_client = init_client()
    semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)

    async for incident_batch in opsgenie_client.get_paginated_resources(
        resource_type=ObjectKind.INCIDENT
    ):
        logger.info(f"Received batch with {len(incident_batch)} incident")
        tasks = [
            enrich_incident_with_alert_data(opsgenie_client, semaphore, incident)
            for incident in incident_batch
        ]
        enriched_incidents = await asyncio.gather(*tasks)
        yield enriched_incidents


@ocean.on_resync(ObjectKind.ALERT)
async def on_alert_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    opsgenie_client = init_client()
    semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)

    async for alerts_batch in opsgenie_client.get_paginated_resources(
        resource_type=ObjectKind.ALERT
    ):
        logger.info(f"Received batch with {len(alerts_batch)} alerts")

        tasks = [
            enrich_alert_with_related_Incident_data(opsgenie_client, semaphore, alert)
            for alert in alerts_batch
        ]
        enriched_alerts = await asyncio.gather(*tasks)
        yield enriched_alerts


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
