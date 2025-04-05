import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from port_ocean.context.event import event
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults
from integration import ObjectKind, PullRequestResourceConfig
from webhook_processors.pull_request_webhook_processor import (
    PullRequestWebhookProcessor,
)


@pytest.fixture
def mock_event():
    with patch("webhook_processors.pull_request_webhook_processor.event") as mock:
        mock.resource_config = MagicMock(spec=PullRequestResourceConfig)
        mock.resource_config.selector.organizations = ["org1"]
        mock.resource_config.selector.state = "all"
        yield mock


@pytest.fixture
def mock_client():
    with patch("webhook_processors.pull_request_webhook_processor.get_client") as mock:
        client = AsyncMock()
        mock.return_value = client
        yield client


@pytest.fixture
def pull_request_webhook_processor(mock_event):
    return PullRequestWebhookProcessor(event=mock_event)


@pytest.mark.asyncio
async def test_should_process_event(pull_request_webhook_processor):
    # Test valid actions
    for action in ["opened", "edited", "closed", "reopened", "merged", "synchronize"]:
        assert (
            await pull_request_webhook_processor.should_process_event(action, {})
            is True
        )

    # Test invalid action
    assert (
        await pull_request_webhook_processor.should_process_event("invalid", {})
        is False
    )


@pytest.mark.asyncio
async def test_get_matching_kinds(pull_request_webhook_processor):
    kinds = await pull_request_webhook_processor.get_matching_kinds()
    assert kinds == [ObjectKind.PULL_REQUEST]


@pytest.mark.asyncio
async def test_validate_payload(pull_request_webhook_processor):
    # Test valid payload
    valid_payload = {
        "pull_request": {"number": 1, "title": "Test PR"},
        "repository": {"name": "test-repo", "owner": {"login": "org1"}},
    }
    assert await pull_request_webhook_processor.validate_payload(valid_payload) is True

    # Test invalid payloads
    assert await pull_request_webhook_processor.validate_payload({}) is False
    assert (
        await pull_request_webhook_processor.validate_payload({"pull_request": {}})
        is False
    )
    assert (
        await pull_request_webhook_processor.validate_payload({"repository": {}})
        is False
    )


@pytest.mark.asyncio
async def test_handle_event_deleted(pull_request_webhook_processor, mock_client):
    payload = {
        "action": "closed",
        "pull_request": {
            "number": 1,
            "merged": False,
        },
        "repository": {"name": "test-repo", "owner": {"login": "org1"}},
    }

    result = await pull_request_webhook_processor.handle_event(payload)
    assert isinstance(result, WebhookEventRawResults)
    assert result.identifier == "1"
    assert result.state == "closed"


@pytest.mark.asyncio
async def test_handle_event_merged(pull_request_webhook_processor, mock_client):
    payload = {
        "action": "closed",
        "pull_request": {
            "number": 1,
            "merged": True,
            "title": "Test PR",
            "html_url": "https://github.com/org1/test-repo/pull/1",
            "state": "closed",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-02T00:00:00Z",
            "closed_at": "2024-01-02T00:00:00Z",
        },
        "repository": {"name": "test-repo", "owner": {"login": "org1"}},
    }

    mock_client.get_single_resource.return_value = payload["pull_request"]

    result = await pull_request_webhook_processor.handle_event(payload)
    assert isinstance(result, WebhookEventRawResults)
    assert result.identifier == "1"
    assert result.title == "Test PR"
    assert result.state == "merged"
    assert result.repository == "org1/test-repo"


@pytest.mark.asyncio
async def test_handle_event_updated(pull_request_webhook_processor, mock_client):
    payload = {
        "action": "opened",
        "pull_request": {
            "number": 1,
            "title": "Test PR",
            "html_url": "https://github.com/org1/test-repo/pull/1",
            "state": "open",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-02T00:00:00Z",
            "closed_at": None,
        },
        "repository": {"name": "test-repo", "owner": {"login": "org1"}},
    }

    mock_client.get_single_resource.return_value = payload["pull_request"]

    result = await pull_request_webhook_processor.handle_event(payload)
    assert isinstance(result, WebhookEventRawResults)
    assert result.identifier == "1"
    assert result.title == "Test PR"
    assert result.state == "open"
    assert result.repository == "org1/test-repo"


@pytest.mark.asyncio
async def test_handle_event_organization_filter(
    pull_request_webhook_processor, mock_client
):
    payload = {
        "action": "opened",
        "pull_request": {"number": 1},
        "repository": {"name": "test-repo", "owner": {"login": "other-org"}},
    }

    result = await pull_request_webhook_processor.handle_event(payload)
    assert result is None


@pytest.mark.asyncio
async def test_handle_event_state_filter(pull_request_webhook_processor, mock_client):
    payload = {
        "action": "opened",
        "pull_request": {
            "number": 1,
            "state": "closed",
        },
        "repository": {"name": "test-repo", "owner": {"login": "org1"}},
    }

    mock_client.get_single_resource.return_value = payload["pull_request"]
    pull_request_webhook_processor.event.resource_config.selector.state = "open"

    result = await pull_request_webhook_processor.handle_event(payload)
    assert result is None
