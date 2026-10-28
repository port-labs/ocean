from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from datadog.client import DatadogClient
from datadog.core.exporters import CatalogEntityExporter
from datadog.core.exporters.base_exporter import MAX_PAGE_SIZE
from datadog.core.exporters.catalog_entity_exporter import (
    SCHEMA_ENRICHMENT_KEY,
    ListCatalogEntityOptions,
)

EMPTY_PAGE: dict[str, list[dict[str, Any]]] = {"data": []}


def entity(entity_id: str, kind: str, with_schema: bool = True) -> dict[str, Any]:
    """Shaped after a real /api/v2/catalog/entity response: the schema relationship
    carries the entity's own id, and the schema itself arrives in `included`."""
    return {
        "id": entity_id,
        "type": "entity",
        "attributes": {
            "kind": kind,
            "name": f"{kind}-{entity_id}",
            "namespace": "default",
        },
        **(
            {"relationships": {"schema": {"data": {"id": entity_id, "type": "schema"}}}}
            if with_schema
            else {}
        ),
    }


@pytest.mark.asyncio
async def test_get_catalog_entities_attaches_schemas(
    mock_datadog_client: DatadogClient,
) -> None:
    datastore_schema = {
        "apiVersion": "v3",
        "kind": "datastore",
        "metadata": {"name": "datastore-2"},
        "spec": {"tier": "3", "componentOf": ["system:checkout"]},
    }
    service_schema = {
        "apiVersion": "v3",
        "kind": "service",
        "metadata": {"name": "service-1"},
        "spec": {"dependsOn": ["datastore:orders-db"]},
    }
    page: dict[str, list[dict[str, Any]]] = {
        "data": [entity("1", "service"), entity("2", "datastore")],
        "included": [
            {"id": "1", "type": "schema", "attributes": {"schema": service_schema}},
            {"id": "2", "type": "schema", "attributes": {"schema": datastore_schema}},
            {"id": "3", "type": "rawSchema", "attributes": {"rawSchema": "eyJ9"}},
        ],
    }

    with patch.object(
        mock_datadog_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [page, EMPTY_PAGE]

        entities = []
        exporter = CatalogEntityExporter(mock_datadog_client)
        async for batch in exporter.get_paginated_resources(ListCatalogEntityOptions()):
            entities.extend(batch)

        assert [e[SCHEMA_ENRICHMENT_KEY] for e in entities] == [
            service_schema,
            datastore_schema,
        ]
        mock_request.assert_any_call(
            f"{mock_datadog_client.api_url}/api/v2/catalog/entity",
            params={
                "page[offset]": 0,
                "page[limit]": MAX_PAGE_SIZE,
                "include": "schema",
            },
        )


@pytest.mark.asyncio
async def test_get_catalog_entities_without_a_usable_schema(
    mock_datadog_client: DatadogClient,
) -> None:
    page: dict[str, list[dict[str, Any]]] = {
        "data": [
            entity("1", "datastore", with_schema=False),
            {
                "id": "2",
                "type": "entity",
                "attributes": {"kind": "queue", "name": "q"},
                "relationships": {},
            },
            {
                "id": "3",
                "type": "entity",
                "attributes": {"kind": "service", "name": "s"},
                "relationships": {"schema": {"data": None}},
            },
            entity("4", "api"),
        ],
        "included": [],
    }

    with patch.object(
        mock_datadog_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [page, EMPTY_PAGE]

        entities = []
        exporter = CatalogEntityExporter(mock_datadog_client)
        async for batch in exporter.get_paginated_resources(ListCatalogEntityOptions()):
            entities.extend(batch)

        assert len(entities) == 4
        assert all(SCHEMA_ENRICHMENT_KEY not in e for e in entities)


@pytest.mark.asyncio
async def test_get_catalog_entities_paginates_by_offset(
    mock_datadog_client: DatadogClient,
) -> None:
    first_page = {"data": [entity("1", "service", with_schema=False)]}
    second_page = {"data": [entity("2", "queue", with_schema=False)]}

    with patch.object(
        mock_datadog_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [first_page, second_page, EMPTY_PAGE]

        entities = []
        exporter = CatalogEntityExporter(mock_datadog_client)
        async for batch in exporter.get_paginated_resources(ListCatalogEntityOptions()):
            entities.extend(batch)

        assert len(entities) == 2
        assert mock_request.call_count == 3
        assert [
            call.kwargs["params"]["page[offset]"]
            for call in mock_request.call_args_list
        ] == [0, MAX_PAGE_SIZE, MAX_PAGE_SIZE * 2]


@pytest.mark.asyncio
async def test_get_catalog_entities_include_discovered(
    mock_datadog_client: DatadogClient,
) -> None:
    with patch.object(
        mock_datadog_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [EMPTY_PAGE]

        exporter = CatalogEntityExporter(mock_datadog_client)
        async for _ in exporter.get_paginated_resources(
            ListCatalogEntityOptions(include_discovered=True)
        ):
            pass

        assert mock_request.call_args.kwargs["params"]["includeDiscovered"] == "true"


@pytest.mark.asyncio
async def test_get_catalog_entities_filters_by_entity_kinds(
    mock_datadog_client: DatadogClient,
) -> None:
    page = {"data": [entity("1", "service", with_schema=False)]}

    with patch.object(
        mock_datadog_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [page, EMPTY_PAGE]

        exporter = CatalogEntityExporter(mock_datadog_client)
        async for _ in exporter.get_paginated_resources(
            ListCatalogEntityOptions(entity_kinds=["service", "datastore"])
        ):
            pass

        assert mock_request.call_count == 2
        assert all(
            call.kwargs["params"]["filter[kind]"] == ["service", "datastore"]
            for call in mock_request.call_args_list
        )


@pytest.mark.asyncio
async def test_get_catalog_entities_warns_for_kinds_that_returned_nothing(
    mock_datadog_client: DatadogClient,
) -> None:
    page = {
        "data": [entity("1", "service")],
        "included": [
            {"id": "1", "type": "schema", "attributes": {"schema": {"spec": {}}}}
        ],
    }

    with (
        patch.object(
            mock_datadog_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request,
        patch("datadog.core.exporters.catalog_entity_exporter.logger") as mock_logger,
    ):
        mock_request.side_effect = [page, EMPTY_PAGE]

        exporter = CatalogEntityExporter(mock_datadog_client)
        async for _ in exporter.get_paginated_resources(
            ListCatalogEntityOptions(entity_kinds=["service", "Datastore"])
        ):
            pass

        mock_logger.warning.assert_called_once()
        assert "['Datastore']" in mock_logger.warning.call_args.args[0]
