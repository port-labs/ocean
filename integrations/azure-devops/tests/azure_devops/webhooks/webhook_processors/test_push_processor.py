import pytest
from unittest.mock import MagicMock
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from azure_devops.webhooks.webhook_processors.push_processor import PushWebhookProcessor


@pytest.fixture
def push_processor(
    event: WebhookEvent, monkeypatch: pytest.MonkeyPatch
) -> PushWebhookProcessor:
    mock_client = MagicMock()
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.push_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )
    return PushWebhookProcessor(event)


@pytest.mark.asyncio
async def test_push_should_process_event(
    push_processor: PushWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "eventType": "git.push",
            "publisherId": "tfs",
            "resource": {"url": "http://example.com"},
        },
        headers={},
    )
    assert await push_processor.should_process_event(event) is True

    event.payload["eventType"] = "wrong.event"
    assert await push_processor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_push_get_matching_kinds(
    push_processor: PushWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    kinds = await push_processor.get_matching_kinds(event)
    assert "repository" in kinds


@pytest.mark.asyncio
async def test_push_validate_payload(
    push_processor: PushWebhookProcessor,
    mock_event_context: None,
) -> None:
    valid_payload = {
        "eventType": "git.push",
        "publisherId": "tfs",
        "resource": {"url": "http://example.com"},
    }
    assert await push_processor.validate_payload(valid_payload) is True

    invalid_payload = {"missing": "fields"}
    assert await push_processor.validate_payload(invalid_payload) is False
