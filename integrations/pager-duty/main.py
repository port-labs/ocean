from typing import Any, Dict, List
from clients.pager_duty import PagerDutyClient


from port_ocean.context.event import event_context

from port_ocean.context.ocean import ocean
from starlette.requests import Request


pager_duty_client = PagerDutyClient(
    ocean.integration_config["token"],
    ocean.integration_config["url"],
    ocean.integration_config["appUrl"],
)


@ocean.on_resync("incidents")
async def on_resync(kind: str) -> List[Dict[Any, Any]]:
    url = ocean.integration_config["url"]

    incidents = pager_duty_client.paginate_request_to_pager_duty(
        f"{url}/incidents", data_key="incidents"
    )

    return incidents


@ocean.on_resync("services")
async def on_resync(kind: str) -> List[Dict[Any, Any]]:
    url = ocean.integration_config["url"]

    services = pager_duty_client.paginate_request_to_pager_duty(
        f"{url}/services", data_key="services"
    )

    return services


@ocean.router.post("/webhook")
async def upsertIncident(data: Dict, request: Request):
    if data["event"]["event_type"] in pager_duty_client.service_delete_events:
        async with event_context("service"):
            await ocean.register_raw(
                "services", {"before": [data["event"]["data"]], "after": []}
            )

    elif data["event"]["event_type"] in pager_duty_client.incident_upsert_events:
        async with event_context("incident"):
            await ocean.register_raw(
                "incidents", {"before": [], "after": [data["event"]["data"]]}
            )

    elif data["event"]["event_type"] in pager_duty_client.service_upsert_events:
        service_id = data["event"]["data"]["id"]
        service = pager_duty_client.get_singular_from_pager_duty(
            plural="services", singular="service", id=service_id
        )

        async with event_context("service"):
            await ocean.register_raw("services", {"before": [], "after": [service]})


@ocean.on_start()
async def on_start() -> None:
    pager_duty_client.create_webhooks_if_not_exists()
