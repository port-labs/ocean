"""Tests for Okta webhook processors."""

import pytest
from unittest.mock import AsyncMock, Mock, patch

from okta.webhook_processors.user_webhook_processor import UserWebhookProcessor
from okta.webhook_processors.group_webhook_processor import GroupWebhookProcessor
 
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from port_ocean.core.handlers.port_app_config.models import ResourceConfig


class TestUserWebhookProcessor:
    """Test cases for UserWebhookProcessor."""

    @pytest.fixture
    def processor(self):
        """Create a UserWebhookProcessor instance."""
        with patch('okta.webhook_processors.user_webhook_processor.create_okta_client'):
            return UserWebhookProcessor()

    @pytest.fixture
    def user_event(self):
        """Create a user webhook event."""
        return WebhookEvent(
            trace_id="test-trace-id",
            payload={
                "eventType": "user.lifecycle.create",
                "published": "2023-01-01T00:00:00Z",
                "eventId": "test-event-id",
                "target": [
                    {
                        "type": "User",
                        "id": "user123",
                        "displayName": "Test User",
                    }
                ],
            },
            headers={},
        )

    @pytest.mark.asyncio
    async def test_should_process_event_user_event(self, processor, user_event):
        """Test that user events are processed."""
        assert await processor._should_process_event(user_event) is True

    @pytest.mark.asyncio
    async def test_should_process_event_non_user_event(self, processor):
        """Test that non-user events are not processed."""
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={
                "eventType": "group.lifecycle.create",
                "published": "2023-01-01T00:00:00Z",
                "eventId": "test-event-id",
            },
            headers={},
        )
        assert await processor._should_process_event(event) is False

    @pytest.mark.asyncio
    async def test_get_matching_kinds(self, processor, user_event):
        """Test that user events match the correct kind."""
        kinds = await processor.get_matching_kinds(user_event)
        assert kinds == ["okta-user"]

    @pytest.mark.asyncio
    async def test_handle_event_create(self, processor, user_event):
        """Test handling a user creation event."""
        with patch.object(processor.client, 'get_user') as mock_get_user:
            mock_get_user.return_value = {"id": "user123", "profile": {"email": "test@example.com"}}
            
            with patch.object(processor.client, 'get_user_groups') as mock_get_groups:
                mock_get_groups.return_value = []
                
                with patch.object(processor.client, 'get_user_apps') as mock_get_apps:
                    mock_get_apps.return_value = []
                    
                    resource_config = ResourceConfig(kind="okta-user", selector={})
                    result = await processor.handle_event(user_event.payload, resource_config)
                    
                    assert len(result.updated_raw_results) == 1
                    assert result.updated_raw_results[0]["id"] == "user123"
                    assert len(result.deleted_raw_results) == 0

    @pytest.mark.asyncio
    async def test_handle_event_delete(self, processor):
        """Test handling a user deletion event."""
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={
                "eventType": "user.lifecycle.delete",
                "published": "2023-01-01T00:00:00Z",
                "eventId": "test-event-id",
                "target": [
                    {
                        "type": "User",
                        "id": "user123",
                    }
                ],
            },
            headers={},
        )
        
        resource_config = ResourceConfig(kind="okta-user", selector={})
        result = await processor.handle_event(event.payload, resource_config)
        
        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 1
        assert result.deleted_raw_results[0]["id"] == "user123"

    def test_extract_user_id_from_target(self, processor):
        """Test extracting user ID from target array."""
        payload = {
            "target": [
                {
                    "type": "User",
                    "id": "user123",
                }
            ]
        }
        user_id = processor._extract_user_id(payload)
        assert user_id == "user123"

    def test_extract_user_id_from_debug_context(self, processor):
        """Test extracting user ID from debug context."""
        payload = {
            "debugContext": {
                "user": {
                    "id": "user123",
                }
            }
        }
        user_id = processor._extract_user_id(payload)
        assert user_id == "user123"


class TestGroupWebhookProcessor:
    """Test cases for GroupWebhookProcessor."""

    @pytest.fixture
    def processor(self):
        """Create a GroupWebhookProcessor instance."""
        with patch('okta.webhook_processors.group_webhook_processor.create_okta_client'):
            return GroupWebhookProcessor()

    @pytest.fixture
    def group_event(self):
        """Create a group webhook event."""
        return WebhookEvent(
            trace_id="test-trace-id",
            payload={
                "eventType": "group.lifecycle.create",
                "published": "2023-01-01T00:00:00Z",
                "eventId": "test-event-id",
                "target": [
                    {
                        "type": "UserGroup",
                        "id": "group123",
                        "displayName": "Test Group",
                    }
                ],
            },
            headers={},
        )

    @pytest.mark.asyncio
    async def test_should_process_event_group_event(self, processor, group_event):
        """Test that group events are processed."""
        assert await processor._should_process_event(group_event) is True

    @pytest.mark.asyncio
    async def test_get_matching_kinds(self, processor, group_event):
        """Test that group events match the correct kind."""
        kinds = await processor.get_matching_kinds(group_event)
        assert kinds == ["okta-group"]


 

