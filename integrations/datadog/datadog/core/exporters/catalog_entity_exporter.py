import asyncio
from datetime import datetime
from itertools import batched
from typing import TYPE_CHECKING, Any

from loguru import logger

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from datadog.core.exporters.base_exporter import ListOptions, PaginatedExporter
from datadog.incremental import CHANGED_CATALOG_ENTITIES_AUDIT_QUERY

if TYPE_CHECKING:
    from datadog.overrides import CatalogEntityResourceConfig

SCHEMA_ENRICHMENT_KEY = "__schema"
CHANGED_ENTITIES_FETCH_BATCH_SIZE = 10


class ListCatalogEntityOptions(ListOptions["CatalogEntityResourceConfig"]):
    include_discovered: bool = False
    entity_kinds: list[str] = []

    @classmethod
    def from_resource_config(
        cls, resource_config: "CatalogEntityResourceConfig"
    ) -> "ListCatalogEntityOptions":
        return cls(
            include_discovered=resource_config.selector.include_discovered,
            entity_kinds=resource_config.selector.entity_kinds,
        )


def _entity_params(options: ListCatalogEntityOptions) -> dict[str, Any]:
    """Query parameters shared by the full and the incremental resync, so entities
    keep one shape."""
    params: dict[str, Any] = {"include": "schema"}
    if options.include_discovered:
        params["includeDiscovered"] = "true"
    if options.entity_kinds:
        params["filter[kind]"] = options.entity_kinds
    return params


def attach_schemas(response: dict[str, Any]) -> list[dict[str, Any]]:
    """An entity's spec — tier, lifecycle, languages and its declared relations — is not
    on the entity itself but in the sibling `included` array, keyed by the id under the
    entity's `schema` relationship."""
    schemas = {
        included["id"]: included["attributes"]["schema"]
        for included in response.get("included", [])
        if included["type"] == "schema"
    }

    entities: list[dict[str, Any]] = response["data"]
    for entity in entities:
        schema_relation = entity.get("relationships", {}).get("schema") or {}
        schema_id = (schema_relation.get("data") or {}).get("id")
        if schema_id in schemas:
            entity[SCHEMA_ENRICHMENT_KEY] = schemas[schema_id]

    without_schema = [e["id"] for e in entities if SCHEMA_ENRICHMENT_KEY not in e]
    if without_schema:
        logger.warning(
            f"{len(without_schema)} of {len(entities)} catalog entities carry no schema; "
            f"their spec properties and declared relations will be empty: {without_schema[:5]}"
        )

    return entities


class CatalogEntityExporter(PaginatedExporter[ListCatalogEntityOptions]):
    @property
    def _entities_url(self) -> str:
        return f"{self.client.api_url}/api/v2/catalog/entity"

    async def get_paginated_resources(
        self, options: ListCatalogEntityOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get Software Catalog entities from Datadog. Without `entity_kinds` every
        kind — service, datastore, queue, api, system and the rest — is returned.
        Docs: https://docs.datadoghq.com/api/latest/software-catalog/#get-a-list-of-entities
        """
        pending_kinds = set(options.entity_kinds)
        async for response in self._paginate_responses_by_offset(
            self._entities_url,
            offset_param="page[offset]",
            size_param="page[limit]",
            extra_params=_entity_params(options),
        ):
            entities = attach_schemas(response)
            if pending_kinds:
                pending_kinds -= {entity["attributes"]["kind"] for entity in entities}
            yield entities

        if pending_kinds:
            logger.warning(
                f"No catalog entities returned for kinds {sorted(pending_kinds)}; Datadog "
                "matches kind names exactly and returns an empty page for one it does not know"
            )

    async def get_changed_entities(
        self, options: ListCatalogEntityOptions, incremental_cursor: datetime
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get catalog entities created or modified since ``incremental_cursor``, found
        through audit events. Deleted entities, and entities of kinds outside
        ``entity_kinds``, are not returned. Discovered entities have no audit events,
        so only a full resync picks up newly discovered ones.
        Docs: https://docs.datadoghq.com/api/latest/audit/#search-audit-logs-events
        """
        refs = await self._changed_asset_ids(
            CHANGED_CATALOG_ENTITIES_AUDIT_QUERY, incremental_cursor
        )

        for batch in batched(refs, CHANGED_ENTITIES_FETCH_BATCH_SIZE):
            results = await asyncio.gather(
                *(self._get_changed_entity(ref, options) for ref in batch)
            )
            if entities := [entity for entity in results if entity]:
                yield entities

    async def _get_changed_entity(
        self, ref: str, options: ListCatalogEntityOptions
    ) -> dict[str, Any] | None:
        """Get an entity found through audit events, or None if it was deleted since
        or its kind is filtered out."""
        response = await self.client.send_api_request(
            self._entities_url,
            params={**_entity_params(options), "filter[ref]": ref},
        )
        if not response.get("data"):
            logger.warning(
                f"Skipping catalog entity '{ref}' from audit events; it no longer exists in Datadog"
            )
            return None
        return attach_schemas(response)[0]
