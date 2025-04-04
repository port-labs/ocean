import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from port_ocean.context.event import event
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults
from integration import ObjectKind, TeamResourceConfig
from webhook_processors.team_webhook_processor import TeamWebhookProcessor


@pytest.fixture
def mock_event():
    with patch("webhook_processors.team_webhook_processor.event") as mock:
        mock.resource_config = MagicMock(spec=TeamResourceConfig)
        mock.resource_config.selector.organizations = ["org1"]
        yield mock


@pytest.fixture
def mock_client():
    with patch("webhook_processors.team_webhook_processor.get_client") as mock:
        client = AsyncMock()
        mock.return_value = client
        yield client


@pytest.fixture
def team_webhook_processor(mock_event):
    return TeamWebhookProcessor(event=mock_event)


@pytest.mark.asyncio
async def test_should_process_event(team_webhook_processor):
    # Test valid actions
    for action in ["created", "deleted", "edited", "added_to_repository", "removed_from_repository"]:
        assert await team_webhook_processor.should_process_event(action, {}) is True

    # Test invalid action
    assert await team_webhook_processor.should_process_event("invalid", {}) is False


@pytest.mark.asyncio
async def test_get_matching_kinds(team_webhook_processor):
    kinds = await team_webhook_processor.get_matching_kinds()
    assert kinds == [ObjectKind.TEAM]


@pytest.mark.asyncio
async def test_validate_payload(team_webhook_processor):
    # Test valid payload
    valid_payload = {
        "team": {
            "name": "test-team",
            "slug": "test-team",
            "description": "Test team",
            "privacy": "closed"
        },
        "organization": {"login": "org1"}
    }
    assert await team_webhook_processor.validate_payload(valid_payload) is True

    # Test invalid payloads
    assert await team_webhook_processor.validate_payload({}) is False
    assert await team_webhook_processor.validate_payload({"team": {}}) is False
    assert await team_webhook_processor.validate_payload({"organization": {}}) is False


@pytest.mark.asyncio
async def test_handle_event_deleted(team_webhook_processor, mock_client):
    payload = {
        "action": "deleted",
        "team": {
            "name": "test-team",
            "slug": "test-team",
            "organization": {"login": "org1"}
        }
    }

    result = await team_webhook_processor.handle_event(payload)
    assert isinstance(result, WebhookEventRawResults)
    assert result.identifier == "test-team"
    assert result.state == "deleted"


@pytest.mark.asyncio
async def test_handle_event_updated(team_webhook_processor, mock_client):
    payload = {
        "action": "created",
        "team": {
            "name": "test-team",
            "slug": "test-team",
            "description": "Test team",
            "privacy": "closed",
            "html_url": "https://github.com/orgs/org1/teams/test-team",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-02T00:00:00Z",
            "organization": {"login": "org1"}
        }
    }

    mock_client.get_single_resource.return_value = payload["team"]

    result = await team_webhook_processor.handle_event(payload)
    assert isinstance(result, WebhookEventRawResults)
    assert result.identifier == "test-team"
    assert result.title == "test-team"
    assert result.state == "active"
    assert result.repository == "org1"


@pytest.mark.asyncio
async def test_handle_event_organization_filter(team_webhook_processor, mock_client):
    payload = {
        "action": "created",
        "team": {
            "name": "test-team",
            "slug": "test-team",
            "organization": {"login": "other-org"}
        }
    }

    result = await team_webhook_processor.handle_event(payload)
    assert result is None


@pytest.mark.asyncio
async def test_handle_event_repository_actions(team_webhook_processor, mock_client):
    # Test added_to_repository action
    payload = {
        "action": "added_to_repository",
        "team": {
            "name": "test-team",
            "slug": "test-team",
            "organization": {"login": "org1"}
        },
        "repository": {
            "name": "test-repo",
            "full_name": "org1/test-repo"
        }
    }

    mock_client.get_single_resource.return_value = payload["team"]

    result = await team_webhook_processor.handle_event(payload)
    assert isinstance(result, WebhookEventRawResults)
    assert result.identifier == "test-team"
    assert result.state == "active"
    assert result.repository == "org1/test-repo"

    # Test removed_from_repository action
    payload["action"] = "removed_from_repository"
    result = await team_webhook_processor.handle_event(payload)
    assert isinstance(result, WebhookEventRawResults)
    assert result.identifier == "test-team"
    assert result.state == "active"
    assert result.repository == "org1/test-repo"
