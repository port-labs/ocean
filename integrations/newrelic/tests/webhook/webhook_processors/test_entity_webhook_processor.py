from unittest.mock import AsyncMock, patch

import pytest
from port_ocean.context.event import event_context
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from newrelic_integration.overrides import (
    NewRelicCustomResourceConfig,
    NewRelicPortAppConfig,
)
from newrelic_integration.webhook.webhook_processors.entity_webhook_processor import (
    EntityWebhookProcessor,
)


@pytest.fixture
def processor(webhook_event: WebhookEvent) -> EntityWebhookProcessor:
    return EntityWebhookProcessor(webhook_event)


@pytest.mark.asyncio
async def test_get_matching_kinds(
    processor: EntityWebhookProcessor,
    port_app_config: NewRelicPortAppConfig,
    issue_payload: dict[str, object],
) -> None:
    async with event_context("test_event") as event:
        event.port_app_config = port_app_config
        kinds = await processor.get_matching_kinds(
            WebhookEvent(trace_id="test", payload=issue_payload, headers={})
        )
    assert kinds == ["newRelicService"]


@pytest.mark.asyncio
async def test_handle_event_returns_matching_entities(
    processor: EntityWebhookProcessor,
    entity_resource_config: NewRelicCustomResourceConfig,
    issue_payload: dict[str, object],
) -> None:
    entity = {"guid": "entity-guid-1", "type": "APM_APPLICATION", "name": "svc"}

    with patch(
        "newrelic_integration.webhook.webhook_processors.entity_webhook_processor.fetch_entities_for_resource",
        new_callable=AsyncMock,
        return_value=[entity],
    ) as mock_fetch:
        results = await processor.handle_event(issue_payload, entity_resource_config)

    mock_fetch.assert_awaited_once()
    assert results.updated_raw_results == [entity]
    assert results.deleted_raw_results == []


@pytest.mark.asyncio
async def test_handle_event_returns_empty_when_no_entities(
    processor: EntityWebhookProcessor,
    entity_resource_config: NewRelicCustomResourceConfig,
    issue_payload: dict[str, object],
) -> None:
    with patch(
        "newrelic_integration.webhook.webhook_processors.entity_webhook_processor.fetch_entities_for_resource",
        new_callable=AsyncMock,
        return_value=[],
    ):
        results = await processor.handle_event(issue_payload, entity_resource_config)

    assert results.updated_raw_results == []
    assert results.deleted_raw_results == []
