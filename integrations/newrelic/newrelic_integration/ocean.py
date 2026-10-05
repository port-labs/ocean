from typing import Any
import asyncio
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from newrelic_integration.core.entities import EntitiesHandler
from newrelic_integration.core.issues import IssuesHandler, IssueState
from newrelic_integration.webhook.registry import register_live_events_webhooks
from newrelic_integration.core.service_levels import ServiceLevelsHandler
from newrelic_integration.core.alert_conditions import AlertConditionsHandler

from newrelic_integration.utils import get_port_resource_configuration_by_port_kind

SERVICE_LEVEL_MAX_CONCURRENT_REQUESTS = 10
SERVICE_DEPENDENCIES_PAGE_SIZE = 100


async def enrich_service_level(
    handler: ServiceLevelsHandler,
    semaphore: asyncio.Semaphore,
    service_level: dict[str, Any],
) -> dict[str, Any]:
    async with semaphore:
        return await handler.enrich_slo_with_sli_and_tags(service_level)


async def enrich_service_call_relations(
    entity_handler: EntitiesHandler,
    entities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    relation_data = await entity_handler.list_service_call_relations_for_entities(
        [entity["guid"] for entity in entities if entity.get("guid")]
    )
    for entity in entities:
        relations = relation_data.get(entity.get("guid", ""), {})
        entity["__depends_on"] = relations.get("depends_on", [])
        entity["__calls"] = relations.get("calls", [])
    return entities


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
            page_size = 100
            counter = 0
            entities = []
            entities_handler = EntitiesHandler()
            include_service_dependencies = (
                port_resource_configuration.selector.include_service_dependencies
            )
            async for entity in entities_handler.list_entities_by_resource_kind(kind):
                if port_resource_configuration.selector.calculate_open_issue_count:
                    number_of_open_issues = (
                        await IssuesHandler().get_number_of_issues_by_entity_guid(
                            entity["guid"],
                            issue_state=IssueState.ACTIVATED,
                        )
                    )
                    entity["__open_issues_count"] = number_of_open_issues
                counter += 1
                entities.append(entity)
                # yield the entities in batches to take advantage of the async list generator
                if counter == page_size:
                    counter = 0
                    if include_service_dependencies:
                        entities = await enrich_service_call_relations(
                            entities_handler,
                            entities,
                        )
                    yield entities
                    entities = []
            if entities:
                if include_service_dependencies:
                    entities = await enrich_service_call_relations(
                        entities_handler,
                        entities,
                    )
                yield entities


@ocean.on_resync(kind="newRelicAlert")
async def resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    with logger.contextualize(resource_kind=kind):
        yield await IssuesHandler().list_issues()


@ocean.on_resync(kind="newRelicServiceLevel")
async def resync_service_levels(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    with logger.contextualize(resource_kind=kind):
        service_level_handler = ServiceLevelsHandler()
        semaphore = asyncio.Semaphore(SERVICE_LEVEL_MAX_CONCURRENT_REQUESTS)

        async for service_levels in service_level_handler.list_service_levels():
            tasks = [
                enrich_service_level(service_level_handler, semaphore, service_level)
                for service_level in service_levels
            ]
            enriched_service_levels = await asyncio.gather(*tasks)
            yield enriched_service_levels


@ocean.on_resync(kind="newRelicDependency")
async def resync_service_dependencies(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    with logger.contextualize(resource_kind=kind):
        service_resource_config = await get_port_resource_configuration_by_port_kind(
            "newRelicService"
        )
        if not service_resource_config:
            logger.error("No newRelicService resource configuration found")
            return
        if not service_resource_config.selector.include_service_dependencies:
            logger.info(
                "Skipping dependency resync because includeServiceDependencies is disabled"
            )
            return

        entities_handler = EntitiesHandler()
        dependency_entities: dict[str, dict[str, Any]] = {}
        source_batch: list[dict[str, Any]] = []
        service_counter = 0

        async for entity in entities_handler.list_entities_by_resource_kind(
            "newRelicService"
        ):
            source_batch.append(entity)
            service_counter += 1
            if service_counter == SERVICE_DEPENDENCIES_PAGE_SIZE:
                relation_data = (
                    await entities_handler.list_service_call_relations_for_entities(
                        [
                            service["guid"]
                            for service in source_batch
                            if service.get("guid")
                        ]
                    )
                )
                for relations in relation_data.values():
                    for target in relations.get("call_targets", []):
                        guid = target.get("guid")
                        if guid:
                            dependency_entities[guid] = target
                source_batch = []
                service_counter = 0

        if source_batch:
            relation_data = (
                await entities_handler.list_service_call_relations_for_entities(
                    [service["guid"] for service in source_batch if service.get("guid")]
                )
            )
            for relations in relation_data.values():
                for target in relations.get("call_targets", []):
                    guid = target.get("guid")
                    if guid:
                        dependency_entities[guid] = target

        dependencies = list(dependency_entities.values())
        for index in range(0, len(dependencies), SERVICE_DEPENDENCIES_PAGE_SIZE):
            yield dependencies[index : index + SERVICE_DEPENDENCIES_PAGE_SIZE]


@ocean.on_resync(kind="newRelicAlertCondition")
async def resync_alert_conditions(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    with logger.contextualize(resource_kind=kind):
        alert_conditions_handler = AlertConditionsHandler()
        page_size = 100
        counter = 0
        conditions = []
        async for condition in alert_conditions_handler.list_alert_conditions():
            counter += 1
            conditions.append(condition)
            # yield the conditions in batches to take advantage of the async list generator
            if counter == page_size:
                counter = 0
                yield conditions
                conditions = []
        if conditions:
            yield conditions


register_live_events_webhooks()
