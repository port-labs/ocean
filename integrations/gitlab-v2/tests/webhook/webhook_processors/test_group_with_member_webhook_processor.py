import pytest
from unittest.mock import AsyncMock, MagicMock

from gitlab.webhook.webhook_processors.group_with_member_webhook_processor import (
    GroupWithMemberWebhookProcessor,
)
from gitlab.helpers.utils import ObjectKind

from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
)

from typing import Any


@pytest.mark.asyncio
class TestGroupWithMemberWebhookProcessor:
    """Test the group with member webhook processor"""

    @pytest.fixture
    def mock_event(self) -> WebhookEvent:
        """Create a mock webhook event"""
        return WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "Subgroup Hook"},
            payload={},
        )

    @pytest.fixture
    def processor(self, mock_event: WebhookEvent) -> GroupWithMemberWebhookProcessor:
        """Create a GroupWithMemberWebhookProcessor instance"""
        return GroupWithMemberWebhookProcessor(event=mock_event)

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
        self, processor: GroupWithMemberWebhookProcessor, mock_event: WebhookEvent
    ) -> None:
        """Test that get_matching_kinds returns the GROUP_WITH_MEMBERS kind."""
        assert await processor.get_matching_kinds(mock_event) == [
            ObjectKind.GROUP_WITH_MEMBERS
        ]

    async def test_handle_event(
        self, processor: GroupWithMemberWebhookProcessor, group_payload: dict[str, Any]
    ) -> None:
        """Test handling a group event"""
        resource_config = MagicMock()
        resource_config.selector = MagicMock()
        resource_config.selector.include_bot_members = True

        group_id = group_payload["group_id"]
        expected_group = {
            "id": group_id,
            "name": group_payload["name"],
            "path": group_payload["path"],
            "__members": [
                {"id": 1, "username": "user1", "name": "User One"},
                {"id": 2, "username": "user2", "name": "User Two"},
            ],
        }

        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_group = AsyncMock(
            return_value={
                "id": group_id,
                "name": group_payload["name"],
                "path": group_payload["path"],
            }
        )
        processor._gitlab_webhook_client.enrich_group_with_members = AsyncMock(
            return_value=expected_group
        )

        result = await processor.handle_event(group_payload, resource_config)

        processor._gitlab_webhook_client.get_group.assert_called_once_with(group_id)
        processor._gitlab_webhook_client.enrich_group_with_members.assert_called_once_with(
            {
                "id": group_id,
                "name": group_payload["name"],
                "path": group_payload["path"],
            },
            include_bot_members=True,
        )
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == expected_group
        assert not result.deleted_raw_results

    async def test_handle_destroy_event(
        self, processor: GroupWithMemberWebhookProcessor
    ) -> None:
        """Test handling a group destroy event"""
        resource_config = MagicMock()
        destroy_payload = {
            "event_name": "group_destroy",
            "group_id": 10,
            "name": "deleted_group",
        }

        result = await processor.handle_event(destroy_payload, resource_config)

        assert not result.updated_raw_results
        assert len(result.deleted_raw_results) == 1
        assert result.deleted_raw_results[0] == destroy_payload

    async def test_should_process_event(
        self, processor: GroupWithMemberWebhookProcessor
    ) -> None:
        """Test that should_process_event correctly identifies group events"""
        # Valid group event
        valid_event = WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "Subgroup Hook"},
            payload={"event_name": "subgroup_create"},
        )
        assert await processor.should_process_event(valid_event) is True

        # Valid member event
        valid_member_event = WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "Member Hook"},
            payload={"event_name": "user_add_to_group"},
        )
        assert await processor.should_process_event(valid_member_event) is True

        # Invalid event type
        invalid_event = WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "Pipeline Hook"},
            payload={"event_name": "subgroup_create"},
        )
        assert await processor.should_process_event(invalid_event) is False

        # Invalid event name
        invalid_name_event = WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "Subgroup Hook"},
            payload={"event_name": "pipeline_success"},
        )
        assert await processor.should_process_event(invalid_name_event) is False

    async def test_validate_payload(
        self, processor: GroupWithMemberWebhookProcessor
    ) -> None:
        """Test that validate_payload correctly validates group payloads"""
        # Valid payload
        valid_payload = {
            "group_id": 10,
            "event_name": "subgroup_create",
        }
        assert await processor.validate_payload(valid_payload) is True

        # Missing group_id
        invalid_payload1 = {
            "event_name": "subgroup_create",
        }
        assert await processor.validate_payload(invalid_payload1) is False

        # Missing event_name
        invalid_payload2 = {
            "group_id": 10,
        }
        assert await processor.validate_payload(invalid_payload2) is False
