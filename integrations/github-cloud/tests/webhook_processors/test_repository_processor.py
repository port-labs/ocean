import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from github_cloud.webhook_processors.repository_webhook_processor import RepositoryWebhookProcessor
from github_cloud.helpers.constants import REPOSITORY_DELETE_EVENTS, REPOSITORY_UPSERT_EVENTS
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent, EventPayload


@pytest.mark.asyncio
async def test_repository_webhook_processor_should_process_event() -> None:
    """Test that repository webhook processor correctly identifies events it should process."""
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={"action": "created"},
        headers={"x-github-event": "repository"}
    )
    processor = RepositoryWebhookProcessor(event)
    
    # Test valid repository events
    for action in REPOSITORY_UPSERT_EVENTS + REPOSITORY_DELETE_EVENTS:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"action": action},
            headers={"x-github-event": "repository"}
        )
        assert await processor.should_process_event(event) is True
    
    # Test invalid events
    invalid_events = [
        {"action": "invalid", "x-github-event": "repository"},
        {"action": "created", "x-github-event": "team"},
        {"action": "created", "x-github-event": ""},
        {"action": "", "x-github-event": "repository"},
        {"action": None, "x-github-event": "repository"},
        {"action": "created", "x-github-event": None}
    ]
    
    for event_data in invalid_events:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"action": event_data["action"]},
            headers={"x-github-event": event_data["x-github-event"]}
        )
        assert await processor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_repository_webhook_processor_get_matching_kinds() -> None:
    """Test that repository webhook processor returns correct matching kinds."""
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={"action": "created"},
        headers={"x-github-event": "repository"}
    )
    processor = RepositoryWebhookProcessor(event)
    kinds = await processor.get_matching_kinds(event)
    assert kinds == ["repository"]


@pytest.fixture
def mock_client(mocker):
    mock_ocean = mocker.patch("initialize_client.ocean")
    mock_ocean.integration_config = {
        "github_base_url": "https://api.github.com",
        "github_access_token": "test-token",
        "app_host": "https://test.com",
        "webhook_secret": "test-secret",
        "github_organization": "test-org"
    }
    mock_client = AsyncMock()
    mock_init_client = mocker.patch("github_cloud.webhook_processors.repository_webhook_processor.init_client")
    mock_init_client.return_value = mock_client
    return mock_client


@pytest.mark.asyncio
async def test_repository_webhook_processor_handle_event_upsert(mock_client):
    repository_data = {
        "id": 123,
        "name": "test-repo",
        "full_name": "test-org/test-repo",
        "owner": {"login": "test-org"},
        "description": "Test repository",
        "private": False,
        "html_url": "https://github.com/test-org/test-repo",
        "created_at": "2024-03-30T00:00:00Z",
        "updated_at": "2024-03-30T00:00:00Z",
    }
    payload = {
        "action": "created",
        "repository": repository_data
    }
    event = WebhookEvent(
        headers={"x-github-event": "repository"},
        payload=payload,
        trace_id="test-trace-id"
    )
    processor = RepositoryWebhookProcessor(event)
    mock_client.get_single_resource.return_value = repository_data
    resource_config = AsyncMock()

    results = await processor.handle_event(payload, resource_config)
    assert len(results.updated_raw_results) == 1
    assert results.updated_raw_results[0]["id"] == 123
    assert results.updated_raw_results[0]["name"] == "test-repo"


@pytest.mark.asyncio
async def test_repository_webhook_processor_handle_event_delete(mock_client):
    repository_data = {
        "id": 123,
        "name": "test-repo",
        "full_name": "test-org/test-repo",
        "owner": {"login": "test-org"},
        "description": "Test repository",
        "private": False,
        "html_url": "https://github.com/test-org/test-repo",
        "created_at": "2024-03-30T00:00:00Z",
        "updated_at": "2024-03-30T00:00:00Z",
    }
    payload = {
        "action": "deleted",
        "repository": repository_data
    }
    event = WebhookEvent(
        headers={"x-github-event": "repository"},
        payload=payload,
        trace_id="test-trace-id"
    )
    processor = RepositoryWebhookProcessor(event)
    mock_client.get_single_resource.return_value = repository_data
    resource_config = AsyncMock()

    results = await processor.handle_event(payload, resource_config)
    assert len(results.deleted_raw_results) == 1
    assert results.deleted_raw_results[0]["id"] == 123
    assert results.deleted_raw_results[0]["name"] == "test-repo"


@pytest.mark.asyncio
async def test_repository_webhook_processor_handle_event_missing_data(mock_client):
    payload = {
        "action": "created",
        "repository": None
    }
    event = WebhookEvent(
        headers={"x-github-event": "repository"},
        payload=payload,
        trace_id="test-trace-id"
    )
    processor = RepositoryWebhookProcessor(event)
    mock_client.get_single_resource.return_value = None
    resource_config = AsyncMock()

    results = await processor.handle_event(payload, resource_config)
    assert len(results.updated_raw_results) == 0
    assert len(results.deleted_raw_results) == 0
    mock_client.get_single_resource.assert_not_awaited()


@pytest.mark.asyncio
async def test_repository_webhook_processor_handle_event_rename(mock_client):
    repository_data = {
        "id": 123,
        "name": "new-repo",
        "full_name": "test-org/new-repo",
        "owner": {"login": "test-org"},
        "description": "Test repository",
        "private": False,
        "html_url": "https://github.com/test-org/new-repo",
        "created_at": "2024-03-30T00:00:00Z",
        "updated_at": "2024-03-30T00:00:00Z",
    }
    payload = {
        "action": "renamed",
        "repository": repository_data
    }
    event = WebhookEvent(
        headers={"x-github-event": "repository"},
        payload=payload,
        trace_id="test-trace-id"
    )
    processor = RepositoryWebhookProcessor(event)
    mock_client.get_single_resource.return_value = repository_data
    resource_config = AsyncMock()

    results = await processor.handle_event(payload, resource_config)
    assert len(results.updated_raw_results) == 1
    assert results.updated_raw_results[0]["id"] == 123
    assert results.updated_raw_results[0]["name"] == "new-repo" 