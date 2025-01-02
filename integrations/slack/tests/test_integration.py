import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from typing import Dict, Any, Awaitable, Callable

from port_ocean.context.event import event_context
from port_ocean.core.event_listener.base import EventListenerEvents
from port_ocean.core.event_listener.webhooks_only import (
    WebhooksOnlyEventListener,
    WebhooksOnlyEventListenerSettings,
)
from ..main import SlackIntegration

async def mock_resync_handler(event_data: Dict[Any, Any]) -> None:
    """Mock resync event handler for testing."""
    pass


@pytest.mark.asyncio
async def test_initial_sync(mock_slack_client: AsyncMock, mock_event_context):
    """Test initial sync functionality."""
    integration = SlackIntegration(mock_event_context)
    integration.client = mock_slack_client

    await integration.on_start()

    # Verify that channels and users were fetched
    mock_slack_client._request.assert_any_call(
        "GET", "conversations.list",
        params={
            "exclude_archived": "false",
            "types": "public_channel,private_channel",
            "limit": 1000
        }
    )
    mock_slack_client._request.assert_any_call(
        "GET", "users.list",
        params={"limit": 1000}
    )
    # Channel members are fetched for each channel
    mock_slack_client._request.assert_any_call(
        "GET", "conversations.members",
        params={
            "channel": "C123456",
            "limit": 1000
        }
    )


@pytest.mark.asyncio
async def test_webhook_event_handling(mock_slack_client: AsyncMock, mock_event_context):
    """Test webhook event handling."""
    integration = SlackIntegration(mock_event_context)
    integration.client = mock_slack_client

    # Test rate limit handling for channel info
    mock_slack_client._request.side_effect = [
        {"ok": False, "error": "ratelimited", "retry_after": 1},  # First call gets rate limited
        {"ok": True, "channel": {"id": "C123456", "name": "new-channel"}},  # Second call succeeds
        {"ok": True},  # Response for member_joined_channel event
        {"ok": True, "members": ["U123456"], "response_metadata": {"next_cursor": "cursor123"}},  # First page of members
        {"ok": True, "members": ["U789012"], "response_metadata": {"next_cursor": ""}}  # Second page of members
    ]

    # Test channel creation event
    channel_event = {
        "type": "event_callback",
        "event": {
            "type": "channel_created",
            "channel": {
                "id": "C123456",
                "name": "new-channel",
            }
        }
    }

    event_listener = integration.EventListenerClass(
        event_listener_config=WebhooksOnlyEventListenerSettings(type="WEBHOOKS_ONLY"),
        integration=integration,
        events={"on_resync": mock_resync_handler}
    )

    response = await event_listener.handle_request(
        AsyncMock(json=AsyncMock(return_value=channel_event))
    )

    assert response == {"ok": True}
    # Verify rate limit handling and channel info request
    mock_slack_client._request.assert_any_call(
        "GET", "conversations.info",
        params={
            "channel": "C123456"
        }
    )

    # Test channel deletion event
    delete_event = {
        "type": "event_callback",
        "event": {
            "type": "channel_deleted",
            "channel": "C123456"
        }
    }

    response = await event_listener.handle_request(
        AsyncMock(json=AsyncMock(return_value=delete_event))
    )
    assert response == {"ok": True}

    # Test channel rename event
    rename_event = {
        "type": "event_callback",
        "event": {
            "type": "channel_rename",
            "channel": {
                "id": "C123456",
                "name": "renamed-channel"
            }
        }
    }

    response = await event_listener.handle_request(
        AsyncMock(json=AsyncMock(return_value=rename_event))
    )
    assert response == {"ok": True}

    # Test member joined channel event
    member_event = {
        "type": "event_callback",
        "event": {
            "type": "member_joined_channel",
            "channel": "C123456",
            "user": "U123456"
        }
    }

    # Test error handling
    mock_slack_client._request.side_effect = Exception("API Error")
    response = await event_listener.handle_request(
        AsyncMock(json=AsyncMock(return_value=member_event))
    )
    assert response == {"ok": False, "error": "Failed to process event"}

    response = await event_listener.handle_request(
        AsyncMock(json=AsyncMock(return_value=member_event))
    )

    assert response == {"ok": True}
    # Verify pagination handling for members list
    mock_slack_client._request.assert_any_call(
        "GET", "conversations.members",
        params={
            "channel": "C123456",
            "cursor": "",
            "limit": 1000
        }
    )
    mock_slack_client._request.assert_any_call(
        "GET", "conversations.members",
        params={
            "channel": "C123456",
            "cursor": "cursor123",
            "limit": 1000
        }
    )


@pytest.mark.asyncio
async def test_url_verification(mock_event_context):
    """Test URL verification challenge handling."""
    integration = SlackIntegration(mock_event_context)

    # Test URL verification challenge
    challenge_event = {
        "type": "url_verification",
        "challenge": "test_challenge"
    }

    event_listener = integration.EventListenerClass(
        event_listener_config=WebhooksOnlyEventListenerSettings(type="WEBHOOKS_ONLY"),
        integration=integration,
        events={"on_resync": mock_resync_handler}
    )

    response = await event_listener.handle_request(
        AsyncMock(json=AsyncMock(return_value=challenge_event))
    )

    assert response == {"challenge": "test_challenge"}


@pytest.mark.asyncio
async def test_sync_channel_members(mock_slack_client: AsyncMock, mock_event_context):
    """Test channel members synchronization."""
    integration = SlackIntegration(mock_event_context)
    integration.client = mock_slack_client

    await integration.sync_channel_members("C123456")

    mock_slack_client._request.assert_called_with(
        "GET", "conversations.members",
        params={
            "channel": "C123456",
            "limit": 1000
        }
    )


@pytest.mark.asyncio
async def test_resync(mock_slack_client: AsyncMock, mock_event_context):
    """Test resync functionality."""
    integration = SlackIntegration(mock_event_context)
    integration.client = mock_slack_client

    await integration.on_resync()

    # Verify that all resources were resynced
    mock_slack_client._request.assert_any_call(
        "GET", "conversations.list",
        params={
            "exclude_archived": "false",
            "types": "public_channel,private_channel",
            "limit": 1000
        }
    )
    mock_slack_client._request.assert_any_call(
        "GET", "users.list",
        params={"limit": 1000}
    )
    mock_slack_client._request.assert_any_call(
        "GET", "conversations.members",
        params={
            "channel": "C123456",
            "limit": 1000
        }
    )
