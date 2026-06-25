import asyncio
from unittest.mock import AsyncMock, patch

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
    get_issue_event_entities,
    get_issue_kinds,
)
from tests.webhook.helpers import port_resource_config


@pytest.mark.asyncio
async def test_enrich_issue_entity_relations() -> None:
    issue_record: dict[str, object] = {"entityGuids": ["entity-guid-1"]}

    with patch(
        "newrelic_integration.webhook.issue_event_utils.EntitiesHandler"
    ) as mock_handler_cls:
        mock_handler = mock_handler_cls.return_value
        mock_handler.list_entities_by_guids = AsyncMock(
            return_value=[{"type": "APM_APPLICATION", "guid": "entity-guid-1"}]
        )
        await enrich_issue_entity_relations(issue_record)

    mock_handler.list_entities_by_guids.assert_awaited_once_with(["entity-guid-1"])
    relations = issue_record["__APM_APPLICATION"]
    assert isinstance(relations, dict)
    assert relations["entity_guids"] == ["entity-guid-1"]


@pytest.mark.asyncio
async def test_get_issue_event_entities_deduplicates_concurrent_fetches() -> None:
    with patch(
        "newrelic_integration.webhook.issue_event_utils.EntitiesHandler"
    ) as mock_handler_cls:
        mock_handler = mock_handler_cls.return_value
        mock_handler.list_entities_by_guids = AsyncMock(
            return_value=[{"type": "APM_APPLICATION", "guid": "entity-guid-1"}]
        )

        first_fetch, second_fetch = await asyncio.gather(
            get_issue_event_entities(["entity-guid-1"]),
            get_issue_event_entities(["entity-guid-1"]),
        )

    mock_handler.list_entities_by_guids.assert_awaited_once_with(["entity-guid-1"])
    assert first_fetch == second_fetch == {
        "entity-guid-1": {"type": "APM_APPLICATION", "guid": "entity-guid-1"}
    }


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
    with (
        patch(
            "newrelic_integration.webhook.issue_event_utils.EntitiesHandler"
        ) as mock_handler_cls,
        patch(
            "newrelic_integration.webhook.issue_event_utils.IssuesHandler"
        ) as mock_issues_cls,
    ):
        mock_handler = mock_handler_cls.return_value
        mock_handler.list_entities_by_guids_and_filter = AsyncMock(
            return_value=[
                {"type": "APM_APPLICATION", "guid": "entity-guid-1"},
                {"type": "APM_APPLICATION", "guid": "entity-guid-2"},
            ]
        )
        mock_issues_cls.return_value.get_number_of_issues_by_entity_guid = AsyncMock(
            return_value=2
        )

        entities = await fetch_entities_for_resource(
            entity_resource_config,
            ["entity-guid-1", "entity-guid-2"],
        )

    mock_handler.list_entities_by_guids_and_filter.assert_awaited_once_with(
        ["entity-guid-1", "entity-guid-2"],
        "type = 'APM_APPLICATION'",
        None,
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

    with patch(
        "newrelic_integration.webhook.issue_event_utils.EntitiesHandler"
    ) as mock_handler_cls:
        mock_handler = mock_handler_cls.return_value
        mock_handler.list_entities_by_guids_and_filter = AsyncMock(return_value=[])

        entities = await fetch_entities_for_resource(
            resource_config,
            ["entity-guid-1"],
        )

    assert entities == []


@pytest.mark.asyncio
async def test_fetch_entities_for_resource_uses_entity_query_filter_without_newrelic_types() -> (
    None
):
    resource_config = NewRelicCustomResourceConfig(
        kind="entity",
        selector=NewRelicSelector(
            query="true",
            entityQueryFilter="type IN ('AWSEC2INSTANCE')",
        ),
        port=port_resource_config(),
    )

    with patch(
        "newrelic_integration.webhook.issue_event_utils.EntitiesHandler"
    ) as mock_handler_cls:
        mock_handler = mock_handler_cls.return_value
        mock_handler.list_entities_by_guids_and_filter = AsyncMock(
            return_value=[{"type": "AWSEC2INSTANCE", "guid": "entity-guid-1"}]
        )

        entities = await fetch_entities_for_resource(
            resource_config,
            ["entity-guid-1", "entity-guid-2"],
        )

    mock_handler.list_entities_by_guids_and_filter.assert_awaited_once_with(
        ["entity-guid-1", "entity-guid-2"],
        "type IN ('AWSEC2INSTANCE')",
        None,
    )
    assert entities == [{"type": "AWSEC2INSTANCE", "guid": "entity-guid-1"}]


def test_get_issue_kinds_defaults_to_new_relic_alert() -> None:
    assert get_issue_kinds(NewRelicPortAppConfig(resources=[])) == ["newRelicAlert"]


def test_get_entity_kinds_excludes_resync_only_resources(
    port_app_config: NewRelicPortAppConfig,
) -> None:
    kinds = get_entity_kinds(port_app_config)
    assert kinds == ["newRelicService"]
