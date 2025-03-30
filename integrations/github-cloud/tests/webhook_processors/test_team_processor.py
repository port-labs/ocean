import pytest
from unittest.mock import AsyncMock, patch
from github_cloud.webhook_processors.team_webhook_processor import TeamWebhookProcessor
from github_cloud.helpers.constants import TEAM_DELETE_EVENTS, TEAM_UPSERT_EVENTS
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent, EventPayload


@pytest.mark.asyncio
async def test_team_webhook_processor_should_process_event() -> None:
    """Test that team webhook processor correctly identifies events it should process."""
    event = WebhookEvent(
        trace_id="test-trace",
        payload={"action": "created"},
        headers={"x-github-event": "team"}
    )
    processor = TeamWebhookProcessor(event)
    
    # Test valid team events
    for action in TEAM_UPSERT_EVENTS + TEAM_DELETE_EVENTS:
        event = WebhookEvent(
            trace_id="test-trace",
            payload={"action": action},
            headers={"x-github-event": "team"}
        )
        assert await processor.should_process_event(event) is True
    
    # Test invalid events
    invalid_events = [
        {"action": "invalid", "x-github-event": "team"},
        {"action": "created", "x-github-event": "repository"},
        {"action": "created", "x-github-event": ""},
        {"action": "", "x-github-event": "team"},
        {"action": None, "x-github-event": "team"},
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
async def test_team_webhook_processor_get_matching_kinds() -> None:
    """Test that team webhook processor returns correct matching kinds."""
    event = WebhookEvent(
        trace_id="test-trace",
        payload={"action": "created"},
        headers={"x-github-event": "team"}
    )
    processor = TeamWebhookProcessor(event)
    kinds = await processor.get_matching_kinds(event)
    assert kinds == ["team"]


@pytest.mark.asyncio
async def test_team_webhook_processor_handle_event_upsert() -> None:
    """Test that team webhook processor correctly handles team creation/update events."""
    event = WebhookEvent(
        trace_id="test-trace",
        payload={"action": "created"},
        headers={"x-github-event": "team"}
    )
    processor = TeamWebhookProcessor(event)
    team_data = {
        "id": 1,
        "name": "test-team",
        "slug": "test-team",
        "description": "Test team description",
        "privacy": "closed"
    }
    payload = {
        "action": "created",
        "team": team_data
    }
    resource_config = AsyncMock()
    
    with patch("initialize_client.ocean") as mock_ocean:
        mock_ocean.integration_config = {
            "github_base_url": "https://api.github.com",
            "github_access_token": "test-token",
            "app_host": "https://test.com",
            "webhook_secret": "test-secret",
            "github_organization": "test-org"
        }
        mock_client = AsyncMock()
        mock_client.organization = "test-org"
        mock_client.base_url = "https://api.github.com"
        mock_init_client = patch("github_cloud.webhook_processors.team_webhook_processor.init_client")
        mock_init_client.start().return_value = mock_client
        mock_client.get_single_resource.return_value = team_data
        
        results = await processor.handle_event(payload, resource_config)
        mock_init_client.stop()
        assert len(results.updated_raw_results) == 1
        assert results.updated_raw_results[0]["name"] == "test-team"
        assert results.deleted_raw_results == []
        
        mock_client.get_single_resource.assert_awaited_once_with("team", "test-team")


@pytest.mark.asyncio
async def test_team_webhook_processor_handle_event_delete() -> None:
    """Test that team webhook processor correctly handles team deletion events."""
    event = WebhookEvent(
        trace_id="test-trace",
        payload={"action": "deleted"},
        headers={"x-github-event": "team"}
    )
    processor = TeamWebhookProcessor(event)
    team_data = {
        "id": 1,
        "name": "test-team",
        "slug": "test-team",
        "description": "Test team description",
        "privacy": "closed"
    }
    payload = {
        "action": "deleted",
        "team": team_data
    }
    resource_config = AsyncMock()
    
    results = await processor.handle_event(payload, resource_config)
    assert len(results.updated_raw_results) == 0
    assert len(results.deleted_raw_results) == 1
    assert results.deleted_raw_results[0]["name"] == "test-team"


@pytest.mark.asyncio
async def test_team_webhook_processor_handle_event_missing_data() -> None:
    """Test that team webhook processor handles missing or invalid data gracefully."""
    event = WebhookEvent(
        trace_id="test-trace",
        payload={"action": "created"},
        headers={"x-github-event": "team"}
    )
    processor = TeamWebhookProcessor(event)
    
    # Test with missing team data
    payload = {
        "action": "created",
        "team": {}
    }
    resource_config = AsyncMock()
    
    with patch("initialize_client.ocean") as mock_ocean:
        mock_ocean.integration_config = {
            "github_base_url": "https://api.github.com",
            "github_access_token": "test-token",
            "app_host": "https://test.com",
            "webhook_secret": "test-secret",
            "github_organization": "test-org"
        }
        mock_client = AsyncMock()
        mock_client.organization = "test-org"
        mock_client.base_url = "https://api.github.com"
        mock_init_client = patch("github_cloud.webhook_processors.team_webhook_processor.init_client")
        mock_init_client.start().return_value = mock_client
        mock_client.get_single_resource.return_value = None
        
        results = await processor.handle_event(payload, resource_config)
        mock_init_client.stop()
        assert len(results.updated_raw_results) == 0
        assert len(results.deleted_raw_results) == 0
        
        # Verify client was not called since team name was missing
        mock_client.get_single_resource.assert_not_awaited() 