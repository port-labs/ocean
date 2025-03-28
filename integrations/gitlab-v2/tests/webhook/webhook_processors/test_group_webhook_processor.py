import pytest
from unittest.mock import AsyncMock, MagicMock

from gitlab.webhook.webhook_processors.group_webhook_processor import (
    GroupWebhookProcessor,
)
from gitlab.helpers.utils import ObjectKind

from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
)

from typing import Any


@pytest.mark.asyncio
class TestGroupWebhookProcessor:
    """Test the group webhook processor"""

    @pytest.fixture
    def mock_event(self) -> WebhookEvent:
        """Create a mock webhook event"""
        return WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "group"},
            payload={},
        )

    @pytest.fixture
    def processor(self, mock_event: WebhookEvent) -> GroupWebhookProcessor:
        """Create a GroupWebhookProcessor instance"""
        return GroupWebhookProcessor(event=mock_event)

    @pytest.fixture
    def group_payload(self) -> dict[str, Any]:
        """Create a sample group webhook payload"""
        return {
            "created_at": "2021-01-20T09:40:12Z",
            "updated_at": "2021-01-20T09:40:12Z",
            "event_name": "subgroup_create",
            "name": "subgroup1",
            "path": "subgroup1",
            "full_path": "group1/subgroup1",
            "group_id": 10,
            "parent_group_id": 7,
            "parent_name": "group1",
            "parent_path": "group1",
            "parent_full_path": "group1",
        }

    async def test_get_matching_kinds(
        self, processor: GroupWebhookProcessor, mock_event: WebhookEvent
    ) -> None:
        """Test that get_matching_kinds returns the GROUP kind."""
        assert await processor.get_matching_kinds(mock_event) == [ObjectKind.GROUP]

    async def test_handle_event(
        self, processor: GroupWebhookProcessor, group_payload: dict[str, Any]
    ) -> None:
        """Test handling a group event"""
        resource_config = MagicMock()
        group_id = group_payload["group_id"]
        expected_group = {
            "id": group_id,
            "name": group_payload["name"],
            "path": group_payload["path"],
        }
        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_group = AsyncMock(
            return_value=expected_group
        )

        result = await processor.handle_event(group_payload, resource_config)

        processor._gitlab_webhook_client.get_group.assert_called_once_with(group_id)
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == expected_group
        assert not result.deleted_raw_results
