import pytest
from unittest.mock import AsyncMock, MagicMock

from github.webhook.webhook_processors.repository_webhook_processor import (
    RepositoryWebhookProcessor,
)
from github.helpers.utils import ObjectKind
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from typing import Any


@pytest.mark.asyncio
class TestRepositoryWebhookProcessor:
    """Test the repository webhook processor"""

    @pytest.fixture
    def mock_event(self) -> WebhookEvent:
        """Create a mock webhook event"""
        return WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-github-event": "repository"},
            payload={},
        )

    @pytest.fixture
    def processor(self, mock_event: WebhookEvent) -> RepositoryWebhookProcessor:
        """Create a RepositoryWebhookProcessor instance"""
        return RepositoryWebhookProcessor(event=mock_event)

    @pytest.fixture
    def repo_payload(self) -> dict[str, Any]:
        """Create a sample repository webhook payload"""
        return {
            "action": "created",
            "repository": {
                "id": 123,
                "full_name": "owner/repo",
                "name": "repo",
                "private": False,
            },
        }

    async def test_get_matching_kinds(
        self, processor: RepositoryWebhookProcessor, mock_event: WebhookEvent
    ) -> None:
        """Test that get_matching_kinds returns the REPOSITORY kind"""
        assert await processor.get_matching_kinds(mock_event) == [ObjectKind.REPOSITORY]

    async def test_handle_event_created(
        self, processor: RepositoryWebhookProcessor, repo_payload: dict[str, Any]
    ) -> None:
        """Test handling a repository created event"""
        resource_config = MagicMock(spec=ResourceConfig)
        expected_repo = {
            "id": 123,
            "full_name": "owner/repo",
            "name": "repo",
            "private": False,
        }

        # Mock the response
        mock_response = MagicMock()
        mock_response.json.return_value = expected_repo

        processor._github_webhook_client = MagicMock()
        processor._github_webhook_client.get_repository = AsyncMock(return_value=mock_response)

        result = await processor.handle_event(repo_payload, resource_config)

        processor._github_webhook_client.get_repository.assert_called_once_with("owner/repo")
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == expected_repo
        assert not result.deleted_raw_results

    async def test_handle_event_deleted(
        self, processor: RepositoryWebhookProcessor, repo_payload: dict[str, Any]
    ) -> None:
        """Test handling a repository deleted event"""
        resource_config = MagicMock(spec=ResourceConfig)
        repo_payload["action"] = "deleted"

        processor._github_webhook_client = MagicMock()

        result = await processor.handle_event(repo_payload, resource_config)

        assert not result.updated_raw_results
        assert len(result.deleted_raw_results) == 1
        assert result.deleted_raw_results[0] == repo_payload["repository"]

    async def test_handle_event_no_full_name(
        self, processor: RepositoryWebhookProcessor
    ) -> None:
        """Test handling event with missing full_name"""
        resource_config = MagicMock(spec=ResourceConfig)
        payload = {
            "action": "created",
            "repository": {
                "id": 123,
                "name": "repo",
                # Missing full_name
            },
        }

        processor._github_webhook_client = MagicMock()

        result = await processor.handle_event(payload, resource_config)

        assert not result.updated_raw_results
        assert not result.deleted_raw_results
