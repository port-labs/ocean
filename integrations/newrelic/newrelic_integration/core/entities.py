from typing import Optional, Any, AsyncIterable, Tuple

import httpx
from loguru import logger

from newrelic_integration.core.paging import send_paginated_graph_api_request
from newrelic_integration.core.utils import send_graph_api_request
from newrelic_integration.utils import (
    get_port_resource_configuration_by_port_kind,
    render_query,
)


class EntitiesHandler:
    @classmethod
    async def get_entity(
        cls, http_client: httpx.AsyncClient, entity_guid: str
    ) -> dict[Any, Any]:
        query_template = """
{
  actor {
    entity(guid: "{{ entity_guid }}") {
      entityType
      guid
      domain
      name
      permalink
      reporting
      tags {
        key
        values
      }
      type
    }
  }
}
        """

        query = await render_query(query_template, entity_guid=entity_guid)
        response = await send_graph_api_request(
            http_client, query=query, request_type="get_entity", entity_guid=entity_guid
        )
        entity = response.get("data", {}).get("actor", {}).get("entity", {})
        cls._format_tags(entity)
        return entity

    @classmethod
    async def list_entities_by_resource_kind(
        cls, http_client: httpx.AsyncClient, resource_kind: str
    ) -> AsyncIterable[dict[str, Any]]:
        query_template = """
{
  actor {
    entitySearch(query: "{{ entity_query_filter }}") {
      results{{ next_cursor_request }} {
        entities {
          entityType
          type
          tags {
            key
            values
          }
          reporting
          name
          lastReportingChangeAt
          guid
          domain
          accountId
          alertSeverity
          permalink
        }
        nextCursor
      }
    }
  }
}
    """
        resource_config = await get_port_resource_configuration_by_port_kind(
            resource_kind
        )
        entity_query_filter = resource_config.get("selector", {}).get(
            "entity_query_filter"
        )
        if not entity_query_filter:
            logger.error(
                "No entity_query_filter found for resource", resource_kind=resource_kind
            )

        async def extract_entities(
            response: dict[Any, Any]
        ) -> Tuple[Optional[str], list[dict[Any, Any]]]:
            results = (
                response.get("data", {})
                .get("actor", {})
                .get("entitySearch", {})
                .get("results", {})
            )
            return results.get("nextCursor"), results.get("entities", [])

        async for entity in send_paginated_graph_api_request(
            http_client,
            query_template,
            request_type="list_entities_by_resource_kind",
            extract_data=extract_entities,
            entity_query_filter=entity_query_filter,
        ):
            cls._format_tags(entity)
            yield entity

    @classmethod
    async def list_entities_by_guids(
        cls, http_client: httpx.AsyncClient, entity_guids: list[str]
    ) -> list[dict[Any, Any]]:
        # entities api doesn't support pagination
        query = """
{
    actor {
        entities(guids: {{ entity_guids }}) {
            entityType
            type
            tags {
                key
                values
            }
            reporting
            name
            lastReportingChangeAt
            guid
            domain
            accountId
            alertSeverity
            permalink
        }
    }
}
    """
        query = await render_query(query, entity_guids=entity_guids)
        response = await send_graph_api_request(
            http_client,
            query,
            request_type="list_entities_by_guids",
            entity_guids=entity_guids,
        )
        entities = response.get("data", {}).get("actor", {}).get("entities", [])
        for entity in entities:
            cls._format_tags(entity)
        return entities

    @staticmethod
    def _format_tags(entity: dict[Any, Any]) -> dict[Any, Any]:
        entity["tags"] = {tag["key"]: tag["values"] for tag in entity.get("tags", [])}
        return entity
