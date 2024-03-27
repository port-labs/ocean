from enum import StrEnum
from typing import Any

from loguru import logger

from client import DatadogClient
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


class ObjectKind(StrEnum):
    HOST = "host"
    MONITOR = "monitor"
    SLO = "slo"
    SERVICE = "serviceCatalog"


def init_client() -> DatadogClient:
    return DatadogClient(
        ocean.integration_config["datadog_base_url"],
        ocean.integration_config["datadog_api_key"],
        ocean.integration_config["datadog_application_key"],
    )


@ocean.on_resync(ObjectKind.HOST)
async def on_resync_hosts(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    dd_client = init_client()

    async for hosts in dd_client.get_hosts():
        logger.info(f"Received batch with {len(hosts)} hosts")
        yield hosts


@ocean.on_resync(ObjectKind.MONITOR)
async def on_resync_monitors(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    dd_client = init_client()

    async for monitors in dd_client.get_monitors():
        logger.info(f"Received batch with {len(monitors)} monitors")
        yield monitors


@ocean.on_resync(ObjectKind.SLO)
async def on_resync_slos(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    dd_client = init_client()

    async for slos in dd_client.get_slos():
        logger.info(f"Received batch with {len(slos)} slos")
        yield slos


@ocean.on_resync(ObjectKind.SERVICE)
async def on_resync_services(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    dd_client = init_client()

    async for services in dd_client.get_services():
        logger.info(f"Received batch with {len(services)} service catalogs")
        yield services


@ocean.router.post("/webhook")
async def handle_webhook_request(data: dict[str, Any]) -> dict[str, Any]:
    logger.info(f"Received event type {data['event_type']} \n {data}")

    dd_client = init_client()

    monitor = await dd_client.get_single_monitor(data["alert_id"])
    if monitor:
        logger.info(f"Updating monitor status for alert {monitor}")
        await ocean.register_raw(ObjectKind.MONITOR, [monitor])

    return {"ok": True}


@ocean.on_start()
async def on_start() -> None:
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    # Verify the presence of a webhook token or app_host, essential for creating subscriptions.
    # If not provided, skip webhook subscription creation.
    if ocean.integration_config.get("app_host") and ocean.integration_config.get(
            "datadog_webhook_token"
    ):
        dd_client = init_client()

        app_host = ocean.integration_config.get("app_host")
        dd_webhook_token = ocean.integration_config.get("datadog_webhook_token")

        await dd_client.create_webhooks_if_not_exists(app_host, dd_webhook_token)
