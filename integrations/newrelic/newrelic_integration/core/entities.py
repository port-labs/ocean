from typing import Optional, Any, AsyncIterable, Tuple, Dict

import httpx
from loguru import logger

from port_ocean.utils import http_async_client

from newrelic_integration.core.paging import send_paginated_graph_api_request
from newrelic_integration.core.query_templates.entities import (
    LIST_ENTITIES_WITH_FILTER_QUERY,
    LIST_ENTITIES_BY_GUIDS_QUERY,
    GET_ENTITY_BY_GUID_QUERY,
)
from newrelic_integration.core.utils import send_graph_api_request, format_tags
from newrelic_integration.utils import (
    get_port_resource_configuration_by_port_kind,
    render_query,
)
from newrelic_integration.core.errors import NewRelicNotFoundError


def build_entity_search_query_for_guids(
    entity_guids: list[str],
    entity_query_filter: str,
) -> str | None:
    unique_guids = list(dict.fromkeys(guid for guid in entity_guids if guid))
    if not unique_guids:
        return None

    guid_list = ", ".join(f"'{guid}'" for guid in unique_guids)
    return f"id IN ({guid_list}) AND ({entity_query_filter})"


class EntitiesHandler:
    def __init__(self, http_client: httpx.AsyncClient | None = None):
        self.http_client = http_client or http_async_client

    async def get_entity(self, entity_guid: str) -> dict[Any, Any]:
        query = await render_query(GET_ENTITY_BY_GUID_QUERY, entity_guid=entity_guid)
        response = await send_graph_api_request(
            self.http_client,
            query=query,
            request_type="get_entity",
            entity_guid=entity_guid,
        )
        entity = response.get("data", {}).get("actor", {}).get("entity", {})
        if not entity:
            raise NewRelicNotFoundError(
                f"No entity found in newrelic for guid {entity_guid}",
            )
        format_tags(entity)
        return entity

    async def list_entities_by_resource_kind(
        self, resource_kind: str
    ) -> AsyncIterable[dict[str, Any]]:
        resource_config = await get_port_resource_configuration_by_port_kind(
            resource_kind
        )
        if not resource_config:
            logger.error(
                "No resource configuration found for resource",
                resource_kind=resource_kind,
            )
            return

        if not resource_config.selector.entity_query_filter:
            logger.error(
                "No entity_query_filter found for resource", resource_kind=resource_kind
            )

        async def extract_entities(
            response: Optional[Dict[str, Any]] = None
        ) -> Tuple[Optional[str], list[Dict[str, Any]]]:
            if not response:
                return None, []

            results = (
                response.get("data", {})
                .get("actor", {})
                .get("entitySearch", {})
                .get("results", {})
            )

            return (results.get("nextCursor"), results.get("entities", []))

        async for entity in send_paginated_graph_api_request(
            self.http_client,
            LIST_ENTITIES_WITH_FILTER_QUERY,
            request_type="list_entities_by_resource_kind",
            extract_data=extract_entities,
            entity_query_filter=resource_config.selector.entity_query_filter,
            extra_entity_properties=resource_config.selector.entity_extra_properties_query,
        ):

            if entity:
                self._format_tags(entity)
                yield entity

    async def list_entities_by_guids(
        self, entity_guids: list[str]
    ) -> list[dict[Any, Any]]:
        if not entity_guids:
            return []

        # entities api doesn't support pagination
        query = await render_query(
            LIST_ENTITIES_BY_GUIDS_QUERY, entity_guids=entity_guids
        )
        response = await send_graph_api_request(
            self.http_client,
            query,
            request_type="list_entities_by_guids",
            entity_guids=entity_guids,
        )
        entities = response.get("data", {}).get("actor", {}).get("entities", [])
        for entity in entities:
            format_tags(entity)
        return entities

    async def list_entities_by_guids_and_filter(
        self,
        entity_guids: list[str],
        entity_query_filter: str,
        extra_entity_properties: str | None = None,
    ) -> list[dict[Any, Any]]:
        combined_query_filter = build_entity_search_query_for_guids(
            entity_guids,
            entity_query_filter,
        )
        if combined_query_filter is None:
            return []

        async def extract_entities(
            response: Optional[Dict[str, Any]] = None,
        ) -> Tuple[Optional[str], list[Dict[str, Any]]]:
            if not response:
                return None, []

            results = (
                response.get("data", {})
                .get("actor", {})
                .get("entitySearch", {})
                .get("results", {})
            )
            return results.get("nextCursor"), results.get("entities", [])

        entities: list[dict[Any, Any]] = []
        async for entity in send_paginated_graph_api_request(
            self.http_client,
            LIST_ENTITIES_WITH_FILTER_QUERY,
            request_type="list_entities_by_guids_and_filter",
            extract_data=extract_entities,
            entity_query_filter=combined_query_filter,
            extra_entity_properties=extra_entity_properties or "",
        ):
            if entity:
                self._format_tags(entity)
                entities.append(entity)

        return entities

    @staticmethod
    def _format_tags(entity: dict[Any, Any]) -> dict[Any, Any]:
        entity["tags"] = {tag["key"]: tag["values"] for tag in entity.get("tags", [])}
        return entity
