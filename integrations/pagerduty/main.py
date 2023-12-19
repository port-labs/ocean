import typing
from typing import Any
import asyncio

from loguru import logger

from clients.pagerduty import PagerDutyClient
from integration import ObjectKind, PagerdutyServiceResourceConfig
from integration import PagerdutyIncidentResourceConfig
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

CONCURRENT_REQUESTS = 5


def initialize_client() -> PagerDutyClient:
    return PagerDutyClient(
        ocean.integration_config["token"],
        ocean.integration_config["api_url"],
        ocean.integration_config.get("app_host"),
    )


async def enrich_incident_with_analytics_data(
    client: PagerDutyClient,
    semaphore: asyncio.Semaphore,
    incident: dict[str, Any],
) -> dict[str, Any]:
    async with semaphore:
        analytics_data = await client.get_incident_analytics(incident["id"])
        incident["__analytics"] = analytics_data
        return incident


@ocean.on_resync(ObjectKind.INCIDENTS)
async def on_incidents_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing Pagerduty resource: {kind}")
    pager_duty_client = initialize_client()
    semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)

    query_params = typing.cast(
        PagerdutyIncidentResourceConfig, event.resource_config
    ).selector.api_query_params

    async for incidents in pager_duty_client.paginate_request_to_pager_duty(
        data_key=ObjectKind.INCIDENTS,
        params=query_params.generate_request_params() if query_params else None,
    ):
        logger.info(f"Received batch with {len(incidents)} incidents")
        tasks = [
            enrich_incident_with_analytics_data(pager_duty_client, semaphore, incident)
            for incident in incidents
        ]
        enriched_incidents = await asyncio.gather(*tasks)
        yield enriched_incidents


@ocean.on_resync(ObjectKind.SERVICES)
async def on_services_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing Pagerduty resource: {kind}")
    pager_duty_client = initialize_client()
    query_params = typing.cast(
        PagerdutyServiceResourceConfig, event.resource_config
    ).selector.api_query_params

    async for services in pager_duty_client.paginate_request_to_pager_duty(
        data_key=ObjectKind.SERVICES,
        params=query_params.generate_request_params() if query_params else None,
    ):
        yield await pager_duty_client.update_oncall_users(services)


@ocean.router.post("/webhook")
async def upsert_incident_webhook_handler(data: dict[str, Any]) -> None:
    pager_duty_client = initialize_client()
    event_type = data["event"]["event_type"]
    logger.info(f"Processing Pagerduty webhook for event type: {event_type}")
    if event_type in pager_duty_client.service_delete_events:
        await ocean.unregister_raw(ObjectKind.SERVICES, [data["event"]["data"]])

    elif event_type in pager_duty_client.incident_upsert_events:
        incident_id = data["event"]["data"]["id"]
        response = await pager_duty_client.get_singular_from_pager_duty(
            object_type=ObjectKind.INCIDENTS, identifier=incident_id
        )
        analytics_data = await pager_duty_client.get_incident_analytics(
            incident_id=incident_id
        )
        incident_data = {**response["incident"], "__analytics": analytics_data}
        await ocean.register_raw(ObjectKind.INCIDENTS, [incident_data])

    elif event_type in pager_duty_client.service_upsert_events:
        service_id = data["event"]["data"]["id"]
        response = await pager_duty_client.get_singular_from_pager_duty(
            object_type=ObjectKind.SERVICES, identifier=service_id
        )
        services = await pager_duty_client.update_oncall_users([response["service"]])

        await ocean.register_raw(ObjectKind.SERVICES, services)


@ocean.on_start()
async def on_start() -> None:
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    pager_duty_client = initialize_client()
    logger.info("Subscribing to Pagerduty webhooks")
    await pager_duty_client.create_webhooks_if_not_exists()
