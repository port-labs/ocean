import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from port_ocean.context.event import event
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults
from integration import ObjectKind, RepositoryResourceConfig
from webhook_processors.repository_webhook_processor import RepositoryWebhookProcessor


@pytest.fixture
def mock_event():
    with patch("webhook_processors.repository_webhook_processor.event") as mock:
        mock.resource_config = MagicMock(spec=RepositoryResourceConfig)
        mock.resource_config.selector.organizations = ["org1"]
        mock.resource_config.selector.visibility = "all"
        yield mock


@pytest.fixture
def mock_client():
    with patch("webhook_processors.repository_webhook_processor.get_client") as mock:
        client = AsyncMock()
        mock.return_value = client
        yield client


@pytest.fixture
def repository_webhook_processor(mock_event):
    return RepositoryWebhookProcessor(event=mock_event)


@pytest.mark.asyncio
async def test_should_process_event(repository_webhook_processor):
    # Test valid actions
    for action in [
        "created",
        "deleted",
        "archived",
        "unarchived",
        "edited",
        "renamed",
        "transferred",
        "publicized",
        "privatized",
    ]:
        assert (
            await repository_webhook_processor.should_process_event(action, {}) is True
        )

    # Test invalid action
    assert (
        await repository_webhook_processor.should_process_event("invalid", {}) is False
    )


@pytest.mark.asyncio
async def test_get_matching_kinds(repository_webhook_processor):
    kinds = await repository_webhook_processor.get_matching_kinds()
    assert kinds == [ObjectKind.REPOSITORY]


@pytest.mark.asyncio
async def test_validate_payload(repository_webhook_processor):
    # Test valid payload
    valid_payload = {
        "repository": {
            "name": "test-repo",
            "full_name": "org1/test-repo",
            "private": False,
            "owner": {"login": "org1"},
        }
    }
    assert await repository_webhook_processor.validate_payload(valid_payload) is True

    # Test invalid payloads
    assert await repository_webhook_processor.validate_payload({}) is False
    assert (
        await repository_webhook_processor.validate_payload({"repository": {}}) is False
    )


@pytest.mark.asyncio
async def test_handle_event_deleted(repository_webhook_processor, mock_client):
    payload = {
        "action": "deleted",
        "repository": {
            "name": "test-repo",
            "full_name": "org1/test-repo",
            "owner": {"login": "org1"},
        },
    }

    result = await repository_webhook_processor.handle_event(payload)
    assert isinstance(result, WebhookEventRawResults)
    assert result.identifier == "org1/test-repo"
    assert result.state == "deleted"


@pytest.mark.asyncio
async def test_handle_event_updated(repository_webhook_processor, mock_client):
    payload = {
        "action": "created",
        "repository": {
            "name": "test-repo",
            "full_name": "org1/test-repo",
            "private": False,
            "description": "Test repository",
            "html_url": "https://github.com/org1/test-repo",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-02T00:00:00Z",
            "owner": {"login": "org1"},
        },
    }

    mock_client.get_single_resource.return_value = payload["repository"]

    result = await repository_webhook_processor.handle_event(payload)
    assert isinstance(result, WebhookEventRawResults)
    assert result.identifier == "org1/test-repo"
    assert result.title == "test-repo"
    assert result.state == "active"
    assert result.repository == "org1/test-repo"


@pytest.mark.asyncio
async def test_handle_event_organization_filter(
    repository_webhook_processor, mock_client
):
    payload = {
        "action": "created",
        "repository": {
            "name": "test-repo",
            "full_name": "other-org/test-repo",
            "owner": {"login": "other-org"},
        },
    }

    result = await repository_webhook_processor.handle_event(payload)
    assert result is None


@pytest.mark.asyncio
async def test_handle_event_visibility_filter(
    repository_webhook_processor, mock_client
):
    payload = {
        "action": "created",
        "repository": {
            "name": "test-repo",
            "full_name": "org1/test-repo",
            "private": True,
            "owner": {"login": "org1"},
        },
    }

    mock_client.get_single_resource.return_value = payload["repository"]
    repository_webhook_processor.event.resource_config.selector.visibility = "public"

    result = await repository_webhook_processor.handle_event(payload)
    assert result is None
