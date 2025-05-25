import pytest
from unittest.mock import AsyncMock, MagicMock

from github.webhook.webhook_processors.pull_request_webhook_processor import (
    PullRequestWebhookProcessor,
)
from github.helpers.utils import ObjectKind
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from typing import Any


@pytest.mark.asyncio
class TestPullRequestWebhookProcessor:
    """Test the pull request webhook processor"""

    @pytest.fixture
    def mock_event(self) -> WebhookEvent:
        """Create a mock webhook event"""
        return WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-github-event": "pull_request"},
            payload={},
        )

    @pytest.fixture
    def processor(self, mock_event: WebhookEvent) -> PullRequestWebhookProcessor:
        """Create a PullRequestWebhookProcessor instance"""
        return PullRequestWebhookProcessor(event=mock_event)

    @pytest.fixture
    def pr_payload(self) -> dict[str, Any]:
        """Create a sample pull request webhook payload"""
        return {
            "action": "opened",
            "pull_request": {
                "id": 456,
                "number": 123,
                "title": "Test PR",
                "state": "open",
            },
            "repository": {
                "id": 789,
                "full_name": "owner/repo",
                "name": "repo",
            },
        }

    async def test_get_matching_kinds(
        self, processor: PullRequestWebhookProcessor, mock_event: WebhookEvent
    ) -> None:
        """Test that get_matching_kinds returns the PULL_REQUEST kind"""
        assert await processor.get_matching_kinds(mock_event) == [ObjectKind.PULL_REQUEST]

    async def test_handle_event_opened(
        self, processor: PullRequestWebhookProcessor, pr_payload: dict[str, Any]
    ) -> None:
        """Test handling a pull request opened event"""
        resource_config = MagicMock(spec=ResourceConfig)
        expected_pr = {
            "id": 456,
            "number": 123,
            "title": "Test PR",
            "state": "open",
            "repository": pr_payload["repository"],
        }

        # Mock the response
        mock_response = MagicMock()
        mock_response.json.return_value = expected_pr

        processor._github_webhook_client = MagicMock()
        processor._github_webhook_client.get_pull_request = AsyncMock(return_value=mock_response)

        result = await processor.handle_event(pr_payload, resource_config)

        processor._github_webhook_client.get_pull_request.assert_called_once_with(
            "owner/repo", 123
        )
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == expected_pr
        assert not result.deleted_raw_results

    async def test_handle_event_api_failure(
        self, processor: PullRequestWebhookProcessor, pr_payload: dict[str, Any]
    ) -> None:
        """Test handling when API call fails"""
        resource_config = MagicMock(spec=ResourceConfig)

        processor._github_webhook_client = MagicMock()
        processor._github_webhook_client.get_pull_request = AsyncMock(return_value=None)

        result = await processor.handle_event(pr_payload, resource_config)

        # Should fall back to webhook payload data
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0]["number"] == 123
        assert result.updated_raw_results[0]["repository"] == pr_payload["repository"]

    async def test_validate_payload(self, processor: PullRequestWebhookProcessor) -> None:
        """Test payload validation"""
        valid_payload = {
            "pull_request": {"id": 123},
            "repository": {"id": 456},
        }
        assert await processor.validate_payload(valid_payload) is True

        invalid_payload = {
            "repository": {"id": 456},
        }
        assert await processor.validate_payload(invalid_payload) is False
