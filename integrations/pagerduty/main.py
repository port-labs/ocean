import typing
from typing import Any

from loguru import logger

from clients.pagerduty import PagerDutyClient
from integration import ObjectKind, PagerdutyServiceResourceConfig
from integration import PagerdutyIncidentResourceConfig, PagerdutyScheduleResourceConfig
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


def initialize_client() -> PagerDutyClient:
    return PagerDutyClient(
        ocean.integration_config["token"],
        ocean.integration_config["api_url"],
        ocean.integration_config.get("app_host"),
    )


@ocean.on_resync(ObjectKind.INCIDENTS)
async def on_incidents_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing Pagerduty resource: {kind}")
    pager_duty_client = initialize_client()
    query_params = typing.cast(
        PagerdutyIncidentResourceConfig, event.resource_config
    ).selector.api_query_params

    async for incidents in pager_duty_client.paginate_request_to_pager_duty(
        data_key=ObjectKind.INCIDENTS,
        params=query_params.generate_request_params() if query_params else None,
    ):
        yield incidents


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


@ocean.on_resync(ObjectKind.SCHEDULES)
async def on_schedules_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing Pagerduty resource: {kind}")
    pager_duty_client = initialize_client()
    query_params = typing.cast(
        PagerdutyScheduleResourceConfig, event.resource_config
    ).selector.api_query_params

    async for schedules in pager_duty_client.paginate_request_to_pager_duty(
        data_key=ObjectKind.SCHEDULES,
        params=query_params.generate_request_params() if query_params else None,
    ):
        yield schedules


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
        await ocean.register_raw(ObjectKind.INCIDENTS, [response["incident"]])

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
