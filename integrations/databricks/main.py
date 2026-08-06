from typing import cast

import httpx
from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from clients.auth import MissingIntegrationCredentialException
from clients.databricks import DatabricksClient
from consts import WEBHOOK_INVOKE_PATH
from integration import (
    CatalogResourceConfig,
    JobResourceConfig,
    JobRunResourceConfig,
    SchemaResourceConfig,
    TableResourceConfig,
)
from kinds import Kinds
from webhook_processors.job_runs import JobRunWebhookProcessor


@ocean.on_resync(Kinds.CLUSTERS)
async def on_clusters_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = DatabricksClient.from_ocean_configuration()
    async for clusters in client.get_clusters():
        logger.info(f"Received batch with {len(clusters)} clusters")
        yield clusters


@ocean.on_resync(Kinds.JOBS)
async def on_jobs_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = DatabricksClient.from_ocean_configuration()
    selector = cast(JobResourceConfig, event.resource_config).selector

    async for jobs in client.get_jobs(expand_tasks=selector.expand_tasks):
        logger.info(f"Received batch with {len(jobs)} jobs")
        yield jobs


@ocean.on_resync(Kinds.JOB_RUNS)
async def on_job_runs_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = DatabricksClient.from_ocean_configuration()
    selector = cast(JobRunResourceConfig, event.resource_config).selector

    async for runs in client.get_job_runs(completed_only=selector.completed_only):
        logger.info(f"Received batch with {len(runs)} job runs")
        yield runs


@ocean.on_resync(Kinds.PIPELINES)
async def on_pipelines_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = DatabricksClient.from_ocean_configuration()
    async for pipelines in client.get_pipelines():
        logger.info(f"Received batch with {len(pipelines)} pipelines")
        yield pipelines


@ocean.on_resync(Kinds.SQL_WAREHOUSES)
async def on_sql_warehouses_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = DatabricksClient.from_ocean_configuration()
    async for warehouses in client.get_sql_warehouses():
        logger.info(f"Received batch with {len(warehouses)} sql warehouses")
        yield warehouses


@ocean.on_resync(Kinds.CATALOGS)
async def on_catalogs_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = DatabricksClient.from_ocean_configuration()
    selector = cast(CatalogResourceConfig, event.resource_config).selector

    async for catalogs in client.get_all_catalogs(catalog_names=selector.catalog_names):
        logger.info(f"Received batch with {len(catalogs)} catalogs")
        yield catalogs


@ocean.on_resync(Kinds.SCHEMAS)
async def on_schemas_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = DatabricksClient.from_ocean_configuration()
    selector = cast(SchemaResourceConfig, event.resource_config).selector

    async for schemas in client.get_all_schemas(catalog_names=selector.catalog_names):
        logger.info(f"Received batch with {len(schemas)} schemas")
        yield schemas


@ocean.on_resync(Kinds.TABLES)
async def on_tables_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = DatabricksClient.from_ocean_configuration()
    selector = cast(TableResourceConfig, event.resource_config).selector

    async for tables in client.get_all_tables(catalog_names=selector.catalog_names):
        logger.info(f"Received batch with {len(tables)} tables")
        yield tables


@ocean.on_start()
async def on_start() -> None:
    try:
        client = DatabricksClient.from_ocean_configuration()
    except MissingIntegrationCredentialException as e:
        logger.error(
            f"Databricks integration is misconfigured, skipping webhook setup: {e}"
        )
        return

    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    base_url = ocean.app.base_url
    if not base_url:
        logger.warning(
            "No base URL configured (OCEAN__BASE_URL), skipping webhook destination "
            "creation. Without it, job run updates will only be reflected on the next "
            "resync instead of in real time."
        )
        return

    invoke_url = f"{base_url.rstrip('/')}{WEBHOOK_INVOKE_PATH}"
    logger.info("Registering Databricks webhook notification destination")
    try:
        await client.create_webhook_destination_if_not_exists(invoke_url)
    except (httpx.HTTPStatusError, httpx.HTTPError) as e:
        logger.error(
            f"Failed to register Databricks webhook notification destination, "
            f"continuing without live job run updates: {e}"
        )


ocean.add_webhook_processor("/webhook", JobRunWebhookProcessor)
