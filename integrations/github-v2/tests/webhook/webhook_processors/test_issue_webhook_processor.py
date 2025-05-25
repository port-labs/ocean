import pytest
from unittest.mock import AsyncMock, MagicMock

from github.webhook.webhook_processors.issue_webhook_processor import (
    IssueWebhookProcessor,
)
from github.helpers.utils import ObjectKind
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from typing import Any


@pytest.mark.asyncio
class TestIssueWebhookProcessor:
    """Test the issue webhook processor"""

    @pytest.fixture
    def mock_event(self) -> WebhookEvent:
        """Create a mock webhook event"""
        return WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-github-event": "issues"},
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
            "action": "opened",
            "issue": {
                "id": 456,
                "number": 123,
                "title": "Test Issue",
                "state": "open",
            },
            "repository": {
                "id": 789,
                "full_name": "owner/repo",
                "name": "repo",
            },
        }

    async def test_get_matching_kinds(
        self, processor: IssueWebhookProcessor, mock_event: WebhookEvent
    ) -> None:
        """Test that get_matching_kinds returns the ISSUE kind"""
        assert await processor.get_matching_kinds(mock_event) == [ObjectKind.ISSUE]

    async def test_handle_event_opened(
        self, processor: IssueWebhookProcessor, issue_payload: dict[str, Any]
    ) -> None:
        """Test handling an issue opened event"""
        resource_config = MagicMock(spec=ResourceConfig)
        expected_issue = {
            "id": 456,
            "number": 123,
            "title": "Test Issue",
            "state": "open",
            "repository": issue_payload["repository"],
        }

        # Mock the response
        mock_response = MagicMock()
        mock_response.json.return_value = expected_issue

        processor._github_webhook_client = MagicMock()
        processor._github_webhook_client.get_issue = AsyncMock(return_value=mock_response)

        result = await processor.handle_event(issue_payload, resource_config)

        processor._github_webhook_client.get_issue.assert_called_once_with(
            "owner/repo", 123
        )
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == expected_issue
        assert not result.deleted_raw_results

    async def test_handle_event_deleted(
        self, processor: IssueWebhookProcessor, issue_payload: dict[str, Any]
    ) -> None:
        """Test handling an issue deleted event"""
        resource_config = MagicMock(spec=ResourceConfig)
        issue_payload["action"] = "deleted"

        processor._github_webhook_client = MagicMock()

        result = await processor.handle_event(issue_payload, resource_config)

        assert not result.updated_raw_results
        assert len(result.deleted_raw_results) == 1
        assert result.deleted_raw_results[0] == issue_payload["issue"]

    async def test_handle_event_api_failure(
        self, processor: IssueWebhookProcessor, issue_payload: dict[str, Any]
    ) -> None:
        """Test handling when API call fails"""
        resource_config = MagicMock(spec=ResourceConfig)

        processor._github_webhook_client = MagicMock()
        processor._github_webhook_client.get_issue = AsyncMock(return_value=None)

        result = await processor.handle_event(issue_payload, resource_config)

        # Should fall back to webhook payload data
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0]["number"] == 123
        assert result.updated_raw_results[0]["repository"] == issue_payload["repository"]

    async def test_validate_payload(self, processor: IssueWebhookProcessor) -> None:
        """Test payload validation"""
        valid_payload = {
            "issue": {"id": 123},
            "repository": {"id": 456},
        }
        assert await processor.validate_payload(valid_payload) is True

        invalid_payload = {
            "repository": {"id": 456},
        }
        assert await processor.validate_payload(invalid_payload) is False
