import pytest
from unittest.mock import AsyncMock, patch
from github_cloud.webhook_processors.issue_webhook_processor import IssueWebhookProcessor
from github_cloud.helpers.constants import ISSUE_DELETE_EVENTS, ISSUE_UPSERT_EVENTS
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent, EventPayload


@pytest.mark.asyncio
async def test_issue_webhook_processor_should_process_event() -> None:
    """Test that issue webhook processor correctly identifies events it should process."""
    event = WebhookEvent(
        trace_id="test-trace",
        payload={"action": "opened"},
        headers={"x-github-event": "issues"}
    )
    processor = IssueWebhookProcessor(event)
    
    # Test valid issue events
    for action in ISSUE_UPSERT_EVENTS + ISSUE_DELETE_EVENTS:
        event = WebhookEvent(
            trace_id="test-trace",
            payload={"action": action},
            headers={"x-github-event": "issues"}
        )
        assert await processor.should_process_event(event) is True
    
    # Test invalid events
    invalid_events = [
        {"action": "invalid", "x-github-event": "issues"},
        {"action": "created", "x-github-event": "repository"},
        {"action": "created", "x-github-event": ""},
        {"action": "", "x-github-event": "issues"},
        {"action": None, "x-github-event": "issues"},
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
async def test_issue_webhook_processor_get_matching_kinds() -> None:
    """Test that issue webhook processor returns correct matching kinds."""
    event = WebhookEvent(
        trace_id="test-trace",
        payload={"action": "created"},
        headers={"x-github-event": "issues"}
    )
    processor = IssueWebhookProcessor(event)
    kinds = await processor.get_matching_kinds(event)
    assert kinds == ["issue"]


@pytest.mark.asyncio
async def test_issue_webhook_processor_handle_event_upsert() -> None:
    """Test that issue webhook processor correctly handles issue creation/update events."""
    event = WebhookEvent(
        trace_id="test-trace",
        payload={"action": "opened"},
        headers={"x-github-event": "issues"}
    )
    processor = IssueWebhookProcessor(event)
    issue_data = {
        "id": 1,
        "number": 123,
        "title": "Bug: Fix critical issue",
        "state": "open",
        "html_url": "https://github.com/org/repo/issues/123",
        "body": "This is a critical bug that needs fixing",
        "user": {"login": "test-user"},
        "labels": [{"name": "bug"}, {"name": "high-priority"}],
        "assignees": [{"login": "assignee-user"}],
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }
    payload = {
        "action": "opened",
        "issue": issue_data,
        "repository": {"name": "test-repo"}
    }
    resource_config = AsyncMock()
    
    with patch("initialize_client.ocean") as mock_ocean:
        mock_ocean.integration_config = {
            "github_access_token": "test-token",
            "github_base_url": "https://api.github.com",
            "app_host": "http://localhost:8000",
            "webhook_secret": "test-secret",
            "github_organization": "test-org"
        }
        with patch("initialize_client.GithubClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.create_from_ocean_config.return_value = mock_client
            mock_client.get_single_resource.return_value = issue_data
            
            results = await processor.handle_event(payload, resource_config)
            assert len(results.updated_raw_results) == 1
            assert results.updated_raw_results[0]["number"] == 123
            assert results.updated_raw_results[0]["title"] == "Bug: Fix critical issue"
            assert results.deleted_raw_results == []
            
            mock_client.get_single_resource.assert_awaited_once_with("issue", "test-repo/123")


@pytest.mark.asyncio
async def test_issue_webhook_processor_handle_event_delete() -> None:
    """Test that issue webhook processor correctly handles issue deletion events."""
    event = WebhookEvent(
        trace_id="test-trace",
        payload={"action": "deleted"},
        headers={"x-github-event": "issues"}
    )
    processor = IssueWebhookProcessor(event)
    issue_data = {
        "id": 1,
        "number": 123,
        "title": "Bug: Fix critical issue",
        "state": "open",
        "html_url": "https://github.com/org/repo/issues/123",
        "body": "This is a critical bug that needs fixing",
        "user": {"login": "test-user"},
        "labels": [{"name": "bug"}, {"name": "high-priority"}],
        "assignees": [{"login": "assignee-user"}],
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }
    payload = {
        "action": "deleted",
        "issue": issue_data,
        "repository": {"name": "test-repo"}
    }
    resource_config = AsyncMock()
    
    results = await processor.handle_event(payload, resource_config)
    assert len(results.updated_raw_results) == 0
    assert len(results.deleted_raw_results) == 1
    assert results.deleted_raw_results[0]["number"] == 123


@pytest.mark.asyncio
async def test_issue_webhook_processor_handle_event_missing_data() -> None:
    """Test that issue webhook processor handles missing or invalid data gracefully."""
    event = WebhookEvent(
        trace_id="test-trace",
        payload={"action": "opened"},
        headers={"x-github-event": "issues"}
    )
    processor = IssueWebhookProcessor(event)
    
    # Test with missing issue data
    payload = {
        "action": "opened",
        "issue": {},
        "repository": {"name": "test-repo"}
    }
    resource_config = AsyncMock()
    
    with patch("initialize_client.ocean") as mock_ocean:
        mock_ocean.integration_config = {
            "github_access_token": "test-token",
            "github_base_url": "https://api.github.com",
            "app_host": "http://localhost:8000",
            "webhook_secret": "test-secret",
            "github_organization": "test-org"
        }
        with patch("initialize_client.GithubClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.create_from_ocean_config.return_value = mock_client
            mock_client.get_single_resource.return_value = None
            
            results = await processor.handle_event(payload, resource_config)
            assert len(results.updated_raw_results) == 0
            assert len(results.deleted_raw_results) == 0
            
            # Verify client was not called since issue number was missing
            mock_client.get_single_resource.assert_not_awaited()
        
    # Test with missing repository data
    payload = {
        "action": "opened",
        "issue": {"number": 123},
        "repository": {}
    }
    
    with patch("initialize_client.ocean") as mock_ocean:
        mock_ocean.integration_config = {
            "github_access_token": "test-token",
            "github_base_url": "https://api.github.com",
            "app_host": "http://localhost:8000",
            "webhook_secret": "test-secret",
            "github_organization": "test-org"
        }
        with patch("initialize_client.GithubClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.create_from_ocean_config.return_value = mock_client
            mock_client.get_single_resource.return_value = None
            
            results = await processor.handle_event(payload, resource_config)
            assert len(results.updated_raw_results) == 0
            assert len(results.deleted_raw_results) == 0
            
            # Verify client was not called since repository name was missing
            mock_client.get_single_resource.assert_not_awaited()


@pytest.mark.asyncio
async def test_issue_webhook_processor_handle_event_label_changes() -> None:
    """Test that issue webhook processor correctly handles issue label changes."""
    event = WebhookEvent(
        trace_id="test-trace",
        payload={"action": "labeled"},
        headers={"x-github-event": "issues"}
    )
    processor = IssueWebhookProcessor(event)
    issue_data = {
        "id": 1,
        "number": 123,
        "title": "Bug: Fix critical issue",
        "state": "open",
        "html_url": "https://github.com/org/repo/issues/123",
        "body": "This is a critical bug that needs fixing",
        "user": {"login": "test-user"},
        "labels": [{"name": "bug"}, {"name": "high-priority"}],
        "assignees": [{"login": "assignee-user"}],
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }
    payload = {
        "action": "labeled",
        "issue": issue_data,
        "repository": {"name": "test-repo"}
    }
    resource_config = AsyncMock()
    
    with patch("initialize_client.ocean") as mock_ocean:
        mock_ocean.integration_config = {
            "github_access_token": "test-token",
            "github_base_url": "https://api.github.com",
            "app_host": "http://localhost:8000",
            "webhook_secret": "test-secret",
            "github_organization": "test-org"
        }
        with patch("initialize_client.GithubClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.create_from_ocean_config.return_value = mock_client
            mock_client.get_single_resource.return_value = issue_data
            
            results = await processor.handle_event(payload, resource_config)
            assert len(results.updated_raw_results) == 1
            assert results.updated_raw_results[0]["number"] == 123
            assert results.updated_raw_results[0]["title"] == "Bug: Fix critical issue"
            assert results.deleted_raw_results == []
            
            mock_client.get_single_resource.assert_awaited_once_with("issue", "test-repo/123") 