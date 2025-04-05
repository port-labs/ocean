import pytest
from unittest.mock import AsyncMock, MagicMock

from gitlab.webhook.webhook_processors.issue_webhook_processor import (
    IssueWebhookProcessor,
)
from gitlab.helpers.utils import ObjectKind

from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
)

from typing import Any


@pytest.mark.asyncio
class TestIssueWebhookProcessor:
    """Test the issue webhook processor"""

    @pytest.fixture
    def mock_event(self) -> WebhookEvent:
        """Create a mock webhook event"""
        return WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "issue"},
            payload={},
        )

    @pytest.fixture
    def processor(self, mock_event: WebhookEvent) -> IssueWebhookProcessor:
        """Create an IssueWebhookProcessor instance"""
        return IssueWebhookProcessor(event=mock_event)

    @pytest.fixture
    def issue_payload(self) -> dict[str, Any]:
        """Create a sample issue webhook payload"""
        return {
            "object_kind": "issue",
            "event_type": "issue",
            "user": {"name": "Test User", "username": "testuser"},
            "project": {"id": 123, "name": "Test Project"},
            "object_attributes": {
                "id": 456,
                "iid": 1,
            },
        }

    async def test_get_matching_kinds(
        self, processor: IssueWebhookProcessor, mock_event: WebhookEvent
    ) -> None:
        """Test that get_matching_kinds returns the ISSUE kind."""
        assert await processor.get_matching_kinds(mock_event) == [ObjectKind.ISSUE]

    async def test_handle_event(
        self, processor: IssueWebhookProcessor, issue_payload: dict[str, Any]
    ) -> None:
        """Test handling an issue event"""
        resource_config = MagicMock()
        project_id = issue_payload["project"]["id"]
        issue_id = issue_payload["object_attributes"]["iid"]
        expected_issue = {
            "id": issue_id,
            "object_kind": "issue",
            "event_type": "issue",
        }
        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_issue = AsyncMock(
            return_value=expected_issue
        )

        result = await processor.handle_event(issue_payload, resource_config)

        processor._gitlab_webhook_client.get_issue.assert_called_once_with(
            project_id, issue_id
        )
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == expected_issue
        assert not result.deleted_raw_results
