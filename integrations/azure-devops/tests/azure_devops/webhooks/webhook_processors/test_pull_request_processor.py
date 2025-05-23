import pytest
from unittest.mock import MagicMock
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from azure_devops.webhooks.webhook_processors.pull_request_processor import (
    PullRequestWebhookProcessor,
)


@pytest.fixture
def pull_request_processor(
    event: WebhookEvent, monkeypatch: pytest.MonkeyPatch
) -> PullRequestWebhookProcessor:
    mock_client = MagicMock()
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.pull_request_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )
    return PullRequestWebhookProcessor(event)


@pytest.mark.asyncio
async def test_pull_request_should_process_event(
    pull_request_processor: PullRequestWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "eventType": "git.pullrequest.updated",
            "publisherId": "tfs",
            "resource": {"pullRequestId": "123"},
        },
        headers={},
    )
    assert await pull_request_processor.should_process_event(event) is True

    event.payload["eventType"] = "wrong.event"
    assert await pull_request_processor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_pull_request_get_matching_kinds(
    pull_request_processor: PullRequestWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    assert await pull_request_processor.get_matching_kinds(event) == ["pull-request"]


@pytest.mark.asyncio
async def test_pull_request_validate_payload(
    pull_request_processor: PullRequestWebhookProcessor,
    mock_event_context: None,
) -> None:
    valid_payload = {
        "eventType": "git.pullrequest.updated",
        "publisherId": "tfs",
        "resource": {"pullRequestId": "123"},
    }
    assert await pull_request_processor.validate_payload(valid_payload) is True

    invalid_payload = {"missing": "fields"}
    assert await pull_request_processor.validate_payload(invalid_payload) is False
