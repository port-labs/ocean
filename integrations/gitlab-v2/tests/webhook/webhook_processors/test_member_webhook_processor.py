import pytest
from unittest.mock import AsyncMock, MagicMock

from gitlab.webhook.webhook_processors.member_webhook_processor import (
    MemberWebhookProcessor,
)
from gitlab.helpers.utils import ObjectKind

from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
)

from typing import Any


@pytest.mark.asyncio
class TestMemberWebhookProcessor:
    """Test the member webhook processor"""

    @pytest.fixture
    def mock_event(self) -> WebhookEvent:
        """Create a mock webhook event"""
        return WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "Member Hook"},
            payload={},
        )

    @pytest.fixture
    def processor(self, mock_event: WebhookEvent) -> MemberWebhookProcessor:
        """Create a MemberWebhookProcessor instance"""
        return MemberWebhookProcessor(event=mock_event)

    @pytest.fixture
    def member_payload(self) -> dict[str, Any]:
        """Create a sample member webhook payload"""
        return {
            "created_at": "2021-01-20T09:40:12Z",
            "updated_at": "2021-01-20T09:40:12Z",
            "event_name": "user_add_to_group",
            "group_id": 10,
            "group_name": "test-group",
            "group_path": "test-group",
            "user_id": 123,
            "user_name": "Test User",
            "user_username": "testuser",
            "user_email": "test@example.com",
            "group_access": "Developer",
        }

    async def test_get_matching_kinds(
        self, processor: MemberWebhookProcessor, mock_event: WebhookEvent
    ) -> None:
        """Test that get_matching_kinds returns the MEMBER and GROUP_WITH_MEMBERS kinds."""
        assert await processor.get_matching_kinds(mock_event) == [
            ObjectKind.MEMBER,
            ObjectKind.GROUP_WITH_MEMBERS,
        ]

    async def test_handle_event(
        self, processor: MemberWebhookProcessor, member_payload: dict[str, Any]
    ) -> None:
        """Test handling a member event"""
        resource_config = MagicMock()
        resource_config.selector = MagicMock()
        resource_config.selector.include_bot_members = True

        group_id = member_payload["group_id"]
        user_id = member_payload["user_id"]
        expected_member = {
            "id": user_id,
            "username": member_payload["user_username"],
            "name": member_payload["user_name"],
            "email": member_payload["user_email"],
            "access_level": member_payload["group_access"],
        }

        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_group_member = AsyncMock(
            return_value=expected_member
        )

        result = await processor.handle_event(member_payload, resource_config)

        processor._gitlab_webhook_client.get_group_member.assert_called_once_with(
            group_id, user_id
        )
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == expected_member
        assert not result.deleted_raw_results

    async def test_handle_remove_event(self, processor: MemberWebhookProcessor) -> None:
        """Test handling a member remove event"""
        resource_config = MagicMock()
        remove_payload = {
            "event_name": "user_remove_from_group",
            "group_id": 10,
            "user_id": 123,
            "user_username": "testuser",
        }

        result = await processor.handle_event(remove_payload, resource_config)

        assert not result.updated_raw_results
        assert len(result.deleted_raw_results) == 1
        assert result.deleted_raw_results[0] == remove_payload

    async def test_handle_bot_member_with_exclude(
        self, processor: MemberWebhookProcessor
    ) -> None:
        """Test handling a bot member when include_bot_members is False"""
        resource_config = MagicMock()
        resource_config.selector = MagicMock()
        resource_config.selector.include_bot_members = False

        bot_payload = {
            "event_name": "user_add_to_group",
            "group_id": 10,
            "user_id": 123,
            "user_username": "botuser",  # Changed to "botuser" to trigger the bot check
        }

        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_group_member = AsyncMock(
            return_value={
                "id": 123,
                "username": "botuser",
                "name": "Bot User",
            }
        )

        result = await processor.handle_event(bot_payload, resource_config)

        # The implementation should not call get_group_member for bot users when include_bot_members is False
        processor._gitlab_webhook_client.get_group_member.assert_not_called()

        # The implementation should return empty results and include the payload in deleted_raw_results
        assert not result.updated_raw_results
        assert len(result.deleted_raw_results) == 1
        assert result.deleted_raw_results[0] == bot_payload

    async def test_should_process_event(
        self, processor: MemberWebhookProcessor
    ) -> None:
        """Test that should_process_event correctly identifies member events"""
        # Valid member event
        valid_event = WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "Member Hook"},
            payload={"event_name": "user_add_to_group"},
        )
        assert await processor.should_process_event(valid_event) is True

        # Invalid event type
        invalid_event = WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "Pipeline Hook"},
            payload={"event_name": "user_add_to_group"},
        )
        assert await processor.should_process_event(invalid_event) is False

        # Invalid event name
        invalid_name_event = WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "Member Hook"},
            payload={"event_name": "pipeline_success"},
        )
        assert await processor.should_process_event(invalid_name_event) is False

    async def test_validate_payload(self, processor: MemberWebhookProcessor) -> None:
        """Test that validate_payload correctly validates member payloads"""
        # Valid payload
        valid_payload = {
            "group_id": 10,
            "user_id": 123,
            "event_name": "user_add_to_group",
        }
        assert await processor.validate_payload(valid_payload) is True

        # Missing group_id
        invalid_payload1 = {
            "user_id": 123,
            "event_name": "user_add_to_group",
        }
        assert await processor.validate_payload(invalid_payload1) is False

        # Missing user_id
        invalid_payload2 = {
            "group_id": 10,
            "event_name": "user_add_to_group",
        }
        assert await processor.validate_payload(invalid_payload2) is False

        # Missing event_name
        invalid_payload3 = {
            "group_id": 10,
            "user_id": 123,
        }
        assert await processor.validate_payload(invalid_payload3) is False
