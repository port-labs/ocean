import pytest
from unittest.mock import MagicMock, AsyncMock

from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from gitlab.webhook.webhook_processors.merge_request_webhook_processor import (
    MergeRequestWebhookProcessor,
)
from gitlab.helpers.utils import ObjectKind

from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
)
from typing import Any


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Initialize mock Ocean context for all tests"""
    try:
        mock_app = MagicMock()
        mock_app.config.integration.config = {
            "gitlab_host": "https://gitlab.example.com",
            "gitlab_token": "test-token",
        }
        mock_app.cache_provider = AsyncMock()
        mock_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.mark.asyncio
class TestMergeRequestWebhookProcessor:
    """Test the merge request webhook processor"""

    @pytest.fixture
    def mock_event(self) -> WebhookEvent:
        """Create a mock webhook event"""
        return WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "merge_request"},
            payload={},
        )

    @pytest.fixture
    def processor(self, mock_event: WebhookEvent) -> MergeRequestWebhookProcessor:
        """Create a MergeRequestWebhookProcessor instance"""
        return MergeRequestWebhookProcessor(event=mock_event)

    @pytest.fixture
    def mr_payload(self) -> dict[str, Any]:
        """Create a sample merge request webhook payload"""
        return {
            "object_kind": "merge_request",
            "event_type": "merge_request",
            "user": {"name": "Test User", "username": "testuser"},
            "project": {"id": 123, "name": "Test Project"},
            "object_attributes": {
                "id": 456,
                "iid": 1,
                "title": "Test MR",
                "description": "Test description",
                "state": "opened",
                "created_at": "2023-01-01T12:00:00Z",
                "updated_at": "2023-01-01T12:00:00Z",
            },
            "changes": {},
        }

    async def test_get_matching_kinds(
        self, processor: MergeRequestWebhookProcessor, mock_event: WebhookEvent
    ) -> None:
        """Test that get_matching_kinds returns the MERGE_REQUEST kind."""
        assert await processor.get_matching_kinds(mock_event) == [
            ObjectKind.MERGE_REQUEST
        ]

    async def test_handle_event(
        self, processor: MergeRequestWebhookProcessor, mr_payload: dict[str, Any]
    ) -> None:
        """Test handling a merge request event"""
        resource_config = MagicMock()
        project_id = mr_payload["project"]["id"]
        mr_id = mr_payload["object_attributes"]["id"]
        expected_mr = {
            "id": mr_id,
            "object_kind": "merge_request",
            "event_type": "merge_request",
        }

        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_merge_request = AsyncMock(
            return_value=expected_mr
        )

        result = await processor.handle_event(mr_payload, resource_config)

        processor._gitlab_webhook_client.get_merge_request.assert_called_once_with(
            project_id, mr_id
        )
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == expected_mr
        assert not result.deleted_raw_results
