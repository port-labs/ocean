import typing
from enum import StrEnum
from typing import Any

from loguru import logger

from client import DatadogClient
from overrides import SLOHistoryResourceConfig, DatadogResourceConfig
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


class ObjectKind(StrEnum):
    HOST = "host"
    MONITOR = "monitor"
    SLO = "slo"
    SERVICE = "service"
    SLO_HISTORY = "sloHistory"
    DASHBOARD = "dashboard"
    DASHBOARD_METRIC = "dashboardMetric"


def init_client() -> DatadogClient:
    return DatadogClient(
        ocean.integration_config["datadog_base_url"],
        ocean.integration_config["datadog_api_key"],
        ocean.integration_config["datadog_application_key"],
    )


@ocean.on_resync(ObjectKind.HOST)
async def on_resync_hosts(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    dd_client = init_client()
    dashboard_ids_to_enrich_with = typing.cast(
        DatadogResourceConfig, event.resource_config
    ).selector.dashboard_ids_to_enrich_with

    async for hosts in dd_client.get_hosts():
        logger.info(f"Received batch with {len(hosts)} hosts")

        if not dashboard_ids_to_enrich_with:
            yield hosts

        logger.info(
            f"Enriching hosts with dashboard metrics from {dashboard_ids_to_enrich_with}"
        )

        for dashboard_id in dashboard_ids_to_enrich_with:
            enriched_hosts = await dd_client.enrich_kind_with_dashboard_metrics(
                dashboard_id,
                hosts,
                template_var="host",
                item_name_extractor=lambda item: item["host_name"],
            )
            yield enriched_hosts
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


@ocean.on_resync(ObjectKind.SLO_HISTORY)
async def on_resync_slo_histories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    dd_client = init_client()
    timeframe = typing.cast(
        SLOHistoryResourceConfig, event.resource_config
    ).selector.timeframe

    period_of_time_in_months = typing.cast(
        SLOHistoryResourceConfig, event.resource_config
    ).selector.period_of_time_in_months

    async for histories in dd_client.list_slo_histories(
        timeframe, period_of_time_in_months
    ):
        yield histories


@ocean.on_resync(ObjectKind.SERVICE)
async def on_resync_services(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    dd_client = init_client()

    dashboard_ids_to_enrich_with = typing.cast(
        DatadogResourceConfig, event.resource_config
    ).selector.dashboard_ids_to_enrich_with

    async for services in dd_client.get_services():
        logger.info(f"Received batch with {len(services)} services")

        if not dashboard_ids_to_enrich_with:
            yield services

        logger.info(
            f"Enriching services with dashboard metrics from {dashboard_ids_to_enrich_with}"
        )

        for dashboard_id in dashboard_ids_to_enrich_with:
            enriched_services = await dd_client.enrich_kind_with_dashboard_metrics(
                dashboard_id, services
            )
            yield enriched_services


@ocean.on_resync(ObjectKind.DASHBOARD)
async def on_resync_dashboards(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    dd_client = init_client()

    async for dashboards in dd_client.get_dashboards():
        logger.info(f"Received batch with {len(dashboards)} dashboards")
        yield dashboards


@ocean.on_resync(ObjectKind.DASHBOARD_METRIC)
async def on_resync_dashboard_metrics(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    dd_client = init_client()

    async for dashboard_metrics in dd_client.get_dashboard_metrics():
        logger.info(f"Received batch with {len(dashboard_metrics)} dashboard metrics")
        yield dashboard_metrics


# https://docs.datadoghq.com/integrations/webhooks/
@ocean.router.post("/webhook")
async def handle_webhook_request(data: dict[str, Any]) -> dict[str, Any]:
    logger.info(
        f"Received event type {data['event_type']} - Alert ID: {data['alert_id']}"
    )

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
