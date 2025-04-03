import pytest
from unittest.mock import AsyncMock, MagicMock

from gitlab.webhook.webhook_processors.push_webhook_processor import (
    PushWebhookProcessor,
)
from gitlab.helpers.utils import ObjectKind

from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
)
from typing import Any


@pytest.mark.asyncio
class TestPushWebhookProcessor:
    """Test the push webhook processor"""

    @pytest.fixture
    def mock_event(self) -> WebhookEvent:
        """Create a mock webhook event"""
        return WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "push"},
            payload={},
        )

    @pytest.fixture
    def processor(self, mock_event: WebhookEvent) -> PushWebhookProcessor:
        """Create a PushWebhookProcessor instance"""
        return PushWebhookProcessor(event=mock_event)

    @pytest.fixture
    def push_payload(self) -> dict[str, Any]:
        """Create a sample push webhook payload"""
        return {
            "object_kind": "push",
            "event_name": "push",
            "before": "abc123",
            "after": "def456",
            "ref": "refs/heads/main",
            "checkout_sha": "def456",
            "user_id": 1,
            "user_name": "Test User",
            "project_id": 123,
            "project": {
                "id": 123,
                "name": "test-repo",
                "url": "https://gitlab.example.com/test/test-repo.git",
                "description": "Test repository",
                "homepage": "https://gitlab.example.com/test/test-repo",
            },
        }

    async def test_get_matching_kinds(
        self, processor: PushWebhookProcessor, mock_event: WebhookEvent
    ) -> None:
        """Test that get_matching_kinds returns the PUSH kind."""
        assert await processor.get_matching_kinds(mock_event) == [ObjectKind.PROJECT]

    async def test_handle_event(
        self, processor: PushWebhookProcessor, push_payload: dict[str, Any]
    ) -> None:
        """Test handling a push event"""
        resource_config = MagicMock()
        project_id = push_payload["project_id"]
        expected_push = {
            "id": project_id,
            "event_name": push_payload["event_name"],
        }

        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_project = AsyncMock(
            return_value=expected_push
        )

        result = await processor.handle_event(push_payload, resource_config)

        processor._gitlab_webhook_client.get_project.assert_called_once_with(project_id)
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == expected_push
        assert not result.deleted_raw_results
