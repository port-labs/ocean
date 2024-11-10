from typing import Any
import httpx
import asyncio
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from newrelic_integration.core.entities import EntitiesHandler
from newrelic_integration.core.issues import IssuesHandler, IssueState, IssueEvent
from newrelic_integration.core.service_levels import ServiceLevelsHandler

from newrelic_integration.utils import (
    get_port_resource_configuration_by_newrelic_entity_type,
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


@ocean.router.post("/events")
async def handle_issues_events(issue: IssueEvent) -> dict[str, bool]:
    with logger.contextualize(issue_id=issue.id, issue_state=issue.state):
        logger.info(
            "Received issue event",
        )
        issue_record = issue.dict(by_alias=True)
        async with httpx.AsyncClient() as http_client:
            for entity_guid in issue_record["entityGuids"]:
                try:
                    entity = await EntitiesHandler(http_client).get_entity(
                        entity_guid=entity_guid
                    )
                    entity_type = entity["type"]
                    entity_resource_config = (
                        await get_port_resource_configuration_by_newrelic_entity_type(
                            entity_type
                        )
                    )
                    if not entity_resource_config:
                        logger.warning(
                            "Received issue event for unknown entity type, ignoring",
                            entity_type=entity_type,
                        )
                    else:
                        if entity_resource_config.selector.calculate_open_issue_count:
                            number_of_open_issues = await IssuesHandler(
                                http_client
                            ).get_number_of_issues_by_entity_guid(
                                entity_guid,
                                issue_state=IssueState.ACTIVATED,
                            )
                            entity["__open_issues_count"] = number_of_open_issues
                        # add the entity guid to the right relation key in the issue
                        # by the format of .__<type>.entity_guids.[<entity_guid>...]
                        issue_record.setdefault(
                            f"__{entity_type}",
                            {},
                        ).setdefault(
                            "entity_guids", []
                        ).append(entity_guid)
                        await ocean.register_raw(entity_resource_config.kind, [entity])
                except Exception as err:
                    logger.exception(
                        "Failed to get entity for issue event, continuing",
                        entity_guid=entity_guid,
                        err=str(err),
                    )
        issue_resource_config = (
            await get_port_resource_configuration_by_newrelic_entity_type("ISSUE")
        )
        # get the port issue kind from the resource configuration if exists, otherwise use default kind newRelicAlert
        port_issue_kind = getattr(issue_resource_config, "kind", "") or "newRelicAlert"
        await ocean.register_raw(port_issue_kind, [issue_record])
        return {"ok": True}
