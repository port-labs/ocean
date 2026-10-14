import asyncio
import json
from collections.abc import Mapping
from itertools import batched
from typing import Any, AsyncIterable

import httpx
from loguru import logger
from port_ocean.utils import http_async_client

from newrelic_integration.core.entities import EntitiesHandler
from newrelic_integration.core.errors import NewRelicError, NewRelicNotFoundError
from newrelic_integration.core.query_templates.service_dependencies import (
    RELATED_ENTITIES_QUERY,
)
from newrelic_integration.core.utils import render_query, send_graph_api_request
from newrelic_integration.utils import get_port_resource_configuration_by_port_kind

SERVICE_DEPENDENCY_ENTITY_TYPES = frozenset({"SERVICE", "APPLICATION"})
CALLS_RELATIONSHIP = "CALLS"
RELATED_ENTITIES_PAGE_LIMIT = 200
MAX_RELATIONSHIP_PAGES = 100
MAX_CONCURRENT_RELATIONSHIP_REQUESTS = 10
DEPENDENCY_BATCH_SIZE = 100


def select_dependency(
    source_guid: str,
    edge: dict[str, Any],
    services_by_guid: Mapping[str, str | None],
) -> str | None:
    """Keep a CALLS edge whose target is a service from the same search."""
    if edge.get("type") != CALLS_RELATIONSHIP:
        return None

    source = edge.get("source") or {}
    if source.get("guid") != source_guid:
        return None

    target = edge.get("target") or {}
    target_entity = target.get("entity") or {}
    target_guid = target_entity.get("guid") or target.get("guid")
    if (
        not isinstance(target_guid, str)
        or not target_guid
        or target_guid == source_guid
    ):
        return None
    if target_guid not in services_by_guid:
        return None

    known_type = services_by_guid.get(target_guid)
    edge_type = target_entity.get("type")
    if known_type not in SERVICE_DEPENDENCY_ENTITY_TYPES:
        return None
    if edge_type and edge_type not in SERVICE_DEPENDENCY_ENTITY_TYPES:
        return None
    return target_guid


class ServiceDependenciesHandler:
    def __init__(self, http_client: httpx.AsyncClient | None = None):
        self.http_client = http_client or http_async_client
        self._entities = EntitiesHandler(self.http_client)

    async def list_service_dependencies(
        self, resource_kind: str
    ) -> AsyncIterable[list[dict[str, Any]]]:
        resource_config = await get_port_resource_configuration_by_port_kind(
            resource_kind
        )
        if resource_config is None or not resource_config.selector.entity_query_filter:
            raise NewRelicError(
                "newRelicServiceDependency requires selector.entityQueryFilter"
            )

        services: list[dict[str, Any]] = []
        async for entity in self._entities.list_entities_by_resource_kind(
            resource_kind
        ):
            if entity.get("guid"):
                services.append(entity)

        services_by_guid = {entity["guid"]: entity.get("type") for entity in services}
        logger.info(
            "Fetching dependencies for New Relic services",
            service_count=len(services),
        )

        batch: list[dict[str, Any]] = []
        for chunk in batched(services, MAX_CONCURRENT_RELATIONSHIP_REQUESTS):
            records = await asyncio.gather(
                *[self._dependency_record(entity, services_by_guid) for entity in chunk]
            )
            for record in records:
                batch.append(record)
                if len(batch) == DEPENDENCY_BATCH_SIZE:
                    yield batch
                    batch = []
        if batch:
            yield batch

    async def _dependency_record(
        self,
        entity: dict[str, Any],
        services_by_guid: Mapping[str, str | None],
    ) -> dict[str, Any]:
        calls = await self.get_entity_dependencies(entity["guid"], services_by_guid)
        return {
            "guid": entity["guid"],
            "name": entity.get("name"),
            "calls": calls,
        }

    async def get_entity_dependencies(
        self,
        source_guid: str,
        services_by_guid: Mapping[str, str | None],
    ) -> list[str]:
        dependencies: list[str] = []
        cursor: str | None = None
        seen_cursors: set[str] = set()

        for _ in range(MAX_RELATIONSHIP_PAGES):
            response = await self._fetch_related_entities(source_guid, cursor)
            entity = (response.get("data") or {}).get("actor", {}).get("entity")
            if not entity:
                raise NewRelicNotFoundError(
                    f"No entity found in New Relic for guid {source_guid}"
                )

            related = entity.get("relatedEntities") or {}
            for edge in related.get("results") or []:
                target_guid = select_dependency(source_guid, edge, services_by_guid)
                if target_guid and target_guid not in dependencies:
                    dependencies.append(target_guid)

            next_cursor = related.get("nextCursor")
            if not next_cursor or next_cursor in seen_cursors:
                return dependencies
            seen_cursors.add(next_cursor)
            cursor = next_cursor

        raise NewRelicError(
            f"Exceeded {MAX_RELATIONSHIP_PAGES} relatedEntities pages for guid {source_guid}"
        )

    async def _fetch_related_entities(
        self, source_guid: str, cursor: str | None
    ) -> dict[str, Any]:
        filter_args = (
            "filter: {direction: OUTBOUND, relationshipTypes: {include: [CALLS]}}, "
            f"limit: {RELATED_ENTITIES_PAGE_LIMIT}"
        )
        if cursor:
            related_entities_args = f"cursor: {json.dumps(cursor)}, {filter_args}"
        else:
            related_entities_args = filter_args

        query = await render_query(
            RELATED_ENTITIES_QUERY,
            entity_guid=json.dumps(source_guid),
            related_entities_args=related_entities_args,
        )
        response = await send_graph_api_request(
            self.http_client,
            query,
            request_type="list_service_dependencies",
            entity_guid=source_guid,
        )
        if not response:
            raise NewRelicError(
                f"Empty relatedEntities response for guid {source_guid}"
            )
        errors = response.get("errors")
        if errors:
            raise NewRelicError(
                f"New Relic GraphQL error while loading dependencies for guid {source_guid}: {errors}"
            )
        return response
