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

logger.warning(ocean.integration_config)
def init_client() -> FirehydrantClient:
    return FirehydrantClient(
        ocean.integration_config["api_url"],
        ocean.integration_config["token"],
        ocean.integration_config.get("app_host")
    )

async def process_incident_tasks(
    semaphore: asyncio.Semaphore, report: dict[str, Any]
) -> dict[str, Any]:
    firehydrant_client = init_client()
    async with semaphore:
        return await firehydrant_client.enrich_incident_report_data(report)

async def process_service_analytics(
    semaphore: asyncio.Semaphore, service: dict[str, Any]
) -> dict[str, Any]:
    firehydrant_client = init_client()
    async with semaphore:
        return await firehydrant_client.compute_service_mean_time_metrics(service.get("active_incidents", []))

@ocean.on_resync(ObjectKind.ENVIRONMENT)
async def on_retrospective_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    firehydrant_client = init_client()

    async for environments in firehydrant_client.get_paginated_resource(resource_type=ObjectKind.ENVIRONMENT):
        logger.debug(
            f"Received batch with {len(environments)} environments"
        )
        yield environments

@ocean.on_resync(ObjectKind.SERVICE)
async def on_retrospective_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    firehydrant_client = init_client()

    async for services in firehydrant_client.get_paginated_resource(resource_type=ObjectKind.SERVICE):
        logger.debug(
            f"Received batch with {len(services)} services"
        )
        semaphore = asyncio.Semaphore(5)
        tasks = [process_service_analytics(semaphore, service) for service in services]
        service_analytics = await asyncio.gather(*tasks)
        
        yield [
            {**service, "__incidentMetrics": metrics} for service, metrics in zip(services, service_analytics)
        ]

@ocean.on_resync(ObjectKind.INCIDENT)
async def on_retrospective_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    firehydrant_client = init_client()

    async for incidents in firehydrant_client.get_paginated_resource(resource_type=ObjectKind.INCIDENT):
        logger.debug(
            f"Received batch with {len(incidents)} incidents"
        )
        yield incidents


@ocean.on_resync(ObjectKind.RETROSPECTIVE)
async def on_retrospective_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    firehydrant_client = init_client()

    async for reports in firehydrant_client.get_paginated_resource(ObjectKind.RETROSPECTIVE):
        logger.debug(
            f"Received batch with {len(reports)} reports, getting their tasks completion status"
        )
        semaphore = asyncio.Semaphore(5)
        tasks = [process_incident_tasks(semaphore, report) for report in reports]
        tasks_completion = await asyncio.gather(*tasks)
        
        yield [
            {**report, "__enrichedData": task} for report, task in zip(reports, tasks_completion)
        ]


# Optional
# Listen to the start event of the integration. Called once when the integration starts.
@ocean.on_start()
async def on_start() -> None:
    # Something to do when the integration starts
    # For example create a client to query 3rd party services - GitHub, Jira, etc...
    logger.info("Starting integration")
