from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from datadog.client import DatadogClient
from datadog.core.exporters import CatalogEntityExporter
from datadog.core.exporters.base_exporter import (
    CHANGED_RESOURCES_FETCH_BATCH_SIZE,
    MAX_PAGE_SIZE,
)
from datadog.core.exporters.catalog_entity_exporter import (
    SCHEMA_ENRICHMENT_KEY,
    ListCatalogEntityOptions,
)
from datadog.incremental import CHANGED_CATALOG_ENTITIES_AUDIT_QUERY

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


AUDIT_SEARCH_URL = "https://api.datadoghq.com/api/v2/audit/events/search"
ENTITIES_URL = "https://api.datadoghq.com/api/v2/catalog/entity"
SINCE = datetime(2026, 11, 5, 10, 0, tzinfo=timezone.utc)


def _audit_event(ref: str) -> dict[str, Any]:
    # Shaped after a real event: the asset ID is the entity reference
    return {
        "id": f"event-{ref}",
        "attributes": {"attributes": {"asset": {"id": ref, "type": "idp_entity"}}},
    }


def _audit_page(*events: dict[str, Any], after: str | None = None) -> dict[str, Any]:
    return {"data": list(events), "meta": {"page": {"after": after} if after else {}}}


def _entity_page(entity_id: str, kind: str = "service") -> dict[str, Any]:
    return {
        "data": [entity(entity_id, kind)],
        "included": [{"id": entity_id, "type": "schema", "attributes": {"schema": {}}}],
    }


async def _collect_changed(
    exporter: CatalogEntityExporter,
    options: ListCatalogEntityOptions = ListCatalogEntityOptions(),
) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    async for batch in exporter.get_changed_entities(options, incremental_cursor=SINCE):
        entities.extend(batch)
    return entities


@pytest.mark.asyncio
async def test_get_changed_entities_searches_audit_events_since_cursor(
    mock_datadog_client: DatadogClient,
) -> None:
    with patch.object(
        mock_datadog_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = _audit_page()

        assert await _collect_changed(CatalogEntityExporter(mock_datadog_client)) == []

        mock_request.assert_called_once_with(
            AUDIT_SEARCH_URL,
            json_data={
                "filter": {
                    "query": CHANGED_CATALOG_ENTITIES_AUDIT_QUERY,
                    "from": "2026-11-05T10:00:00+00:00",
                    "to": "now",
                },
                "sort": "-timestamp",
                "page": {"limit": MAX_PAGE_SIZE},
            },
            method="POST",
        )


@pytest.mark.asyncio
async def test_get_changed_entities_fetches_each_ref_once_with_schema(
    mock_datadog_client: DatadogClient,
) -> None:
    with patch.object(
        mock_datadog_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [
            _audit_page(
                _audit_event("service:default/a"),
                _audit_event("service:default/a"),
                _audit_event("datastore:default/b"),
            ),
            _entity_page("1"),
            _entity_page("2", kind="datastore"),
        ]

        entities = await _collect_changed(CatalogEntityExporter(mock_datadog_client))

        assert [e["id"] for e in entities] == ["1", "2"]
        assert all(SCHEMA_ENRICHMENT_KEY in e for e in entities)
        # Datadog ignores unknown filters and returns every entity, so pin the name
        assert mock_request.call_args_list[1].args == (ENTITIES_URL,)
        assert mock_request.call_args_list[1].kwargs == {
            "params": {"include": "schema", "filter[ref]": "service:default/a"}
        }
        assert mock_request.call_args_list[2].kwargs["params"]["filter[ref]"] == (
            "datastore:default/b"
        )


@pytest.mark.asyncio
async def test_get_changed_entities_yields_one_batch_per_concurrent_fetch(
    mock_datadog_client: DatadogClient,
) -> None:
    entity_ids = [str(i) for i in range(CHANGED_RESOURCES_FETCH_BATCH_SIZE + 1)]

    async def respond(
        url: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        method: str = "GET",
    ) -> dict[str, Any]:
        if json_data is not None:
            return _audit_page(
                *(_audit_event(f"service:default/{i}") for i in entity_ids)
            )
        assert params is not None
        return _entity_page(params["filter[ref]"].rpartition("/")[2])

    with patch.object(
        mock_datadog_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = respond

        batches = [
            batch
            async for batch in CatalogEntityExporter(
                mock_datadog_client
            ).get_changed_entities(ListCatalogEntityOptions(), incremental_cursor=SINCE)
        ]

    assert [len(batch) for batch in batches] == [CHANGED_RESOURCES_FETCH_BATCH_SIZE, 1]
    assert [e["id"] for batch in batches for e in batch] == entity_ids


@pytest.mark.asyncio
async def test_get_changed_entities_keeps_selector_filters(
    mock_datadog_client: DatadogClient,
) -> None:
    with patch.object(
        mock_datadog_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [
            _audit_page(_audit_event("service:default/a")),
            _entity_page("1"),
        ]

        await _collect_changed(
            CatalogEntityExporter(mock_datadog_client),
            ListCatalogEntityOptions(
                include_discovered=True, entity_kinds=["service", "api"]
            ),
        )

        assert mock_request.call_args_list[1].kwargs["params"] == {
            "include": "schema",
            "includeDiscovered": "true",
            "filter[kind]": ["service", "api"],
            "filter[ref]": "service:default/a",
        }


@pytest.mark.asyncio
async def test_get_changed_entities_skips_refs_that_return_nothing(
    mock_datadog_client: DatadogClient,
) -> None:
    """A deleted entity, or one of a kind outside ``entity_kinds``, comes back empty."""
    with patch.object(
        mock_datadog_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [
            _audit_page(
                _audit_event("service:default/gone"), _audit_event("service:default/b")
            ),
            EMPTY_PAGE,
            _entity_page("2"),
        ]

        entities = await _collect_changed(CatalogEntityExporter(mock_datadog_client))

        assert [e["id"] for e in entities] == ["2"]
