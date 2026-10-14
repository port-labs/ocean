from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest

from newrelic_integration.core.errors import NewRelicError, NewRelicNotFoundError
from newrelic_integration.core.service_dependencies import (
    ServiceDependenciesHandler,
    select_dependency,
)
from newrelic_integration.overrides import (
    NewRelicSelector,
    NewRelicServiceDependencyResourceConfig,
)
from newrelic_integration.webhook.constants import SERVICE_DEPENDENCY_KIND
from newrelic_integration.webhook.issue_event_utils import get_entity_kinds
from newrelic_integration.overrides import NewRelicPortAppConfig
from tests.webhook.helpers import port_resource_config

SERVICES = {
    "service-a": "SERVICE",
    "service-b": "APPLICATION",
    "external": "HTTPSERVICE",
}


def _edge(
    source_guid: str,
    target_guid: str,
    target_type: str,
    relationship_type: str = "CALLS",
) -> dict[str, Any]:
    return {
        "type": relationship_type,
        "source": {"guid": source_guid},
        "target": {
            "guid": target_guid,
            "entity": {"guid": target_guid, "name": target_guid, "type": target_type},
        },
    }


def test_select_dependency_call_keeps_outbound_service_target() -> None:
    edge = _edge("service-a", "service-b", "APPLICATION")
    assert select_dependency("service-a", edge, SERVICES) == "service-b"


@pytest.mark.parametrize(
    "edge",
    [
        _edge("service-b", "service-a", "SERVICE"),
        _edge("service-a", "external", "HTTPSERVICE"),
        _edge("service-a", "service-a", "SERVICE"),
        _edge("service-a", "missing", "SERVICE"),
        _edge("service-a", "service-b", "APPLICATION", relationship_type="HOSTS"),
    ],
)
def test_select_dependency_call_drops_edges_outside_the_map(
    edge: dict[str, Any],
) -> None:
    assert select_dependency("service-a", edge, SERVICES) is None


def _related_response(
    source_guid: str,
    edges: list[dict[str, Any]],
    next_cursor: str | None = None,
) -> dict[str, Any]:
    return {
        "data": {
            "actor": {
                "entity": {
                    "guid": source_guid,
                    "name": source_guid,
                    "type": "SERVICE",
                    "relatedEntities": {
                        "nextCursor": next_cursor,
                        "results": edges,
                    },
                }
            }
        }
    }


@pytest.mark.asyncio
async def test_outbound_call_guids_paginates_and_filters() -> None:
    handler = ServiceDependenciesHandler(AsyncMock())
    pages = [
        _related_response(
            "service-a",
            [
                _edge("service-a", "service-b", "APPLICATION"),
                _edge("service-a", "external", "HTTPSERVICE"),
            ],
            next_cursor="page-2",
        ),
        _related_response(
            "service-a",
            [
                _edge("service-a", "service-b", "APPLICATION"),
                _edge("service-b", "service-a", "SERVICE"),
            ],
        ),
    ]

    with (
        patch(
            "newrelic_integration.core.service_dependencies.render_query",
            new_callable=AsyncMock,
            return_value="query",
        ),
        patch(
            "newrelic_integration.core.service_dependencies.send_graph_api_request",
            new_callable=AsyncMock,
            side_effect=pages,
        ) as mock_send,
    ):
        calls = await handler.get_entity_dependencies("service-a", SERVICES)

    assert calls == ["service-b"]
    assert mock_send.await_count == 2


@pytest.mark.asyncio
async def test_outbound_call_guids_raises_on_graphql_error() -> None:
    handler = ServiceDependenciesHandler(AsyncMock())
    with (
        patch(
            "newrelic_integration.core.service_dependencies.render_query",
            new_callable=AsyncMock,
            return_value="query",
        ),
        patch(
            "newrelic_integration.core.service_dependencies.send_graph_api_request",
            new_callable=AsyncMock,
            return_value={"errors": [{"message": "complexity exceeded"}]},
        ),
        pytest.raises(NewRelicError, match="complexity exceeded"),
    ):
        await handler.get_entity_dependencies("service-a", SERVICES)


@pytest.mark.asyncio
async def test_outbound_call_guids_raises_when_entity_is_missing() -> None:
    handler = ServiceDependenciesHandler(AsyncMock())
    with (
        patch(
            "newrelic_integration.core.service_dependencies.render_query",
            new_callable=AsyncMock,
            return_value="query",
        ),
        patch(
            "newrelic_integration.core.service_dependencies.send_graph_api_request",
            new_callable=AsyncMock,
            return_value={"data": {"actor": {"entity": None}}},
        ),
        pytest.raises(NewRelicNotFoundError),
    ):
        await handler.get_entity_dependencies("service-a", SERVICES)


@pytest.mark.asyncio
async def test_list_service_dependencies_emits_services_with_empty_calls() -> None:
    handler = ServiceDependenciesHandler(AsyncMock())
    services = [
        {"guid": "service-a", "name": "payments", "type": "SERVICE"},
        {"guid": "service-b", "name": "billing", "type": "APPLICATION"},
    ]

    async def list_entities(_kind: str) -> AsyncIterator[dict[str, Any]]:
        for service in services:
            yield service

    config = NewRelicServiceDependencyResourceConfig(
        kind="newRelicServiceDependency",
        selector=NewRelicSelector(
            query="true",
            entityQueryFilter="type in ('SERVICE','APPLICATION')",
        ),
        port=port_resource_config(),
    )

    with (
        patch(
            "newrelic_integration.core.service_dependencies.get_port_resource_configuration_by_port_kind",
            new_callable=AsyncMock,
            return_value=config,
        ),
        patch.object(
            handler._entities,
            "list_entities_by_resource_kind",
            list_entities,
        ),
        patch.object(
            handler,
            "get_entity_dependencies",
            new_callable=AsyncMock,
            side_effect=[["service-b"], []],
        ),
    ):
        batches = [
            batch
            async for batch in handler.list_service_dependencies(
                SERVICE_DEPENDENCY_KIND
            )
        ]

    assert batches == [
        [
            {"guid": "service-a", "name": "payments", "calls": ["service-b"]},
            {"guid": "service-b", "name": "billing", "calls": []},
        ]
    ]


def test_get_entity_kinds_excludes_service_dependency() -> None:
    app_config = NewRelicPortAppConfig(
        resources=[
            NewRelicServiceDependencyResourceConfig(
                kind="newRelicServiceDependency",
                selector=NewRelicSelector(
                    query="true",
                    entityQueryFilter="type in ('SERVICE','APPLICATION')",
                ),
                port=port_resource_config(),
            )
        ]
    )
    assert get_entity_kinds(app_config) == []
