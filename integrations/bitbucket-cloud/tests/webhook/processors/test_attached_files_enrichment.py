"""Tests for the includedFiles enrichment feature in the Bitbucket Cloud integration."""

import pytest
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)

# Patch the module before importing the class
with patch("initialize_client.init_webhook_client") as mock_init_client:
    from bitbucket_cloud.webhook_processors.processors.repository_webhook_processor import (
        RepositoryWebhookProcessor,
    )

from bitbucket_cloud.webhook_processors.webhook_client import BitbucketWebhookClient


@pytest.fixture
def event() -> WebhookEvent:
    return WebhookEvent(trace_id="test-trace-id", payload={}, headers={})


@pytest.fixture
def webhook_client_mock() -> MagicMock:
    """Create a mocked webhook client."""
    return MagicMock(spec=BitbucketWebhookClient)


@pytest.fixture
def repository_webhook_processor(
    webhook_client_mock: MagicMock, event: WebhookEvent
) -> RepositoryWebhookProcessor:
    """Create a RepositoryWebhookProcessor with mocked webhook client."""
    processor = RepositoryWebhookProcessor(event)
    processor._webhook_client = webhook_client_mock
    return processor


@pytest.fixture
def sample_repo() -> dict[str, Any]:
    return {
        "uuid": "repo-123",
        "slug": "test-repo",
        "name": "Test Repository",
        "mainbranch": {"name": "main"},
        "description": "A test repository",
        "workspace": {"slug": "test-workspace"},
    }


@pytest.mark.asyncio
class TestBitbucketAttachedFilesEnrichment:
    """Tests for included files enrichment in RepositoryWebhookProcessor."""

    async def test_handle_event_with_included_files(
        self,
        repository_webhook_processor: RepositoryWebhookProcessor,
        webhook_client_mock: MagicMock,
        sample_repo: dict[str, Any],
    ) -> None:
        """Test that handle_event enriches with attached files when configured."""
        payload = {"repository": {"uuid": "repo-123"}}
        resource_config = MagicMock()
        resource_config.selector.included_files = ["README.md", "CODEOWNERS"]

        webhook_client_mock.get_repository.return_value = sample_repo
        webhook_client_mock.get_repository_files = AsyncMock(
            side_effect=["# Hello", "* @admin"]
        )

        result = await repository_webhook_processor.handle_event(
            payload, resource_config
        )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 1
        assert "__includedFiles" in result.updated_raw_results[0]
        assert (
            result.updated_raw_results[0]["__includedFiles"]["README.md"] == "# Hello"
        )
        assert (
            result.updated_raw_results[0]["__includedFiles"]["CODEOWNERS"] == "* @admin"
        )

    async def test_handle_event_without_included_files(
        self,
        repository_webhook_processor: RepositoryWebhookProcessor,
        webhook_client_mock: MagicMock,
        sample_repo: dict[str, Any],
    ) -> None:
        """Test that handle_event does not enrich when includedFiles is empty."""
        payload = {"repository": {"uuid": "repo-123"}}
        resource_config = MagicMock()
        resource_config.selector.included_files = []

        webhook_client_mock.get_repository.return_value = sample_repo

        result = await repository_webhook_processor.handle_event(
            payload, resource_config
        )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 1
        assert "__includedFiles" not in result.updated_raw_results[0]
