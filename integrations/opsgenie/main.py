from typing import Any
from enum import StrEnum
from loguru import logger

from port_ocean.context.ocean import ocean
from opsgenie_integration.client import OpsGenieClient


class ObjectKind(StrEnum):
    SCHEDULE = "schedules"
    ALERT = "alerts"


opsgenie_client = OpsGenieClient(
    ocean.integration_config["api_token"],
    ocean.integration_config["api_url"],
)


@ocean.on_resync(ObjectKind.SCHEDULE)
async def on_schedule_resync(kind: str) -> list[dict[Any, Any]]:
    logger.info(f"Listing OpsGenie resource: {kind}")
    schedules = await opsgenie_client.get_paginated_resources(
        resource_type=ObjectKind.SCHEDULE
    )
    return await opsgenie_client.update_oncall_users(schedules=schedules)


@ocean.on_resync(ObjectKind.ALERT)
async def on_alert_resync(kind: str) -> list[dict[Any, Any]]:
    logger.info(f"Listing OpsGenie resource: {kind}")
    return await opsgenie_client.get_paginated_resources(resource_type=ObjectKind.ALERT)


@ocean.router.post("/webhook")
async def on_alert_webhook_handler(data: dict[str, Any]) -> None:
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
