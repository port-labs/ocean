from typing import Any

from loguru import logger

from clients.pagerduty import PagerDutyClient
from port_ocean.context.ocean import ocean


class ObjectKind:
    SERVICES = "services"
    INCIDENTS = "incidents"


pager_duty_client = PagerDutyClient(
    ocean.integration_config["token"],
    ocean.integration_config["api_url"],
    ocean.integration_config["app_host"],
)


@ocean.on_resync(ObjectKind.INCIDENTS)
async def on_incidents_resync(kind: str) -> list[dict[str, Any]]:
    logger.info(f"Listing Pagerduty resource: {kind}")

    return await pager_duty_client.paginate_request_to_pager_duty(
        data_key=ObjectKind.INCIDENTS
    )


@ocean.on_resync(ObjectKind.SERVICES)
async def on_services_resync(kind: str) -> list[dict[str, Any]]:
    logger.info(f"Listing Pagerduty resource: {kind}")

    services = await pager_duty_client.paginate_request_to_pager_duty(
        data_key=ObjectKind.SERVICES
    )
    return await pager_duty_client.update_oncall_users(services)


@ocean.router.post("/webhook")
async def upsert_incident_webhook_handler(data: dict[str, Any]) -> None:
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
    logger.info("Subscribing to Pagerduty webhooks")
    await pager_duty_client.create_webhooks_if_not_exists()
