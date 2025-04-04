import pytest
from unittest.mock import AsyncMock, patch
from github_cloud.webhook_processors.issue_webhook_processor import (
    IssueWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from github_cloud.helpers.utils import ObjectKind


@pytest.fixture
async def processor():
    with patch(
        "github_cloud.webhook_processors.issue_webhook_processor.init_client"
    ) as mock_init_client:
        mock_client = AsyncMock()
        mock_init_client.return_value = mock_client
        processor = IssueWebhookProcessor()
        yield processor


@pytest.fixture
def valid_issue_event():
    return WebhookEvent(
        payload={
            "action": "opened",
            "issue": {"number": 1, "title": "Test Issue"},
            "repository": {"name": "test-repo", "full_name": "org/test-repo"},
            "sender": {"login": "test-user"},
        },
        headers={"x-github-event": "issues"},
        trace_id="test-trace-id",
    )


@pytest.mark.asyncio
async def test_should_process_event(processor, valid_issue_event):
    # Test valid event
    assert await processor.should_process_event(valid_issue_event) is True

    # Test invalid event type
    invalid_event = WebhookEvent(
        payload={"action": "opened"},
        headers={"x-github-event": "invalid"},
        trace_id="test-trace-id",
    )
    assert await processor.should_process_event(invalid_event) is False

    # Test invalid action
    invalid_action = WebhookEvent(
        payload={"action": "invalid_action"},
        headers={"x-github-event": "issues"},
        trace_id="test-trace-id",
    )
    assert await processor.should_process_event(invalid_action) is False


@pytest.mark.asyncio
async def test_get_supported_resource_kinds(processor, valid_issue_event):
    kinds = await processor.get_supported_resource_kinds(valid_issue_event)
    assert kinds == [ObjectKind.ISSUE]


@pytest.mark.asyncio
async def test_validate_payload(processor):
    # Test valid payload
    valid_payload = {
        "action": "opened",
        "issue": {"number": 1},
        "repository": {"name": "test-repo"},
        "sender": {"login": "test-user"},
    }
    assert await processor.validate_payload(valid_payload) is True

    # Test missing required fields
    invalid_payload = {"action": "opened", "issue": {"number": 1}}
    assert await processor.validate_payload(invalid_payload) is False


@pytest.mark.asyncio
async def test_authenticate(processor):
    # Test authentication (always returns True as per implementation)
    assert await processor.authenticate({}, {}) is True


@pytest.mark.asyncio
async def test_process_webhook_event(processor, valid_issue_event):
    # Mock the client's fetch_resource method
    processor.client.fetch_resource.return_value = {"number": 1, "title": "Test Issue"}

    # Test successful event processing
    result = await processor.process_webhook_event(valid_issue_event.payload, {})
    assert isinstance(result, WebhookEventRawResults)
    assert len(result.updated_raw_results) > 0
    assert len(result.deleted_raw_results) == 0

    # Test delete action
    delete_event = WebhookEvent(
        payload={
            "action": "deleted",
            "issue": {"number": 1},
            "repository": {"name": "test-repo"},
            "sender": {"login": "test-user"},
        },
        headers={"x-github-event": "issues"},
        trace_id="test-trace-id",
    )
    result = await processor.process_webhook_event(delete_event.payload, {})
    assert len(result.updated_raw_results) == 0
    assert len(result.deleted_raw_results) > 0

    # Test error handling
    processor.client.fetch_resource.side_effect = Exception("Test error")
    result = await processor.process_webhook_event(valid_issue_event.payload, {})
    assert len(result.updated_raw_results) == 0
    assert len(result.deleted_raw_results) == 0
