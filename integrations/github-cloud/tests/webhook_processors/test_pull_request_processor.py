import pytest
from unittest.mock import AsyncMock, patch
from github_cloud.webhook_processors.pull_request_webhook_processor import PullRequestWebhookProcessor
from github_cloud.helpers.constants import PULL_REQUEST_DELETE_EVENTS, PULL_REQUEST_UPSERT_EVENTS
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent, EventPayload


@pytest.mark.asyncio
async def test_pull_request_webhook_processor_should_process_event() -> None:
    """Test that pull request webhook processor correctly identifies events it should process."""
    event = WebhookEvent(
        trace_id="test-trace",
        payload={"action": "opened"},
        headers={"x-github-event": "pull_request"}
    )
    processor = PullRequestWebhookProcessor(event)
    
    # Test valid pull request events
    for action in PULL_REQUEST_UPSERT_EVENTS + PULL_REQUEST_DELETE_EVENTS:
        event = WebhookEvent(
            trace_id="test-trace",
            payload={"action": action},
            headers={"x-github-event": "pull_request"}
        )
        assert await processor.should_process_event(event) is True
    
    # Test invalid events
    invalid_events = [
        {"action": "invalid", "x-github-event": "pull_request"},
        {"action": "created", "x-github-event": "repository"},
        {"action": "created", "x-github-event": ""},
        {"action": "", "x-github-event": "pull_request"},
        {"action": None, "x-github-event": "pull_request"},
        {"action": "created", "x-github-event": None}
    ]
    
    for event_data in invalid_events:
        event = WebhookEvent(
            trace_id="test-trace",
            payload={"action": event_data["action"]},
            headers={"x-github-event": event_data["x-github-event"]}
        )
        assert await processor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_pull_request_webhook_processor_get_matching_kinds() -> None:
    """Test that pull request webhook processor returns correct matching kinds."""
    event = WebhookEvent(
        trace_id="test-trace",
        payload={"action": "created"},
        headers={"x-github-event": "pull_request"}
    )
    processor = PullRequestWebhookProcessor(event)
    kinds = await processor.get_matching_kinds(event)
    assert kinds == ["pull_request"]


@pytest.mark.asyncio
async def test_pull_request_webhook_processor_handle_event_upsert() -> None:
    """Test that pull request webhook processor correctly handles PR creation/update events."""
    event = WebhookEvent(
        trace_id="test-trace",
        payload={"action": "opened"},
        headers={"x-github-event": "pull_request"}
    )
    processor = PullRequestWebhookProcessor(event)
    pr_data = {
        "id": 1,
        "number": 123,
        "title": "Feature: Add new functionality",
        "state": "open",
        "html_url": "https://github.com/org/repo/pull/123",
        "body": "This PR adds new features",
        "user": {"login": "test-user"},
        "base": {"ref": "main", "repo": {"full_name": "org/repo"}},
        "head": {"ref": "feature-branch"},
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }
    payload = {
        "action": "opened",
        "pull_request": pr_data,
        "repository": {"name": "test-repo"}
    }
    resource_config = AsyncMock()
    
    with patch("initialize_client.ocean") as mock_ocean:
        mock_ocean.integration_config = {
            "github_access_token": "test-token",
            "github_base_url": "https://api.github.com",
            "app_host": "https://app.example.com",
            "webhook_secret": "test-secret",
            "github_organization": "test-org"
        }
        
        with patch("initialize_client.GithubClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get_single_resource.return_value = pr_data
            mock_client_class.create_from_ocean_config.return_value = mock_client
            
            results = await processor.handle_event(payload, resource_config)
            assert len(results.updated_raw_results) == 1
            assert results.updated_raw_results[0]["number"] == 123
            assert results.updated_raw_results[0]["title"] == "Feature: Add new functionality"
            assert results.deleted_raw_results == []
            
            mock_client.get_single_resource.assert_awaited_once_with("pull_request", "test-repo/123")


@pytest.mark.asyncio
async def test_pull_request_webhook_processor_handle_event_delete() -> None:
    """Test that pull request webhook processor correctly handles PR deletion events."""
    event = WebhookEvent(
        trace_id="test-trace",
        payload={"action": "deleted"},
        headers={"x-github-event": "pull_request"}
    )
    processor = PullRequestWebhookProcessor(event)
    pr_data = {
        "id": 1,
        "number": 123,
        "title": "Feature: Add new functionality",
        "state": "open",
        "html_url": "https://github.com/org/repo/pull/123",
        "body": "This PR adds new features",
        "user": {"login": "test-user"},
        "base": {"ref": "main", "repo": {"full_name": "org/repo"}},
        "head": {"ref": "feature-branch"},
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }
    payload = {
        "action": "deleted",
        "pull_request": pr_data,
        "repository": {"name": "test-repo"}
    }
    resource_config = AsyncMock()
    
    results = await processor.handle_event(payload, resource_config)
    assert len(results.updated_raw_results) == 0
    assert len(results.deleted_raw_results) == 1
    assert results.deleted_raw_results[0]["number"] == 123


@pytest.mark.asyncio
async def test_pull_request_webhook_processor_handle_event_missing_data() -> None:
    """Test that pull request webhook processor handles missing or invalid data gracefully."""
    event = WebhookEvent(
        trace_id="test-trace",
        payload={"action": "opened"},
        headers={"x-github-event": "pull_request"}
    )
    processor = PullRequestWebhookProcessor(event)
    
    # Test with missing PR data
    payload = {
        "action": "opened",
        "pull_request": {},
        "repository": {"name": "test-repo"}
    }
    resource_config = AsyncMock()
    
    with patch("initialize_client.ocean") as mock_ocean:
        mock_ocean.integration_config = {
            "github_access_token": "test-token",
            "github_base_url": "https://api.github.com",
            "app_host": "https://app.example.com",
            "webhook_secret": "test-secret",
            "github_organization": "test-org"
        }
        
        with patch("initialize_client.GithubClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get_single_resource.return_value = None
            mock_client_class.create_from_ocean_config.return_value = mock_client
            
            results = await processor.handle_event(payload, resource_config)
            assert len(results.updated_raw_results) == 0
            assert len(results.deleted_raw_results) == 0
            
            # Verify client was not called since PR number was missing
            mock_client.get_single_resource.assert_not_awaited()
        
    # Test with missing repository data
    payload = {
        "action": "opened",
        "pull_request": {"number": 123},
        "repository": {}
    }
    
    with patch("initialize_client.ocean") as mock_ocean:
        mock_ocean.integration_config = {
            "github_access_token": "test-token",
            "github_base_url": "https://api.github.com",
            "app_host": "https://app.example.com",
            "webhook_secret": "test-secret",
            "github_organization": "test-org"
        }
        
        with patch("initialize_client.GithubClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get_single_resource.return_value = None
            mock_client_class.create_from_ocean_config.return_value = mock_client
            
            results = await processor.handle_event(payload, resource_config)
            assert len(results.updated_raw_results) == 0
            assert len(results.deleted_raw_results) == 0
            
            # Verify client was not called since repository name was missing
            mock_client.get_single_resource.assert_not_awaited()


@pytest.mark.asyncio
async def test_pull_request_webhook_processor_handle_event_review() -> None:
    """Test that pull request webhook processor correctly handles PR review events."""
    event = WebhookEvent(
        trace_id="test-trace",
        payload={"action": "submitted"},
        headers={"x-github-event": "pull_request"}
    )
    processor = PullRequestWebhookProcessor(event)
    pr_data = {
        "id": 1,
        "number": 123,
        "title": "Feature: Add new functionality",
        "state": "open",
        "html_url": "https://github.com/org/repo/pull/123",
        "body": "This PR adds new features",
        "user": {"login": "test-user"},
        "base": {"ref": "main", "repo": {"full_name": "org/repo"}},
        "head": {"ref": "feature-branch"},
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }
    payload = {
        "action": "submitted",
        "pull_request": pr_data,
        "repository": {"name": "test-repo"},
        "review": {
            "state": "approved",
            "user": {"login": "reviewer"},
            "body": "Looks good!",
            "submitted_at": "2024-01-01T00:00:00Z"
        }
    }
    resource_config = AsyncMock()
    
    with patch("initialize_client.ocean") as mock_ocean:
        mock_ocean.integration_config = {
            "github_access_token": "test-token",
            "github_base_url": "https://api.github.com",
            "app_host": "https://app.example.com",
            "webhook_secret": "test-secret",
            "github_organization": "test-org"
        }
        
        with patch("initialize_client.GithubClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get_single_resource.return_value = pr_data
            mock_client_class.create_from_ocean_config.return_value = mock_client
            
            results = await processor.handle_event(payload, resource_config)
            assert len(results.updated_raw_results) == 1
            assert results.updated_raw_results[0]["number"] == 123
            assert results.updated_raw_results[0]["title"] == "Feature: Add new functionality"
            assert results.deleted_raw_results == []
            
            mock_client.get_single_resource.assert_awaited_once_with("pull_request", "test-repo/123") 