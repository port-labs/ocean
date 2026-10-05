import json
from typing import Optional, Any, AsyncIterable, Tuple, Dict

import httpx
from loguru import logger

from port_ocean.utils import http_async_client

from newrelic_integration.core.paging import send_paginated_graph_api_request
from newrelic_integration.core.query_templates.entities import (
    LIST_ENTITIES_WITH_FILTER_QUERY,
    LIST_ENTITIES_BY_GUIDS_QUERY,
    LIST_ENTITIES_RELATED_ENTITIES_BY_GUIDS_QUERY,
    LIST_ENTITY_RELATED_ENTITIES_QUERY,
    GET_ENTITY_BY_GUID_QUERY,
)
from newrelic_integration.core.utils import send_graph_api_request, format_tags
from newrelic_integration.utils import (
    get_port_resource_configuration_by_port_kind,
    render_query,
)
from newrelic_integration.core.errors import NewRelicNotFoundError


class EntitiesHandler:
    RELATED_ENTITIES_BATCH_SIZE = 25
    SERVICE_TARGET_TYPES = {"SERVICE", "APPLICATION"}
    SERVICE_TARGET_DOMAINS = {"APM"}

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
        # entities api doesn't support pagination
        query = await render_query(
            LIST_ENTITIES_BY_GUIDS_QUERY, entity_guids=json.dumps(entity_guids)
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

    async def list_service_call_relations_for_entities(
        self, entity_guids: list[str]
    ) -> dict[str, dict[str, Any]]:
        relations_by_entity_guid: dict[str, dict[str, Any]] = {}

        for guid_batch in self._chunk_entity_guids(entity_guids):
            query = await render_query(
                LIST_ENTITIES_RELATED_ENTITIES_BY_GUIDS_QUERY,
                entity_guids=json.dumps(guid_batch),
            )
            response = await send_graph_api_request(
                self.http_client,
                query,
                request_type="list_service_call_relations_for_entities",
                entity_guids=guid_batch,
            )
            entities = response.get("data", {}).get("actor", {}).get("entities", [])
            for entity in entities:
                source_entity_guid = entity.get("guid")
                if not source_entity_guid:
                    continue
                accumulator = self._get_relation_accumulator(
                    relations_by_entity_guid, source_entity_guid
                )
                self._accumulate_related_entities(
                    source_entity_guid=source_entity_guid,
                    related_entities=entity.get("relatedEntities", {}).get(
                        "results", []
                    ),
                    accumulator=accumulator,
                )

                next_cursor = entity.get("relatedEntities", {}).get("nextCursor")
                while next_cursor:
                    cursor_response = await self._fetch_entity_related_entities_page(
                        source_entity_guid=source_entity_guid,
                        next_cursor=next_cursor,
                    )
                    related_entities = (
                        cursor_response.get("data", {})
                        .get("actor", {})
                        .get("entity", {})
                        .get("relatedEntities", {})
                    )
                    self._accumulate_related_entities(
                        source_entity_guid=source_entity_guid,
                        related_entities=related_entities.get("results", []),
                        accumulator=accumulator,
                    )
                    next_cursor = related_entities.get("nextCursor")

        return {
            guid: {
                "depends_on": sorted(data["depends_on"]),
                "calls": sorted(data["calls"]),
                "call_targets": list(data["call_targets"].values()),
            }
            for guid, data in relations_by_entity_guid.items()
        }

    async def list_service_call_relations_for_entity(
        self, entity_guid: str
    ) -> dict[str, Any]:
        relations = await self.list_service_call_relations_for_entities([entity_guid])
        return relations.get(
            entity_guid,
            {"depends_on": [], "calls": [], "call_targets": []},
        )

    @staticmethod
    def _format_tags(entity: dict[Any, Any]) -> dict[Any, Any]:
        entity["tags"] = {tag["key"]: tag["values"] for tag in entity.get("tags", [])}
        return entity

    @classmethod
    def _chunk_entity_guids(cls, entity_guids: list[str]) -> list[list[str]]:
        return [
            entity_guids[index : index + cls.RELATED_ENTITIES_BATCH_SIZE]
            for index in range(0, len(entity_guids), cls.RELATED_ENTITIES_BATCH_SIZE)
        ]

    async def _fetch_entity_related_entities_page(
        self, source_entity_guid: str, next_cursor: str
    ) -> dict[str, Any]:
        query = await render_query(
            LIST_ENTITY_RELATED_ENTITIES_QUERY,
            entity_guid=source_entity_guid,
            next_cursor_request=f', cursor: "{next_cursor}"',
        )
        return await send_graph_api_request(
            self.http_client,
            query=query,
            request_type="list_service_call_relations_for_entity_cursor",
            entity_guid=source_entity_guid,
            next_cursor=next_cursor,
        )

    @classmethod
    def _get_relation_accumulator(
        cls,
        relations_by_entity_guid: dict[str, dict[str, Any]],
        source_entity_guid: str,
    ) -> dict[str, Any]:
        if source_entity_guid not in relations_by_entity_guid:
            relations_by_entity_guid[source_entity_guid] = {
                "depends_on": set(),
                "calls": set(),
                "call_targets": {},
            }
        return relations_by_entity_guid[source_entity_guid]

    @classmethod
    def _accumulate_related_entities(
        cls,
        source_entity_guid: str,
        related_entities: list[dict[str, Any]],
        accumulator: dict[str, Any],
    ) -> None:
        for related_entity in related_entities:
            if related_entity.get("type") != "CALLS":
                continue

            edge_source_guid = (
                related_entity.get("source", {}).get("entity", {}).get("guid")
            )
            if edge_source_guid != source_entity_guid:
                continue

            target = related_entity.get("target", {}).get("entity", {})
            target_guid = target.get("guid")
            target_type = target.get("type")
            target_domain = target.get("domain")
            if not target_guid or not target_type:
                continue
            if target_guid == source_entity_guid:
                continue

            if (
                target_type in cls.SERVICE_TARGET_TYPES
                and target_domain in cls.SERVICE_TARGET_DOMAINS
            ):
                accumulator["depends_on"].add(target_guid)
                continue

            accumulator["calls"].add(target_guid)
            accumulator["call_targets"][target_guid] = cls._normalize_dependency_target(
                related_entity
            )

    @staticmethod
    def _normalize_dependency_target(related_entity: dict[str, Any]) -> dict[str, Any]:
        target = related_entity.get("target", {}).get("entity", {})
        format_tags(target)
        return {
            "guid": target.get("guid"),
            "name": target.get("name"),
            "type": target.get("type"),
            "domain": target.get("domain"),
            "entityType": target.get("entityType"),
            "accountId": target.get("accountId")
            or related_entity.get("target", {}).get("accountId"),
            "reporting": target.get("reporting"),
            "permalink": target.get("permalink"),
            "tags": target.get("tags", {}),
            "relationshipType": related_entity.get("type"),
            "createdAt": related_entity.get("createdAt"),
        }
