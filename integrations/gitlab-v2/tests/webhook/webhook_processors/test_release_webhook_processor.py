import pytest
from unittest.mock import AsyncMock, MagicMock

from gitlab.webhook.webhook_processors.release_webhook_processor import (
    ReleaseWebhookProcessor,
)
from gitlab.helpers.utils import ObjectKind

from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
)
from typing import Any


@pytest.mark.asyncio
class TestReleaseWebhookProcessor:
    """Test the release webhook processor"""

    @pytest.fixture
    def mock_event(self) -> WebhookEvent:
        """Create a mock webhook event"""
        return WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "release"},
            payload={},
        )

    @pytest.fixture
    def processor(self, mock_event: WebhookEvent) -> ReleaseWebhookProcessor:
        """Create a ReleaseWebhookProcessor instance"""
        return ReleaseWebhookProcessor(event=mock_event)

    @pytest.fixture
    def release_payload(self) -> dict[str, Any]:
        """Create a sample release webhook payload"""
        return {
            "object_kind": "release",
            "event_name": "release",
            "tag": "v1.0.0",
            "action": "create",
            "project": {
                "id": 123,
                "name": "test-repo",
                "path_with_namespace": "test/test-repo",
                "url": "https://gitlab.example.com/test/test-repo.git",
                "description": "Test repository",
                "homepage": "https://gitlab.example.com/test/test-repo",
            },
            "release": {
                "tag_name": "v1.0.0",
                "name": "Version 1.0.0",
                "description": "First release",
                "created_at": "2023-01-01T00:00:00Z",
            },
        }

    async def test_get_matching_kinds(
        self, processor: ReleaseWebhookProcessor, mock_event: WebhookEvent
    ) -> None:
        """Test that get_matching_kinds returns the RELEASE kind."""
        assert await processor.get_matching_kinds(mock_event) == [ObjectKind.RELEASE]

    async def test_handle_event(
        self, processor: ReleaseWebhookProcessor, release_payload: dict[str, Any]
    ) -> None:
        """Test handling a release event"""
        resource_config = MagicMock()
        project_id = release_payload["project"]["id"]
        tag_name = release_payload["tag"]
        project_path = release_payload["project"]["path_with_namespace"]
        expected_release_from_api = {
            "tag_name": tag_name,
            "name": "Version 1.0.0",
            "project_id": project_id,
        }

        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_release = AsyncMock(
            return_value=expected_release_from_api
        )

        result = await processor.handle_event(release_payload, resource_config)

        processor._gitlab_webhook_client.get_release.assert_called_once_with(
            project_id=project_id,
            tag_name=tag_name,
        )
        assert len(result.updated_raw_results) == 1
        # Verify that __project was added to the release
        assert result.updated_raw_results[0]["tag_name"] == tag_name
        assert result.updated_raw_results[0]["__project"] == {
            "path_with_namespace": project_path
        }
        assert not result.deleted_raw_results
