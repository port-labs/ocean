import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Patch ocean before importing processors
patcher = patch('github_cloud.clients.client_factory.ocean', MagicMock())
patcher.start()

from github_cloud.webhook.webhook_processors import (
    RepositoryWebhookProcessor,
    PullRequestWebhookProcessor
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

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
