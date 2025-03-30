import pytest
from unittest.mock import AsyncMock, patch
from github_cloud.webhook_processors.workflow_webhook_processor import WorkflowWebhookProcessor
from github_cloud.helpers.constants import WORKFLOW_DELETE_EVENTS, WORKFLOW_UPSERT_EVENTS
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent, EventPayload


@pytest.mark.asyncio
async def test_workflow_webhook_processor_should_process_event() -> None:
    """Test that workflow webhook processor correctly identifies events it should process."""
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={"action": "created"},
        headers={"x-github-event": "workflow"}
    )
    processor = WorkflowWebhookProcessor(event)
    
    # Test valid workflow events
    for action in WORKFLOW_UPSERT_EVENTS + WORKFLOW_DELETE_EVENTS:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"action": action},
            headers={"x-github-event": "workflow"}
        )
        assert await processor.should_process_event(event) is True
    
    # Test invalid events
    invalid_events = [
        {"action": "invalid", "x-github-event": "workflow"},
        {"action": "created", "x-github-event": "repository"},
        {"action": "created", "x-github-event": ""},
        {"action": "", "x-github-event": "workflow"},
        {"action": None, "x-github-event": "workflow"},
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
async def test_workflow_webhook_processor_get_matching_kinds() -> None:
    """Test that workflow webhook processor returns correct matching kinds."""
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={"action": "created"},
        headers={"x-github-event": "workflow"}
    )
    processor = WorkflowWebhookProcessor(event)
    kinds = await processor.get_matching_kinds(event)
    assert kinds == ["workflow"]


@pytest.mark.asyncio
async def test_workflow_webhook_processor_handle_event_upsert() -> None:
    """Test that workflow webhook processor correctly handles workflow creation/update events."""
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={"action": "created"},
        headers={"x-github-event": "workflow"}
    )
    processor = WorkflowWebhookProcessor(event)
    workflow_data = {
        "id": 1,
        "name": "CI/CD Pipeline",
        "path": ".github/workflows/ci.yml",
        "state": "active",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }
    payload = {
        "action": "created",
        "workflow": workflow_data,
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
            mock_client.get_single_resource.return_value = workflow_data
            
            results = await processor.handle_event(payload, resource_config)
            assert len(results.updated_raw_results) == 1
            assert results.updated_raw_results[0]["name"] == "CI/CD Pipeline"
            assert results.deleted_raw_results == []
            
            mock_client.get_single_resource.assert_awaited_once_with("workflow", "test-repo/1")


@pytest.mark.asyncio
async def test_workflow_webhook_processor_handle_event_delete() -> None:
    """Test that workflow webhook processor correctly handles workflow deletion events."""
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={"action": "deleted"},
        headers={"x-github-event": "workflow"}
    )
    processor = WorkflowWebhookProcessor(event)
    workflow_data = {
        "id": 1,
        "name": "CI/CD Pipeline",
        "path": ".github/workflows/ci.yml",
        "state": "active",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }
    payload = {
        "action": "deleted",
        "workflow": workflow_data,
        "repository": {"name": "test-repo"}
    }
    resource_config = AsyncMock()
    
    results = await processor.handle_event(payload, resource_config)
    assert len(results.updated_raw_results) == 0
    assert len(results.deleted_raw_results) == 1
    assert results.deleted_raw_results[0]["name"] == "CI/CD Pipeline"


@pytest.mark.asyncio
async def test_workflow_webhook_processor_handle_event_missing_data() -> None:
    """Test that workflow webhook processor handles missing or invalid data gracefully."""
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={"action": "created"},
        headers={"x-github-event": "workflow"}
    )
    processor = WorkflowWebhookProcessor(event)
    
    # Test with missing workflow data
    payload = {
        "action": "created",
        "workflow": {},
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
            
            # Verify client was not called since workflow ID was missing
            mock_client.get_single_resource.assert_not_awaited()
        
    # Test with missing repository data
    payload = {
        "action": "created",
        "workflow": {"id": 1},
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