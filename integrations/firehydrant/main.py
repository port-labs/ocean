from typing import Any
from enum import StrEnum
from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.context.ocean import ocean
import asyncio
from client import FirehydrantClient


class ObjectKind(StrEnum):
    ENVIRONMENT = "environment"
    INCIDENT = "incident"
    SERVICE = "service"
    RETROSPECTIVE = "retrospective"


## Helper function to initialize the Firehydrant client
def init_client() -> FirehydrantClient:
    return FirehydrantClient(
        ocean.integration_config["api_url"],
        ocean.integration_config["token"],
        ocean.integration_config.get("app_host", ""),
    )


## Enriches the incident report data
async def process_incident_tasks(
    semaphore: asyncio.Semaphore, report: dict[str, Any]
) -> dict[str, Any]:
    firehydrant_client = init_client()
    async with semaphore:
        return await firehydrant_client.enrich_incident_report_data(report)


## Enriches the services data
async def process_service_analytics(
    semaphore: asyncio.Semaphore, service: dict[str, Any]
) -> dict[str, Any]:
    firehydrant_client = init_client()
    async with semaphore:
        return await firehydrant_client.compute_service_mean_time_metrics(
            service.get("active_incidents", [])
        )


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
        semaphore = asyncio.Semaphore(5)
        tasks = [process_service_analytics(semaphore, service) for service in services]
        service_analytics = await asyncio.gather(*tasks)

        yield [
            {**service, "__incidentMetrics": metrics}
            for service, metrics in zip(services, service_analytics)
        ]


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
        tasks = [process_incident_tasks(semaphore, report) for report in reports]
        tasks_completion = await asyncio.gather(*tasks)

        yield [
            {**report, "__enrichedData": task}
            for report, task in zip(reports, tasks_completion)
        ]


@ocean.router.post("/webhook")
async def handle_firehydrant_webhook(webhook_data: dict[str, Any]) -> None:
    firehydrant_client = init_client()
    ## check for incident in the webhook data. Have a look at the sample webhook event payload https://firehydrant.com/docs/integration-guides/creating-webhooks/
    if "incident" in webhook_data.get("data", {}):
        incident_id = webhook_data.get("data", {}).get("incident", {}).get("id", "")
        incident_data = await firehydrant_client.get_single_incident(
            incident_id=incident_id
        )
        await ocean.register_raw(ObjectKind.INCIDENT, [incident_data])

    logger.info("Webhook event processed")


@ocean.on_start()
async def on_start() -> None:
    ## We are making the subscription of webhook optional. It will be triggered only when the user specifies the app_host variable
    if ocean.integration_config.get("app_host"):
        logger.info("Subscribing to Firehydrant webhooks")

        firehydrant_client = init_client()
        await firehydrant_client.create_webhooks_if_not_exists()

        logger.info("Subscribed to webhook incident events")
