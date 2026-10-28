from typing import TYPE_CHECKING, Any

from loguru import logger

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from datadog.core.exporters.base_exporter import ListOptions, PaginatedExporter

if TYPE_CHECKING:
    from datadog.overrides import CatalogEntityResourceConfig

SCHEMA_ENRICHMENT_KEY = "__schema"


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
        schema_relation = entity.get("relationships", {}).get("schema")
        if schema_relation:
            entity[SCHEMA_ENRICHMENT_KEY] = schemas[schema_relation["data"]["id"]]

    without_schema = [e["id"] for e in entities if SCHEMA_ENRICHMENT_KEY not in e]
    if without_schema:
        logger.warning(
            f"{len(without_schema)} of {len(entities)} catalog entities carry no schema; "
            f"their spec properties and declared relations will be empty: {without_schema[:5]}"
        )

    return entities


class CatalogEntityExporter(PaginatedExporter[ListCatalogEntityOptions]):
    async def get_paginated_resources(
        self, options: ListCatalogEntityOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get Software Catalog entities from Datadog. Without `entity_kinds` every
        kind — service, datastore, queue, api, system and the rest — is returned.
        Docs: https://docs.datadoghq.com/api/latest/software-catalog/#get-a-list-of-entities
        """
        url = f"{self.client.api_url}/api/v2/catalog/entity"
        # `include` takes exactly one value: "schema,relation" returns includeCount 0
        params: dict[str, Any] = {"include": "schema"}
        if options.include_discovered:
            params["includeDiscovered"] = "true"
        if options.entity_kinds:
            params["filter[kind]"] = options.entity_kinds

        pending_kinds = set(options.entity_kinds)
        async for response in self._paginate_responses_by_offset(
            url,
            offset_param="page[offset]",
            size_param="page[limit]",
            extra_params=params,
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
