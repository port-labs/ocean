from typing import Any
import httpx
import asyncio
from loguru import logger
from newrelic_integration.webhook.webhook_manager import NewRelicWebhookManager
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from newrelic_integration.core.entities import EntitiesHandler
from newrelic_integration.core.issues import IssuesHandler, IssueState
from newrelic_integration.core.service_levels import ServiceLevelsHandler
from newrelic_integration.webhook.processors.issue_webhook_processor import (
    IssueWebhookProcessor,
)

from newrelic_integration.utils import (
    get_port_resource_configuration_by_port_kind,
)

SERVICE_LEVEL_MAX_CONCURRENT_REQUESTS = 10


async def enrich_service_level(
    handler: ServiceLevelsHandler,
    semaphore: asyncio.Semaphore,
    service_level: dict[str, Any],
) -> dict[str, Any]:
    async with semaphore:
        return await handler.enrich_slo_with_sli_and_tags(service_level)


@ocean.on_resync()
async def resync_entities(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    with logger.contextualize(resource_kind=kind):
        port_resource_configuration = (
            await get_port_resource_configuration_by_port_kind(kind)
        )
        if not port_resource_configuration:
            logger.error(
                "No resource configuration found for resource",
                resource_kind=kind,
            )
            return
        # mainly for issues newRelicAlert as it has different resync logic than entities
        if not port_resource_configuration.selector.entity_query_filter:
            logger.info(
                f"Skipping resync for kind without entity_query_filter, kind: {kind}",
            )
            return
        else:
            async with httpx.AsyncClient() as http_client:
                page_size = 100
                counter = 0
                entities = []
                async for entity in EntitiesHandler(
                    http_client
                ).list_entities_by_resource_kind(kind):
                    if port_resource_configuration.selector.calculate_open_issue_count:
                        number_of_open_issues = await IssuesHandler(
                            http_client
                        ).get_number_of_issues_by_entity_guid(
                            entity["guid"],
                            issue_state=IssueState.ACTIVATED,
                        )
                        entity["__open_issues_count"] = number_of_open_issues
                    counter += 1
                    entities.append(entity)
                    # yield the entities in batches to take advantage of the async list generator
                    if counter == page_size:
                        counter = 0
                        yield entities
                        entities = []
                if entities:
                    yield entities


@ocean.on_resync(kind="newRelicAlert")
async def resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    with logger.contextualize(resource_kind=kind):
        async with httpx.AsyncClient() as http_client:
            yield await IssuesHandler(http_client).list_issues()


@ocean.on_resync(kind="newRelicServiceLevel")
async def resync_service_levels(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    with logger.contextualize(resource_kind=kind):
        async with httpx.AsyncClient() as http_client:
            service_level_handler = ServiceLevelsHandler(http_client)
            semaphore = asyncio.Semaphore(SERVICE_LEVEL_MAX_CONCURRENT_REQUESTS)

            async for service_levels in service_level_handler.list_service_levels():
                tasks = [
                    enrich_service_level(
                        service_level_handler, semaphore, service_level
                    )
                    for service_level in service_levels
                ]
                enriched_service_levels = await asyncio.gather(*tasks)
                yield enriched_service_levels


@ocean.on_start()
async def on_start() -> None:
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    async with httpx.AsyncClient() as http_client:
        webhook_manager = NewRelicWebhookManager(http_client)
        await webhook_manager.ensure_webhook_exists()


ocean.add_webhook_processor("/webhook", IssueWebhookProcessor)
