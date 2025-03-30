import pytest
from unittest.mock import AsyncMock, MagicMock
from port_ocean.core.handlers.webhook.webhook_event import EventPayload, WebhookEvent


@pytest.fixture
def mock_webhook_event() -> WebhookEvent:
    """Create a base mock webhook event that can be customized by tests."""
    return WebhookEvent(
        payload={"action": "created"},
        headers={"x-github-event": "default"}
    )


@pytest.fixture
def mock_event_payload() -> EventPayload:
    """Create a base mock event payload that can be customized by tests."""
    return EventPayload(
        action="created",
        repository={"full_name": "org/test-repo"}
    )


@pytest.fixture
def mock_resource_config() -> AsyncMock:
    """Create a mock resource configuration."""
    return AsyncMock()


@pytest.fixture
def mock_github_response() -> dict:
    """Create a base mock GitHub API response that can be customized by tests."""
    return {
        "id": 1,
        "name": "test-resource",
        "html_url": "https://github.com/org/test-repo",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }


@pytest.fixture
def mock_github_client(mock_github_response: dict) -> MagicMock:
    """Create a mock GitHub client with common methods."""
    client = MagicMock()
    client.get_single_resource = AsyncMock(return_value=mock_github_response)
    client.get_repositories = AsyncMock(return_value=[mock_github_response])
    client.get_issues = AsyncMock(return_value=[mock_github_response])
    client.get_pull_requests = AsyncMock(return_value=[mock_github_response])
    client.get_teams = AsyncMock(return_value=[mock_github_response])
    client.get_workflows = AsyncMock(return_value=[mock_github_response])
    return client


@pytest.fixture
def mock_init_client(mock_github_client: MagicMock) -> AsyncMock:
    """Create a mock init_client function that returns the mock GitHub client."""
    return AsyncMock(return_value=mock_github_client) 