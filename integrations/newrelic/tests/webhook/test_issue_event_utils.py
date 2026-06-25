from unittest.mock import AsyncMock, patch

import httpx
import pytest

from newrelic_integration.overrides import (
    NewRelicCustomResourceConfig,
    NewRelicPortAppConfig,
    NewRelicSelector,
)
from newrelic_integration.webhook.issue_event_utils import (
    enrich_issue_entity_relations,
    fetch_entities_for_resource,
    get_entity_kinds,
    get_issue_kinds,
)
from tests.webhook.helpers import port_resource_config


@pytest.mark.asyncio
async def test_enrich_issue_entity_relations() -> None:
    issue_record: dict[str, object] = {"entityGuids": ["entity-guid-1"]}
    mock_http_client = AsyncMock(spec=httpx.AsyncClient)

    with patch(
        "newrelic_integration.webhook.issue_event_utils.EntitiesHandler"
    ) as mock_handler_cls:
        mock_handler = mock_handler_cls.return_value
        mock_handler.get_entity = AsyncMock(
            return_value={"type": "APM_APPLICATION", "guid": "entity-guid-1"}
        )
        await enrich_issue_entity_relations(mock_http_client, issue_record)

    relations = issue_record["__APM_APPLICATION"]
    assert isinstance(relations, dict)
    assert relations["entity_guids"] == ["entity-guid-1"]


@pytest.fixture
def entity_resource_config() -> NewRelicCustomResourceConfig:
    return NewRelicCustomResourceConfig(
        kind="newRelicService",
        selector=NewRelicSelector(
            query="true",
            newRelicTypes=["APM_APPLICATION"],
            entityQueryFilter="type = 'APM_APPLICATION'",
            calculateOpenIssueCount=True,
        ),
        port=port_resource_config(),
    )


@pytest.fixture
def port_app_config(
    entity_resource_config: NewRelicCustomResourceConfig,
) -> NewRelicPortAppConfig:
    return NewRelicPortAppConfig(resources=[entity_resource_config])


@pytest.mark.asyncio
async def test_fetch_entities_for_resource_filters_by_type(
    entity_resource_config: NewRelicCustomResourceConfig,
) -> None:
    mock_http_client = AsyncMock(spec=httpx.AsyncClient)

    with (
        patch(
            "newrelic_integration.webhook.issue_event_utils.EntitiesHandler"
        ) as mock_handler_cls,
        patch(
            "newrelic_integration.webhook.issue_event_utils.IssuesHandler"
        ) as mock_issues_cls,
    ):
        mock_handler = mock_handler_cls.return_value
        mock_handler.get_entity = AsyncMock(
            return_value={"type": "APM_APPLICATION", "guid": "entity-guid-1"}
        )
        mock_issues_cls.return_value.get_number_of_issues_by_entity_guid = AsyncMock(
            return_value=2
        )

        entities = await fetch_entities_for_resource(
            mock_http_client,
            entity_resource_config,
            ["entity-guid-1", "entity-guid-2"],
        )

    assert len(entities) == 2
    assert entities[0]["__open_issues_count"] == 2
    assert entities[1]["__open_issues_count"] == 2
    assert (
        mock_issues_cls.return_value.get_number_of_issues_by_entity_guid.await_count
        == 2
    )


@pytest.mark.asyncio
async def test_fetch_entities_for_resource_skips_non_matching_types() -> None:
    resource_config = NewRelicCustomResourceConfig(
        kind="newRelicService",
        selector=NewRelicSelector(
            query="true",
            newRelicTypes=["HOST"],
            entityQueryFilter="type = 'HOST'",
        ),
        port=port_resource_config(),
    )
    mock_http_client = AsyncMock(spec=httpx.AsyncClient)

    with patch(
        "newrelic_integration.webhook.issue_event_utils.EntitiesHandler"
    ) as mock_handler_cls:
        mock_handler = mock_handler_cls.return_value
        mock_handler.get_entity = AsyncMock(
            return_value={"type": "APM_APPLICATION", "guid": "entity-guid-1"}
        )

        entities = await fetch_entities_for_resource(
            mock_http_client,
            resource_config,
            ["entity-guid-1"],
        )

    assert entities == []


def test_get_issue_kinds_defaults_to_new_relic_alert() -> None:
    assert get_issue_kinds(NewRelicPortAppConfig(resources=[])) == ["newRelicAlert"]


def test_get_entity_kinds_excludes_resync_only_resources(
    port_app_config: NewRelicPortAppConfig,
) -> None:
    kinds = get_entity_kinds(port_app_config)
    assert kinds == ["newRelicService"]
