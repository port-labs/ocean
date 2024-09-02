from typing import Any, cast
from loguru import logger
import asyncio
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from client import OpsGenieClient
from utils import ObjectKind, ResourceKindsWithSpecialHandling

from integration import AlertAndIncidentResourceConfig, ScheduleResourceConfig

CONCURRENT_REQUESTS = 5


def init_client() -> OpsGenieClient:
    return OpsGenieClient(
        ocean.integration_config["api_token"],
        ocean.integration_config["api_url"],
    )


async def enrich_services_with_oncall_data(
    opsgenie_client: OpsGenieClient,
    semaphore: asyncio.Semaphore,
    service_batch: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    team_ids = {service["teamId"] for service in service_batch if service.get("teamId")}

    schedules = await opsgenie_client.get_schedules_by_teams(list(team_ids))

    schedule_ids = [schedule["id"] for schedule in schedules.values()]

    async def fetch_oncall(schedule_id: str) -> tuple[str, dict[str, Any]]:
        async with semaphore:
            return schedule_id, await opsgenie_client.get_oncall_user(schedule_id)

    oncall_tasks = [fetch_oncall(schedule_id) for schedule_id in schedule_ids]
    results = await asyncio.gather(*oncall_tasks)

    oncalls = {}
    for schedule_id, oncall in results:
        oncalls[schedule_id] = oncall

    enriched_services = []
    for service in service_batch:
        team_id = service.get("teamId")
        if team_id:
            schedule = next(
                (
                    sched
                    for sched in schedules.values()
                    if sched["ownerTeam"]["id"] == team_id
                ),
                None,
            )
            if schedule:
                service["__oncalls"] = oncalls.get(schedule["id"], {})
        enriched_services.append(service)

    return enriched_services


@ocean.on_resync()
async def on_resources_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:

    if kind in iter(ResourceKindsWithSpecialHandling):
        logger.info(f"Kind {kind} has a special handling. Skipping...")
        return

    opsgenie_client = init_client()
    async for resource_batch in opsgenie_client.get_paginated_resources(
        resource_type=ObjectKind(kind)
    ):
        logger.info(f"Received batch with {len(resource_batch)} {kind}")
        yield resource_batch


@ocean.on_resync(ObjectKind.SERVICE)
async def on_service_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    opsgenie_client = init_client()
    semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)

    async for service_batch in opsgenie_client.get_paginated_resources(
        resource_type=ObjectKind.SERVICE
    ):
        logger.info(
            f"Received batch with {len(service_batch)} services, enriching with on-call data"
        )

        enriched_services = await enrich_services_with_oncall_data(
            opsgenie_client, semaphore, service_batch
        )
        yield enriched_services


@ocean.on_resync(ObjectKind.INCIDENT)
async def on_incident_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    opsgenie_client = init_client()

    selector = cast(AlertAndIncidentResourceConfig, event.resource_config).selector
    async for incident_batch in opsgenie_client.get_paginated_resources(
        resource_type=ObjectKind.INCIDENT,
        query_params=(
            selector.api_query_params.generate_request_params()
            if selector.api_query_params
            else None
        ),
    ):
        logger.info(f"Received batch with {len(incident_batch)} incidents")
        yield incident_batch


@ocean.on_resync(ObjectKind.ALERT)
async def on_alert_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    opsgenie_client = init_client()

    selector = cast(AlertAndIncidentResourceConfig, event.resource_config).selector
    async for alerts_batch in opsgenie_client.get_paginated_resources(
        resource_type=ObjectKind.ALERT,
        query_params=(
            selector.api_query_params.generate_request_params()
            if selector.api_query_params
            else None
        ),
    ):
        logger.info(f"Received batch with {len(alerts_batch)} alerts")
        yield alerts_batch


@ocean.on_resync(ObjectKind.SCHEDULE)
async def on_schedule_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    opsgenie_client = init_client()

    selector = cast(ScheduleResourceConfig, event.resource_config).selector
    async for schedules_batch in opsgenie_client.get_paginated_resources(
        resource_type=ObjectKind.SCHEDULE,
        query_params=(
            selector.api_query_params.generate_request_params()
            if selector.api_query_params
            else None
        ),
    ):
        logger.info(f"Received batch with {len(schedules_batch)} schedules")
        yield schedules_batch


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
