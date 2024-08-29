from typing import Any, cast
from loguru import logger
from more_itertools import chunked
from collections import defaultdict
import asyncio
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from client import OpsGenieClient
from utils import ObjectKind

from integration import AlertResourceConfig, IncidentResourceConfig

CONCURRENT_REQUESTS = 5
INCIDENT_CHUNK_SIZE = 20


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


async def enrich_incidents_with_impacted_services(
    opsgenie_client: OpsGenieClient,
    semaphore: asyncio.Semaphore,
    incidents: list[dict[str, Any]],
    chunk_size: int = INCIDENT_CHUNK_SIZE,
) -> list[dict[str, Any]]:
    enriched_incidents = []

    for incident_chunk in chunked(incidents, chunk_size):
        impacted_service_ids = set()
        incident_to_service_map = defaultdict(list)

        for incident in incident_chunk:
            if incident["impactedServices"]:
                impacted_service_ids.update(incident["impactedServices"])
                incident_to_service_map[incident["id"]] = incident["impactedServices"]
        logger.info(
            f"Got {len(impacted_service_ids)} unique impacted services from {len(incident_chunk)} incidents with a chunk size of {chunk_size}"
        )

        # Fetch all impacted services for this chunk in one API call
        async with semaphore:
            all_impacted_services = await opsgenie_client.get_impacted_services(
                list(impacted_service_ids)
            )

        # Map impacted services back to the incidents in this chunk
        services_dict = {service["id"]: service for service in all_impacted_services}
        for incident in incident_chunk:
            incident["__impactedServices"] = [
                services_dict[service_id]
                for service_id in incident_to_service_map[incident["id"]]
                if service_id in services_dict
            ]
        enriched_incidents.extend(incident_chunk)
    return enriched_incidents


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

    selector = cast(IncidentResourceConfig, event.resource_config).selector
    async for incident_batch in opsgenie_client.get_paginated_resources(
        resource_type=ObjectKind.INCIDENT,
        query_params=selector.api_query_params.generate_request_params()
        if selector.api_query_params
        else None,
    ):
        logger.info(f"Received batch with {len(incident_batch)} incidents")

        if selector.enrich_services:
            enriched_incidents = await enrich_incidents_with_impacted_services(
                opsgenie_client,
                semaphore,
                incident_batch,
                chunk_size=INCIDENT_CHUNK_SIZE,
            )
            yield enriched_incidents
        yield incident_batch


@ocean.on_resync(ObjectKind.ALERT)
async def on_alert_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    opsgenie_client = init_client()

    selector = cast(AlertResourceConfig, event.resource_config).selector
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
