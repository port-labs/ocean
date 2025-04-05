import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from port_ocean.context.event import event
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults
from integration import ObjectKind, IssueResourceConfig
from webhook_processors.issue_webhook_processor import IssueWebhookProcessor


@pytest.fixture
def mock_event():
    with patch("webhook_processors.issue_webhook_processor.event") as mock:
        mock.resource_config = MagicMock(spec=IssueResourceConfig)
        mock.resource_config.selector.organizations = ["org1"]
        mock.resource_config.selector.state = "all"
        yield mock


@pytest.fixture
def mock_client():
    with patch("webhook_processors.issue_webhook_processor.get_client") as mock:
        client = AsyncMock()
        mock.return_value = client
        yield client


@pytest.fixture
def issue_webhook_processor(mock_event):
    return IssueWebhookProcessor(event=mock_event)


@pytest.mark.asyncio
async def test_should_process_event(issue_webhook_processor):
    # Test valid actions
    for action in ["opened", "edited", "closed", "reopened", "deleted"]:
        assert await issue_webhook_processor.should_process_event(action, {}) is True

    # Test invalid action
    assert await issue_webhook_processor.should_process_event("invalid", {}) is False


@pytest.mark.asyncio
async def test_get_matching_kinds(issue_webhook_processor):
    kinds = await issue_webhook_processor.get_matching_kinds()
    assert kinds == [ObjectKind.ISSUE]


@pytest.mark.asyncio
async def test_validate_payload(issue_webhook_processor):
    # Test valid payload
    valid_payload = {
        "issue": {"number": 1, "title": "Test Issue"},
        "repository": {"name": "test-repo", "owner": {"login": "org1"}},
    }
    assert await issue_webhook_processor.validate_payload(valid_payload) is True

    # Test invalid payloads
    assert await issue_webhook_processor.validate_payload({}) is False
    assert await issue_webhook_processor.validate_payload({"issue": {}}) is False
    assert await issue_webhook_processor.validate_payload({"repository": {}}) is False


@pytest.mark.asyncio
async def test_handle_event_deleted(issue_webhook_processor, mock_client):
    payload = {
        "action": "deleted",
        "issue": {"number": 1},
        "repository": {"name": "test-repo", "owner": {"login": "org1"}},
    }

    result = await issue_webhook_processor.handle_event(payload)
    assert isinstance(result, WebhookEventRawResults)
    assert result.identifier == "1"
    assert result.state == "deleted"


@pytest.mark.asyncio
async def test_handle_event_updated(issue_webhook_processor, mock_client):
    payload = {
        "action": "opened",
        "issue": {
            "number": 1,
            "title": "Test Issue",
            "html_url": "https://github.com/org1/test-repo/issues/1",
            "state": "open",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-02T00:00:00Z",
            "closed_at": None,
        },
        "repository": {"name": "test-repo", "owner": {"login": "org1"}},
    }

    mock_client.get_single_resource.return_value = payload["issue"]

    result = await issue_webhook_processor.handle_event(payload)
    assert isinstance(result, WebhookEventRawResults)
    assert result.identifier == "1"
    assert result.title == "Test Issue"
    assert result.state == "open"
    assert result.repository == "org1/test-repo"


@pytest.mark.asyncio
async def test_handle_event_organization_filter(issue_webhook_processor, mock_client):
    payload = {
        "action": "opened",
        "issue": {"number": 1},
        "repository": {"name": "test-repo", "owner": {"login": "other-org"}},
    }

    result = await issue_webhook_processor.handle_event(payload)
    assert result is None


@pytest.mark.asyncio
async def test_handle_event_state_filter(issue_webhook_processor, mock_client):
    payload = {
        "action": "opened",
        "issue": {
            "number": 1,
            "state": "closed",
        },
        "repository": {"name": "test-repo", "owner": {"login": "org1"}},
    }

    mock_client.get_single_resource.return_value = payload["issue"]
    issue_webhook_processor.event.resource_config.selector.state = "open"

    result = await issue_webhook_processor.handle_event(payload)
    assert result is None
