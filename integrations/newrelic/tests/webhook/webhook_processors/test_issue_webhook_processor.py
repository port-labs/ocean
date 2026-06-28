from unittest.mock import AsyncMock, patch

import pytest
from port_ocean.context.event import event_context
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from newrelic_integration.overrides import (
    NewRelicAlertResourceConfig,
    NewRelicPortAppConfig,
)
from newrelic_integration.webhook.webhook_processors.issue_webhook_processor import (
    IssueWebhookProcessor,
)


@pytest.fixture
def processor(webhook_event: WebhookEvent) -> IssueWebhookProcessor:
    return IssueWebhookProcessor(webhook_event)


@pytest.mark.asyncio
async def test_should_process_event_valid(
    processor: IssueWebhookProcessor,
    issue_payload: dict[str, object],
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload=issue_payload,
        headers={},
    )
    assert await processor.should_process_event(event) is True


@pytest.mark.asyncio
async def test_should_process_event_invalid(processor: IssueWebhookProcessor) -> None:
    event = WebhookEvent(trace_id="test", payload={"foo": "bar"}, headers={})
    assert await processor.should_process_event(event) is False


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [[], "not-an-object"])
async def test_should_process_event_rejects_non_object_payload(
    processor: IssueWebhookProcessor,
    payload: list[object] | str,
) -> None:
    event = WebhookEvent(trace_id="test", payload=payload, headers={})  # type: ignore[arg-type]
    assert await processor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_get_matching_kinds(
    processor: IssueWebhookProcessor,
    port_app_config: NewRelicPortAppConfig,
    issue_payload: dict[str, object],
) -> None:
    async with event_context("test_event") as event:
        event.port_app_config = port_app_config
        kinds = await processor.get_matching_kinds(
            WebhookEvent(trace_id="test", payload=issue_payload, headers={})
        )
    assert kinds == ["newRelicAlert"]


@pytest.mark.asyncio
async def test_handle_event_enriches_issue(
    processor: IssueWebhookProcessor,
    alert_resource_config: NewRelicAlertResourceConfig,
    issue_payload: dict[str, object],
) -> None:
    with patch(
        "newrelic_integration.webhook.webhook_processors.issue_webhook_processor.enrich_issue_entity_relations",
        new_callable=AsyncMock,
    ) as mock_enrich:
        results = await processor.handle_event(issue_payload, alert_resource_config)

    mock_enrich.assert_awaited_once()
    assert len(results.updated_raw_results) == 1
    assert results.updated_raw_results[0]["issueId"] == "issue-1"
    assert results.deleted_raw_results == []


@pytest.mark.asyncio
async def test_handle_event_still_syncs_issue_when_enrichment_fails(
    processor: IssueWebhookProcessor,
    alert_resource_config: NewRelicAlertResourceConfig,
    issue_payload: dict[str, object],
) -> None:
    with patch(
        "newrelic_integration.webhook.issue_event_utils.EntitiesHandler"
    ) as mock_handler_cls:
        mock_handler = mock_handler_cls.return_value
        mock_handler.list_entities_by_guids = AsyncMock(
            side_effect=RuntimeError("GraphQL unavailable")
        )
        results = await processor.handle_event(issue_payload, alert_resource_config)

    assert len(results.updated_raw_results) == 1
    assert results.updated_raw_results[0]["issueId"] == "issue-1"
    assert results.deleted_raw_results == []
