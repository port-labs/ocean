import pytest
from unittest.mock import AsyncMock, MagicMock

from gitlab.webhook.webhook_processors.tag_webhook_processor import (
    TagWebhookProcessor,
)
from gitlab.helpers.utils import ObjectKind

from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
)
from typing import Any


@pytest.mark.asyncio
class TestTagWebhookProcessor:
    """Test the tag webhook processor"""

    @pytest.fixture
    def mock_event(self) -> WebhookEvent:
        """Create a mock webhook event"""
        return WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "tag_push"},
            payload={},
        )

    @pytest.fixture
    def processor(self, mock_event: WebhookEvent) -> TagWebhookProcessor:
        """Create a TagWebhookProcessor instance"""
        return TagWebhookProcessor(event=mock_event)

    @pytest.fixture
    def tag_payload(self) -> dict[str, Any]:
        """Create a sample tag webhook payload"""
        return {
            "object_kind": "tag_push",
            "event_name": "tag_push",
            "before": "0000000000000000000000000000000000000000",
            "after": "abc123def456",
            "ref": "refs/tags/v1.0.0",
            "checkout_sha": "abc123def456",
            "user_id": 1,
            "user_name": "Test User",
            "project_id": 123,
            "project": {
                "id": 123,
                "name": "test-repo",
                "path_with_namespace": "test/test-repo",
                "url": "https://gitlab.example.com/test/test-repo.git",
                "description": "Test repository",
                "homepage": "https://gitlab.example.com/test/test-repo",
            },
        }

    async def test_get_matching_kinds(
        self, processor: TagWebhookProcessor, mock_event: WebhookEvent
    ) -> None:
        """Test that get_matching_kinds returns the TAG kind."""
        assert await processor.get_matching_kinds(mock_event) == [ObjectKind.TAG]

    async def test_handle_event(
        self, processor: TagWebhookProcessor, tag_payload: dict[str, Any]
    ) -> None:
        """Test handling a tag event"""
        resource_config = MagicMock()
        project_id = tag_payload["project"]["id"]
        tag_name = "v1.0.0"  # Extracted from refs/tags/v1.0.0
        project_path = tag_payload["project"]["path_with_namespace"]
        expected_tag_from_api = {
            "name": tag_name,
            "project_id": project_id,
            "target": tag_payload["after"],
        }

        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_tag = AsyncMock(
            return_value=expected_tag_from_api
        )
        processor._gitlab_webhook_client.enrich_with_project_path = MagicMock(
            return_value={
                **expected_tag_from_api,
                "__project": {"path_with_namespace": project_path},
            }
        )

        result = await processor.handle_event(tag_payload, resource_config)

        processor._gitlab_webhook_client.get_tag.assert_called_once_with(
            project_id=project_id,
            tag_name=tag_name,
        )
        assert len(result.updated_raw_results) == 1
        # Verify that __project was added to the tag
        assert result.updated_raw_results[0]["name"] == tag_name
        assert result.updated_raw_results[0]["__project"] == {
            "path_with_namespace": project_path
        }
        assert not result.deleted_raw_results
