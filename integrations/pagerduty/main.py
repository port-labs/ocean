from typing import Any, Dict, List
from clients.pagerduty import PagerDutyClient
from port_ocean.context.ocean import ocean
from starlette.requests import Request
from loguru import logger


class ObjectKind:
    SERVICES = "services"
    INCIDENTS = "incidents"


pager_duty_client = PagerDutyClient(
    ocean.integration_config["token"],
    ocean.integration_config["api_url"],
    ocean.integration_config["app_host"],
)


@ocean.on_resync(ObjectKind.INCIDENTS)
async def on_incidents_resync(kind: str) -> List[Dict[Any, Any]]:
    logger.info(f"Listing Pagerduty resource: {ObjectKind.INCIDENTS}")

    return await pager_duty_client.paginate_request_to_pager_duty(data_key="incidents")


@ocean.on_resync(ObjectKind.SERVICES)
async def on_services_resync(kind: str) -> List[Dict[Any, Any]]:
    logger.info(f"Listing Pagerduty resource: {ObjectKind.SERVICES}")

    return await pager_duty_client.paginate_request_to_pager_duty(data_key="services")


@ocean.router.post("/webhook")
async def upsert_incident_webhook_handler(
    data: Dict[str, Any], request: Request
) -> None:
    logger.info(
        f"Processing Pagerduty webhook for event type: {data['event']['event_type']}"
    )
    if data["event"]["event_type"] in pager_duty_client.service_delete_events:
        await ocean.unregister_raw("services", [data["event"]["data"]])

    elif data["event"]["event_type"] in pager_duty_client.incident_upsert_events:
        incident_id = data["event"]["data"]["id"]
        incident = await pager_duty_client.get_singular_from_pager_duty(
            plural="incidents", singular="incident", id=incident_id
        )
        await ocean.register_raw("incidents", [incident])

    elif data["event"]["event_type"] in pager_duty_client.service_upsert_events:
        service_id = data["event"]["data"]["id"]
        service = await pager_duty_client.get_singular_from_pager_duty(
            plural="services", singular="service", id=service_id
        )

        await ocean.register_raw("services", [service])


@ocean.on_start()
async def on_start() -> None:
    logger.info("Subscribing to Pagerduty webhooks")
    await pager_duty_client.create_webhooks_if_not_exists()
