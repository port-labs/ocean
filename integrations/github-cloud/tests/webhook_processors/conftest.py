import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from port_ocean.core.handlers.webhook.webhook_event import EventPayload, WebhookEvent
from github_cloud.webhook_processors.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from github_cloud.helpers.utils import ObjectKind
from typing import Generator


@pytest.fixture
def mock_webhook_event() -> WebhookEvent:
    """Create a base mock webhook event that can be customized by tests."""
    return WebhookEvent(
        payload={"action": "created"}, headers={"x-github-event": "default"}
    )


@pytest.fixture
def mock_event_payload() -> EventPayload:
    """Create a base mock event payload that can be customized by tests."""
    return EventPayload(action="created", repository={"full_name": "org/test-repo"})


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
        "updated_at": "2024-01-01T00:00:00Z",
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
def mock_init_client() -> Generator[AsyncMock, None, None]:
    """Mock the init_client function."""
    with patch("github_cloud.initialize_client.init_client") as mock:
        mock_client = AsyncMock()
        mock_client.fetch_resource = AsyncMock()
        mock.return_value = mock_client
        yield mock


@pytest.fixture
def base_webhook_event() -> WebhookEvent:
    """Create a base webhook event with common fields."""
    return WebhookEvent(
        payload={
            "repository": {"name": "test-repo", "full_name": "org/test-repo"},
            "sender": {"login": "test-user"},
        },
        headers={"x-github-event": "test-event"},
        trace_id="test-trace-id",
    )


@pytest.fixture
def mock_webhook_processor() -> AbstractWebhookProcessor:
    """Create a mock webhook processor for testing."""
    processor = AsyncMock(spec=AbstractWebhookProcessor)
    processor.should_process_event = AsyncMock(return_value=True)
    processor.get_supported_resource_kinds = AsyncMock(return_value=["test-kind"])
    processor.process_webhook_event = AsyncMock()
    processor.authenticate = AsyncMock(return_value=True)
    processor.validate_payload = AsyncMock(return_value=True)
    return processor


@pytest.fixture
def valid_issue_event(base_webhook_event) -> WebhookEvent:
    """Create a valid issue webhook event."""
    event = base_webhook_event
    event.payload.update(
        {"action": "opened", "issue": {"number": 1, "title": "Test Issue"}}
    )
    event.headers["x-github-event"] = "issues"
    return event


@pytest.fixture
def valid_pr_event(base_webhook_event) -> WebhookEvent:
    """Create a valid pull request webhook event."""
    event = base_webhook_event
    event.payload.update(
        {"action": "opened", "pull_request": {"number": 1, "title": "Test PR"}}
    )
    event.headers["x-github-event"] = "pull_request"
    return event


@pytest.fixture
def valid_repo_event(base_webhook_event) -> WebhookEvent:
    """Create a valid repository webhook event."""
    event = base_webhook_event
    event.payload.update({"action": "created"})
    event.headers["x-github-event"] = "repository"
    return event


@pytest.fixture
def valid_team_event(base_webhook_event) -> WebhookEvent:
    """Create a valid team webhook event."""
    event = base_webhook_event
    event.payload.update(
        {
            "action": "created",
            "team": {"name": "test-team", "id": 1},
            "organization": {"login": "test-org"},
        }
    )
    event.headers["x-github-event"] = "team"
    return event


@pytest.fixture
def valid_workflow_event(base_webhook_event) -> WebhookEvent:
    """Create a valid workflow webhook event."""
    event = base_webhook_event
    event.payload.update(
        {"action": "created", "workflow": {"name": "test-workflow", "id": 1}}
    )
    event.headers["x-github-event"] = "workflow"
    return event


@pytest.fixture
def delete_event_template(base_webhook_event) -> WebhookEvent:
    """Create a template for delete events."""
    event = base_webhook_event
    event.payload.update({"action": "deleted"})
    return event
