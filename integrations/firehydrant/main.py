import asyncio
from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from client import FirehydrantClient
from init_client import init_client
from utils import ObjectKind
from webhook.registry import register_live_events_webhooks


async def enrich_retrospective_with_incident_data(
    http_client: FirehydrantClient, semaphore: asyncio.Semaphore, report: dict[str, Any]
) -> dict[str, Any]:
    async with semaphore:
        tasks = await http_client.get_tasks_by_incident(report["incident"]["id"])
        report["__incident"] = {"tasks": tasks}
        return report


@ocean.on_resync(ObjectKind.ENVIRONMENT)
async def on_environment_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    firehydrant_client = init_client()

    async for environments in firehydrant_client.get_paginated_resource(
        resource_type=ObjectKind.ENVIRONMENT
    ):
        logger.debug(f"Received batch with {len(environments)} environments")
        yield environments


@ocean.on_resync(ObjectKind.SERVICE)
async def on_service_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    firehydrant_client = init_client()

    async for services in firehydrant_client.get_paginated_resource(
        resource_type=ObjectKind.SERVICE
    ):
        logger.debug(f"Received batch with {len(services)} services")
        enriched_services = await firehydrant_client.get_incident_milestones(
            services=services
        )
        yield enriched_services


@ocean.on_resync(ObjectKind.INCIDENT)
async def on_incident_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    firehydrant_client = init_client()

    async for incidents in firehydrant_client.get_paginated_resource(
        resource_type=ObjectKind.INCIDENT
    ):
        logger.debug(f"Received batch with {len(incidents)} incidents")
        yield incidents


@ocean.on_resync(ObjectKind.RETROSPECTIVE)
async def on_retrospective_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    firehydrant_client = init_client()

    async for reports in firehydrant_client.get_paginated_resource(
        ObjectKind.RETROSPECTIVE
    ):
        logger.debug(
            f"Received batch with {len(reports)} reports, getting their tasks completion status"
        )
        semaphore = asyncio.Semaphore(5)
        tasks = [
            enrich_retrospective_with_incident_data(
                firehydrant_client, semaphore, report
            )
            for report in reports
        ]
        enriched_reports = await asyncio.gather(*tasks)
        yield enriched_reports


@ocean.on_start()
async def on_start() -> None:
    if not ocean.app.config.event_listener.should_process_webhooks:
        logger.info(
            "Skipping webhook subscription because the event listener doesn't support webhooks"
        )
        return

    base_url = ocean.app.base_url
    if not base_url:
        logger.info(
            "Skipping webhook subscription because no base URL is configured. "
            "Set OCEAN__BASE_URL to enable live events."
        )
        return

    logger.info("Subscribing to FireHydrant webhooks")
    firehydrant_client = init_client()
    await firehydrant_client.create_webhooks_if_not_exists(base_url=base_url)
    logger.info("Subscribed to FireHydrant webhook events")


register_live_events_webhooks()
