from unittest.mock import AsyncMock, patch

import pytest
from port_ocean.context.event import event_context

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
async def test_enrich_issue_entity_relations(
    port_app_config: NewRelicPortAppConfig,
) -> None:
    issue_record: dict[str, object] = {"entityGuids": ["entity-guid-1"]}

    with patch(
        "newrelic_integration.webhook.issue_event_utils.EntitiesHandler"
    ) as mock_handler_cls:
        mock_handler = mock_handler_cls.return_value
        mock_handler.get_entity = AsyncMock(
            return_value={"type": "APM_APPLICATION", "guid": "entity-guid-1"}
        )
        async with event_context("test_event") as event:
            event.port_app_config = port_app_config
            await enrich_issue_entity_relations(issue_record)

    mock_handler.get_entity.assert_awaited_once_with(entity_guid="entity-guid-1")
    relations = issue_record["__APM_APPLICATION"]
    assert isinstance(relations, dict)
    assert relations["entity_guids"] == ["entity-guid-1"]


@pytest.mark.asyncio
async def test_enrich_issue_entity_relations_skips_unknown_entity_type(
    port_app_config: NewRelicPortAppConfig,
) -> None:
    issue_record: dict[str, object] = {"entityGuids": ["entity-guid-1"]}

    with patch(
        "newrelic_integration.webhook.issue_event_utils.EntitiesHandler"
    ) as mock_handler_cls:
        mock_handler = mock_handler_cls.return_value
        mock_handler.get_entity = AsyncMock(
            return_value={"type": "HOST", "guid": "entity-guid-1"}
        )
        async with event_context("test_event") as event:
            event.port_app_config = port_app_config
            await enrich_issue_entity_relations(issue_record)

    assert "__HOST" not in issue_record


@pytest.mark.asyncio
async def test_enrich_issue_entity_relations_continues_on_fetch_failure() -> None:
    issue_record: dict[str, object] = {
        "issueId": "issue-1",
        "entityGuids": ["entity-guid-1"],
    }

    with patch(
        "newrelic_integration.webhook.issue_event_utils.EntitiesHandler"
    ) as mock_handler_cls:
        mock_handler = mock_handler_cls.return_value
        mock_handler.get_entity = AsyncMock(
            side_effect=RuntimeError("GraphQL unavailable")
        )
        await enrich_issue_entity_relations(issue_record)

    assert issue_record["issueId"] == "issue-1"
    assert "__APM_APPLICATION" not in issue_record


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
        mock_handler.get_entity = AsyncMock(
            side_effect=[
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

    assert mock_handler.get_entity.await_count == 2
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
        mock_handler.get_entity = AsyncMock(
            return_value={"type": "APM_APPLICATION", "guid": "entity-guid-1"}
        )

        entities = await fetch_entities_for_resource(
            resource_config,
            ["entity-guid-1"],
        )

    assert entities == []


@pytest.mark.asyncio
async def test_fetch_entities_for_resource_includes_entities_without_newrelic_types() -> (
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
        mock_handler.get_entity = AsyncMock(
            side_effect=[
                {"type": "AWSEC2INSTANCE", "guid": "entity-guid-1"},
                RuntimeError("Entity not found"),
            ]
        )

        entities = await fetch_entities_for_resource(
            resource_config,
            ["entity-guid-1", "entity-guid-2"],
        )

    assert entities == [{"type": "AWSEC2INSTANCE", "guid": "entity-guid-1"}]


def test_get_issue_kinds_defaults_to_new_relic_alert() -> None:
    assert get_issue_kinds(NewRelicPortAppConfig(resources=[])) == ["newRelicAlert"]


def test_get_entity_kinds_excludes_resync_only_resources(
    port_app_config: NewRelicPortAppConfig,
) -> None:
    kinds = get_entity_kinds(port_app_config)
    assert kinds == ["newRelicService"]
