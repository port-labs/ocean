from unittest.mock import AsyncMock, patch

import pytest
from port_ocean.context.event import event_context
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from newrelic_integration.overrides import (
    NewRelicAlertResourceConfig,
    NewRelicCustomResourceConfig,
    NewRelicPortAppConfig,
    NewRelicSelector,
)
from newrelic_integration.webhook.webhook_processors.entity_webhook_processor import (
    EntityWebhookProcessor,
)
from newrelic_integration.webhook.webhook_processors.issue_webhook_processor import (
    IssueWebhookProcessor,
)


def _port_resource_config() -> PortResourceConfig:
    return PortResourceConfig(
        entity=MappingsConfig(
            mappings=EntityMapping(
                identifier=".guid",
                title=".name",
                blueprint="newRelicService",
                properties={},
            )
        )
    )


def _issue_payload() -> dict[str, object]:
    return {
        "issueId": "issue-1",
        "title": ["High error rate"],
        "state": "ACTIVATED",
        "entityGuids": ["entity-guid-1"],
    }


def _issue_event(payload: dict[str, object] | None = None) -> WebhookEvent:
    return WebhookEvent(
        trace_id="test-trace-id",
        payload=payload or _issue_payload(),
        headers={},
    )


def _entity_resource_config() -> NewRelicCustomResourceConfig:
    return NewRelicCustomResourceConfig(
        kind="newRelicService",
        selector=NewRelicSelector(
            query="true",
            newRelicTypes=["APM_APPLICATION"],
            entityQueryFilter="type = 'APM_APPLICATION'",
            calculateOpenIssueCount=True,
        ),
        port=_port_resource_config(),
    )


def _alert_resource_config() -> NewRelicAlertResourceConfig:
    return NewRelicAlertResourceConfig(
        kind="newRelicAlert",
        selector=NewRelicSelector(query="true"),
        port=_port_resource_config(),
    )


def _port_app_config() -> NewRelicPortAppConfig:
    return NewRelicPortAppConfig(
        resources=[_alert_resource_config(), _entity_resource_config()]
    )


@pytest.fixture
def mock_port_app_config() -> NewRelicPortAppConfig:
    return _port_app_config()


@pytest.mark.asyncio
class TestIssueWebhookProcessor:
    async def test_should_process_event_valid(self) -> None:
        processor = IssueWebhookProcessor(_issue_event())
        assert await processor.should_process_event(_issue_event()) is True

    async def test_should_process_event_invalid(self) -> None:
        processor = IssueWebhookProcessor(_issue_event())
        event = WebhookEvent(trace_id="test", payload={"foo": "bar"}, headers={})
        assert await processor.should_process_event(event) is False

    async def test_get_matching_kinds(
        self, mock_port_app_config: NewRelicPortAppConfig
    ) -> None:
        processor = IssueWebhookProcessor(_issue_event())
        async with event_context("test_event") as event:
            event.port_app_config = mock_port_app_config
            kinds = await processor.get_matching_kinds(_issue_event())
        assert kinds == ["newRelicAlert"]

    async def test_handle_event_enriches_issue(self) -> None:
        processor = IssueWebhookProcessor(_issue_event())
        payload = _issue_payload()

        with patch(
            "newrelic_integration.webhook.webhook_processors.issue_webhook_processor.enrich_issue_entity_relations",
            new_callable=AsyncMock,
        ) as mock_enrich:
            results = await processor.handle_event(payload, _alert_resource_config())

        mock_enrich.assert_awaited_once()
        assert len(results.updated_raw_results) == 1
        assert results.updated_raw_results[0]["issueId"] == "issue-1"
        assert results.deleted_raw_results == []


@pytest.mark.asyncio
class TestEntityWebhookProcessor:
    async def test_get_matching_kinds(
        self, mock_port_app_config: NewRelicPortAppConfig
    ) -> None:
        processor = EntityWebhookProcessor(_issue_event())
        async with event_context("test_event") as event:
            event.port_app_config = mock_port_app_config
            kinds = await processor.get_matching_kinds(_issue_event())
        assert kinds == ["newRelicService"]

    async def test_handle_event_returns_matching_entities(self) -> None:
        processor = EntityWebhookProcessor(_issue_event())
        payload = _issue_payload()
        entity = {"guid": "entity-guid-1", "type": "APM_APPLICATION", "name": "svc"}

        with patch(
            "newrelic_integration.webhook.webhook_processors.entity_webhook_processor.fetch_entities_for_resource",
            new_callable=AsyncMock,
            return_value=[entity],
        ) as mock_fetch:
            results = await processor.handle_event(payload, _entity_resource_config())

        mock_fetch.assert_awaited_once()
        assert results.updated_raw_results == [entity]
        assert results.deleted_raw_results == []

    async def test_handle_event_returns_empty_when_no_entities(self) -> None:
        processor = EntityWebhookProcessor(_issue_event())

        with patch(
            "newrelic_integration.webhook.webhook_processors.entity_webhook_processor.fetch_entities_for_resource",
            new_callable=AsyncMock,
            return_value=[],
        ):
            results = await processor.handle_event(
                _issue_payload(), _entity_resource_config()
            )

        assert results.updated_raw_results == []
        assert results.deleted_raw_results == []
