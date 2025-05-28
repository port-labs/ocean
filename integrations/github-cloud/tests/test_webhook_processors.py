import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Patch ocean before importing processors
patcher = patch('github_cloud.clients.client_factory.ocean', MagicMock())
patcher.start()

from github_cloud.webhook.webhook_processors import (
    RepositoryWebhookProcessor,
    PullRequestWebhookProcessor,
    WorkflowWebhookProcessor,
    IssueWebhookProcessor
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

class AsyncIteratorWrapper:
    """Helper class to wrap a list as an async iterator for testing."""
    def __init__(self, items):
        self._items = items
        self._index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._index >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._index]
        self._index += 1
        return item

@pytest.fixture
def mock_webhook_event():
    return WebhookEvent(
        headers={
            "x-github-event": "repository",
            "x-github-delivery": "123",
            "x-hub-signature-256": "sha256=123"
        },
        payload={
            "repository": {
                "id": 123,
                "name": "test-repo",
                "full_name": "owner/test-repo"
            },
            "ref": "refs/heads/main",
            "commits": [
                {
                    "id": "abc123",
                    "message": "test commit"
                }
            ]
        },
        trace_id="test-trace-id"
    )

@pytest.fixture
def mock_pull_request_event():
    return WebhookEvent(
        headers={
            "x-github-event": "pull_request",
            "x-github-delivery": "123",
            "x-hub-signature-256": "sha256=123"
        },
        payload={
            "repository": {
                "id": 123,
                "name": "test-repo",
                "full_name": "owner/test-repo"
            },
            "pull_request": {
                "id": 456,
                "number": 1,
                "title": "test pr",
                "state": "open"
            },
            "action": "opened"
        },
        trace_id="test-trace-id"
    )

@pytest.fixture
def mock_workflow_run_event():
    return WebhookEvent(
        headers={
            "x-github-event": "workflow_run",
            "x-github-delivery": "123",
            "x-hub-signature-256": "sha256=123"
        },
        payload={
            "action": "completed",
            "workflow_run": {
                "id": 789,
                "name": "Test Workflow",
                "status": "completed",
                "conclusion": "success",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:01:00Z",
                "html_url": "https://github.com/owner/repo/actions/runs/789",
                "head_branch": "main",
                "head_sha": "abc123",
                "triggering_actor": {
                    "login": "test-user"
                }
            },
            "repository": {
                "id": 123,
                "name": "test-repo",
                "full_name": "owner/test-repo"
            }
        },
        trace_id="test-trace-id"
    )

@pytest.fixture
def mock_workflow_job_event():
    return WebhookEvent(
        headers={
            "x-github-event": "workflow_job",
            "x-github-delivery": "123",
            "x-hub-signature-256": "sha256=123"
        },
        payload={
            "action": "completed",
            "workflow_job": {
                "id": 456,
                "name": "Test Job",
                "status": "completed",
                "conclusion": "success",
                "started_at": "2024-01-01T00:00:00Z",
                "completed_at": "2024-01-01T00:01:00Z",
                "runner_name": "test-runner",
                "runner_group_name": "test-group",
                "run_id": 789,
                "steps": [
                    {
                        "name": "Step 1",
                        "status": "completed",
                        "conclusion": "success",
                        "number": 1,
                        "started_at": "2024-01-01T00:00:00Z",
                        "completed_at": "2024-01-01T00:00:30Z"
                    }
                ]
            },
            "repository": {
                "id": 123,
                "name": "test-repo",
                "full_name": "owner/test-repo"
            },
            "workflow_run": {
                "id": 789,
                "name": "Test Workflow"
            }
        },
        trace_id="test-trace-id"
    )

@pytest.fixture
def mock_issue_event():
    """Fixture for a mock issue event."""
    return {
        "action": "opened",
        "issue": {
            "id": 123,
            "number": 1,
            "title": "Test Issue",
            "state": "open",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "closed_at": None,
            "body": "Test issue body",
            "html_url": "https://github.com/owner/repo/issues/1",
            "assignees": [{"login": "user1"}],
            "labels": [{"name": "bug"}],
            "user": {"login": "author1"}
        },
        "repository": {
            "id": 456,
            "full_name": "owner/repo",
            "name": "repo",
            "html_url": "https://github.com/owner/repo",
            "description": "Test repository",
            "default_branch": "main",
            "visibility": "public",
            "archived": False,
            "disabled": False,
            "fork": False,
            "forks_count": 0,
            "stargazers_count": 0,
            "watchers_count": 0,
            "open_issues_count": 1,
            "language": "Python",
            "topics": ["test"],
            "license": {"name": "MIT"},
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "pushed_at": "2024-01-01T00:00:00Z"
        }
    }

@pytest.mark.asyncio
async def test_repository_webhook_processor_authenticate(mock_webhook_event):
    processor = RepositoryWebhookProcessor(mock_webhook_event)
    result = await processor.authenticate(mock_webhook_event.payload, mock_webhook_event.headers)
    assert result is True

@pytest.mark.asyncio
async def test_pull_request_webhook_processor_authenticate(mock_pull_request_event):
    processor = PullRequestWebhookProcessor(mock_pull_request_event)
    result = await processor.authenticate(mock_pull_request_event.payload, mock_pull_request_event.headers)
    assert result is True

@pytest.mark.asyncio
async def test_repository_webhook_processor_should_process_event(mock_webhook_event):
    processor = RepositoryWebhookProcessor(mock_webhook_event)
    assert await processor.should_process_event(mock_webhook_event) is True

@pytest.mark.asyncio
async def test_pull_request_webhook_processor_should_process_event(mock_pull_request_event):
    processor = PullRequestWebhookProcessor(mock_pull_request_event)
    assert await processor.should_process_event(mock_pull_request_event) is True

@pytest.mark.asyncio
async def test_repository_webhook_processor_should_not_process_event():
    event = WebhookEvent(headers={"x-github-event": "unknown"}, payload={}, trace_id="test-trace-id")
    processor = RepositoryWebhookProcessor(event)
    assert await processor.should_process_event(event) is False

@pytest.mark.asyncio
async def test_pull_request_webhook_processor_should_not_process_event():
    event = WebhookEvent(headers={"x-github-event": "unknown"}, payload={}, trace_id="test-trace-id")
    processor = PullRequestWebhookProcessor(event)
    assert await processor.should_process_event(event) is False

@pytest.mark.asyncio
async def test_repository_webhook_processor_validate_payload(mock_webhook_event):
    processor = RepositoryWebhookProcessor(mock_webhook_event)
    assert await processor.validate_payload(mock_webhook_event.payload) is True

@pytest.mark.asyncio
async def test_pull_request_webhook_processor_validate_payload(mock_pull_request_event):
    processor = PullRequestWebhookProcessor(mock_pull_request_event)
    assert await processor.validate_payload(mock_pull_request_event.payload) is True

@pytest.mark.asyncio
async def test_repository_webhook_processor_validate_payload_invalid():
    event = WebhookEvent(headers={}, payload={}, trace_id="test-trace-id")
    processor = RepositoryWebhookProcessor(event)
    assert await processor.validate_payload(event.payload) is False

@pytest.mark.asyncio
async def test_pull_request_webhook_processor_validate_payload_invalid():
    event = WebhookEvent(headers={}, payload={}, trace_id="test-trace-id")
    processor = PullRequestWebhookProcessor(event)
    assert await processor.validate_payload(event.payload) is False

def test_repository_webhook_processor_events():
    event = WebhookEvent(headers={}, payload={}, trace_id="test-trace-id")
    processor = RepositoryWebhookProcessor(event)
    events = processor.events
    assert isinstance(events, list)

def test_pull_request_webhook_processor_events():
    event = WebhookEvent(headers={}, payload={}, trace_id="test-trace-id")
    processor = PullRequestWebhookProcessor(event)
    events = processor.events
    assert isinstance(events, list)

@pytest.mark.asyncio
async def test_repository_webhook_processor_handle_event(mock_webhook_event):
    processor = RepositoryWebhookProcessor(mock_webhook_event)
    mock_github_client = AsyncMock()
    processor._github_cloud_webhook_client = mock_github_client

    # Mock the repository data
    mock_repo = {
        "id": 123,
        "name": "test-repo",
        "full_name": "owner/test-repo",
        "default_branch": "main"
    }
    mock_github_client.get_repository.return_value = mock_repo

    # Test handle_event
    result = await processor.handle_event(mock_webhook_event.payload, MagicMock())

    assert result.updated_raw_results == [mock_repo]
    assert result.deleted_raw_results == []
    mock_github_client.get_repository.assert_called_once_with("owner/test-repo")

@pytest.mark.asyncio
async def test_repository_webhook_processor_handle_event_deleted(mock_webhook_event):
    processor = RepositoryWebhookProcessor(mock_webhook_event)

    # Modify payload for deleted event
    mock_webhook_event.payload["action"] = "deleted"
    mock_webhook_event.payload["repository"] = {
        "id": 123,
        "name": "test-repo",
        "full_name": "owner/test-repo"
    }

    # Test handle_event
    result = await processor.handle_event(mock_webhook_event.payload, MagicMock())

    assert result.updated_raw_results == []
    assert result.deleted_raw_results == [mock_webhook_event.payload["repository"]]

@pytest.mark.asyncio
async def test_pull_request_webhook_processor_handle_event(mock_pull_request_event):
    processor = PullRequestWebhookProcessor(mock_pull_request_event)
    mock_github_client = AsyncMock()
    processor._github_cloud_webhook_client = mock_github_client

    # Mock the pull request data
    mock_pr = {
        "id": 456,
        "number": 1,
        "title": "test pr",
        "state": "open",
        "repository": mock_pull_request_event.payload["repository"]
    }
    mock_github_client.get_pull_request.return_value = mock_pr

    # Test handle_event
    result = await processor.handle_event(mock_pull_request_event.payload, MagicMock())

    assert result.updated_raw_results == [mock_pr]
    assert result.deleted_raw_results == []
    mock_github_client.get_pull_request.assert_called_once_with(
        "owner/test-repo", 1
    )

@pytest.mark.asyncio
async def test_pull_request_webhook_processor_handle_event_fetch_failed(mock_pull_request_event):
    processor = PullRequestWebhookProcessor(mock_pull_request_event)
    mock_github_client = AsyncMock()
    processor._github_cloud_webhook_client = mock_github_client

    # Mock failed pull request fetch
    mock_github_client.get_pull_request.return_value = None

    # Test handle_event
    result = await processor.handle_event(mock_pull_request_event.payload, MagicMock())

    # Should use the PR from the payload
    expected_pr = mock_pull_request_event.payload["pull_request"]
    expected_pr["repository"] = mock_pull_request_event.payload["repository"]

    assert result.updated_raw_results == [expected_pr]
    assert result.deleted_raw_results == []
    mock_github_client.get_pull_request.assert_called_once_with(
        "owner/test-repo", 1
    )

@pytest.mark.asyncio
async def test_repository_webhook_processor_handle_event_missing_repo_name(mock_webhook_event):
    processor = RepositoryWebhookProcessor(mock_webhook_event)

    # Modify payload to remove repository full_name
    mock_webhook_event.payload["repository"] = {
        "id": 123,
        "name": "test-repo"
    }

    # Test handle_event
    result = await processor.handle_event(mock_webhook_event.payload, MagicMock())

    assert result.updated_raw_results == []
    assert result.deleted_raw_results == []

@pytest.mark.asyncio
async def test_repository_webhook_processor_validate_payload_missing_repository():
    event = WebhookEvent(
        headers={"x-github-event": "repository"},
        payload={"action": "created"},
        trace_id="test-trace-id"
    )
    processor = RepositoryWebhookProcessor(event)
    assert await processor.validate_payload(event.payload) is False

@pytest.mark.asyncio
async def test_pull_request_webhook_processor_validate_payload_missing_pull_request():
    event = WebhookEvent(
        headers={"x-github-event": "pull_request"},
        payload={"repository": {"full_name": "owner/repo"}},
        trace_id="test-trace-id"
    )
    processor = PullRequestWebhookProcessor(event)
    assert await processor.validate_payload(event.payload) is False

@pytest.mark.asyncio
async def test_pull_request_webhook_processor_validate_payload_missing_repository():
    event = WebhookEvent(
        headers={"x-github-event": "pull_request"},
        payload={"pull_request": {"number": 1}},
        trace_id="test-trace-id"
    )
    processor = PullRequestWebhookProcessor(event)
    assert await processor.validate_payload(event.payload) is False

@pytest.mark.asyncio
async def test_workflow_webhook_processor_authenticate(mock_workflow_run_event):
    processor = WorkflowWebhookProcessor(mock_workflow_run_event)
    result = await processor.authenticate(mock_workflow_run_event.payload, mock_workflow_run_event.headers)
    assert result is True

@pytest.mark.asyncio
async def test_workflow_webhook_processor_should_process_event(mock_workflow_run_event):
    processor = WorkflowWebhookProcessor(mock_workflow_run_event)
    assert await processor.should_process_event(mock_workflow_run_event) is False

@pytest.mark.asyncio
async def test_workflow_webhook_processor_should_not_process_event():
    event = WebhookEvent(headers={"x-github-event": "unknown"}, payload={}, trace_id="test-trace-id")
    processor = WorkflowWebhookProcessor(event)
    assert await processor.should_process_event(event) is False

@pytest.mark.asyncio
async def test_workflow_webhook_processor_validate_payload_workflow_run(mock_workflow_run_event):
    processor = WorkflowWebhookProcessor(mock_workflow_run_event)
    assert await processor.validate_payload(mock_workflow_run_event.payload) is True

@pytest.mark.asyncio
async def test_workflow_webhook_processor_validate_payload_workflow_job(mock_workflow_job_event):
    processor = WorkflowWebhookProcessor(mock_workflow_job_event)
    assert await processor.validate_payload(mock_workflow_job_event.payload) is True

@pytest.mark.asyncio
async def test_workflow_webhook_processor_validate_payload_invalid():
    event = WebhookEvent(headers={}, payload={}, trace_id="test-trace-id")
    processor = WorkflowWebhookProcessor(event)
    assert await processor.validate_payload(event.payload) is False

def test_workflow_webhook_processor_events():
    event = WebhookEvent(headers={}, payload={}, trace_id="test-trace-id")
    processor = WorkflowWebhookProcessor(event)
    events = processor.events
    assert isinstance(events, list)
    assert "workflow" in events

@pytest.mark.asyncio
async def test_issue_webhook_processor_handle_issue_event(mock_issue_event):
    """Test handling of issue events."""
    # Create mock GitHub client
    mock_github_client = AsyncMock()

    # Mock the issue data to be returned
    mock_issue = {
        "id": 123,
        "number": 1,
        "title": "Test Issue",
        "state": "open",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        "closed_at": None,
        "body": "Test issue body",
        "html_url": "https://github.com/owner/repo/issues/1",
        "assignees": [{"login": "user1"}],
        "labels": [{"name": "bug"}],
        "user": {"login": "author1"}
    }

    # Set up the mock to return our mock issue
    mock_github_client.get_issue.return_value = mock_issue

    # Create the processor with our mock client
    processor = IssueWebhookProcessor(WebhookEvent(
        payload=mock_issue_event,
        trace_id="test-trace",
        headers={"x-github-event": "issues"}
    ))
    processor._github_cloud_webhook_client = mock_github_client

    # Process the event
    results = await processor.handle_event()

    # Verify the results
    assert len(results.updated_raw_results) == 1
    updated_issue = results.updated_raw_results[0]
    assert updated_issue["id"] == mock_issue["id"]
    assert updated_issue["number"] == mock_issue["number"]
    assert updated_issue["title"] == mock_issue["title"]
    assert updated_issue["repository"] == mock_issue_event["repository"]

    # Verify the mock was called correctly
    mock_github_client.get_issue.assert_called_once_with(
        mock_issue_event["repository"]["full_name"],
        mock_issue_event["issue"]["number"]
    )

@pytest.mark.asyncio
async def test_issue_webhook_processor_handle_issue_event_fetch_failure(mock_issue_event):
    """Test handling of issue events when GitHub API fetch fails."""
    # Create mock GitHub client
    mock_github_client = AsyncMock()

    # Set up the mock to return None (simulating API failure)
    mock_github_client.get_issue.return_value = None

    # Create the processor with our mock client
    processor = IssueWebhookProcessor(WebhookEvent(
        payload=mock_issue_event,
        trace_id="test-trace",
        headers={"x-github-event": "issues"}
    ))
    processor._github_cloud_webhook_client = mock_github_client

    # Process the event
    results = await processor.handle_event()

    # Verify the results fall back to payload data
    assert len(results.updated_raw_results) == 1
    updated_issue = results.updated_raw_results[0]
    assert updated_issue["id"] == mock_issue_event["issue"]["id"]
    assert updated_issue["number"] == mock_issue_event["issue"]["number"]
    assert updated_issue["title"] == mock_issue_event["issue"]["title"]
    assert updated_issue["repository"] == mock_issue_event["repository"]

    # Verify the mock was called
    mock_github_client.get_issue.assert_called_once_with(
        mock_issue_event["repository"]["full_name"],
        mock_issue_event["issue"]["number"]
    )

@pytest.mark.asyncio
async def test_issue_webhook_processor_validate_payload():
    """Test payload validation."""
    processor = IssueWebhookProcessor(WebhookEvent(payload={}, trace_id="test-trace", headers={}))

    # Test invalid payload
    assert not await processor.validate_payload({})
    assert not await processor.validate_payload({"issue": {}})
    assert not await processor.validate_payload({"repository": {}})

    # Test valid payload
    valid_payload = {
        "issue": {"number": 1},
        "repository": {"full_name": "owner/repo"}
    }
    assert await processor.validate_payload(valid_payload)
