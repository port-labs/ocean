"""Tests for the attachedFiles enrichment feature in the Bitbucket Cloud integration."""

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
    }


@pytest.mark.asyncio
class TestBitbucketAttachedFilesEnrichment:
    """Tests for the _enrich_with_attached_files method on RepositoryWebhookProcessor."""

    async def test_enrich_with_attached_files_success(
        self,
        repository_webhook_processor: RepositoryWebhookProcessor,
        webhook_client_mock: MagicMock,
        sample_repo: dict[str, Any],
    ) -> None:
        """Test enriching a repo with attached files successfully fetches content."""
        webhook_client_mock.get_repository_files = AsyncMock(
            side_effect=["# README content", "* @owner"]
        )

        result = await repository_webhook_processor._enrich_with_attached_files(
            sample_repo, ["README.md", "CODEOWNERS"]
        )

        assert "__attachedFiles" in result
        assert result["__attachedFiles"]["README.md"] == "# README content"
        assert result["__attachedFiles"]["CODEOWNERS"] == "* @owner"
        assert webhook_client_mock.get_repository_files.call_count == 2
        webhook_client_mock.get_repository_files.assert_any_call(
            "test-repo", "main", "README.md"
        )
        webhook_client_mock.get_repository_files.assert_any_call(
            "test-repo", "main", "CODEOWNERS"
        )

    async def test_enrich_with_attached_files_missing_file(
        self,
        repository_webhook_processor: RepositoryWebhookProcessor,
        webhook_client_mock: MagicMock,
        sample_repo: dict[str, Any],
    ) -> None:
        """Test that missing files are stored as None."""
        webhook_client_mock.get_repository_files = AsyncMock(
            side_effect=["# README content", Exception("404 Not Found")]
        )

        result = await repository_webhook_processor._enrich_with_attached_files(
            sample_repo, ["README.md", "MISSING.md"]
        )

        assert result["__attachedFiles"]["README.md"] == "# README content"
        assert result["__attachedFiles"]["MISSING.md"] is None

    async def test_enrich_with_attached_files_empty_list(
        self,
        repository_webhook_processor: RepositoryWebhookProcessor,
        sample_repo: dict[str, Any],
    ) -> None:
        """Test that an empty file list results in an empty __attachedFiles dict."""
        result = await repository_webhook_processor._enrich_with_attached_files(
            sample_repo, []
        )

        assert result["__attachedFiles"] == {}

    async def test_enrich_with_attached_files_uses_slug(
        self,
        repository_webhook_processor: RepositoryWebhookProcessor,
        webhook_client_mock: MagicMock,
    ) -> None:
        """Test that enrichment correctly uses slug when available."""
        repo = {
            "uuid": "repo-456",
            "slug": "my-slug",
            "name": "My Repo Name",
            "mainbranch": {"name": "develop"},
        }
        webhook_client_mock.get_repository_files = AsyncMock(
            return_value="file content"
        )

        await repository_webhook_processor._enrich_with_attached_files(
            repo, ["README.md"]
        )

        webhook_client_mock.get_repository_files.assert_called_once_with(
            "my-slug", "develop", "README.md"
        )

    async def test_enrich_with_attached_files_fallback_branch(
        self,
        repository_webhook_processor: RepositoryWebhookProcessor,
        webhook_client_mock: MagicMock,
    ) -> None:
        """Test fallback to 'main' when mainbranch is missing."""
        repo = {
            "uuid": "repo-789",
            "slug": "test-repo",
            "name": "Test Repo",
        }
        webhook_client_mock.get_repository_files = AsyncMock(
            return_value="file content"
        )

        await repository_webhook_processor._enrich_with_attached_files(
            repo, ["README.md"]
        )

        webhook_client_mock.get_repository_files.assert_called_once_with(
            "test-repo", "main", "README.md"
        )

    async def test_handle_event_with_attached_files(
        self,
        repository_webhook_processor: RepositoryWebhookProcessor,
        webhook_client_mock: MagicMock,
        sample_repo: dict[str, Any],
    ) -> None:
        """Test that handle_event enriches with attached files when configured."""
        payload = {"repository": {"uuid": "repo-123"}}
        resource_config = MagicMock()
        resource_config.selector.attached_files = ["README.md", "CODEOWNERS"]

        webhook_client_mock.get_repository.return_value = sample_repo
        webhook_client_mock.get_repository_files = AsyncMock(
            side_effect=["# Hello", "* @admin"]
        )

        result = await repository_webhook_processor.handle_event(
            payload, resource_config
        )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 1
        assert "__attachedFiles" in result.updated_raw_results[0]
        assert result.updated_raw_results[0]["__attachedFiles"]["README.md"] == "# Hello"
        assert (
            result.updated_raw_results[0]["__attachedFiles"]["CODEOWNERS"] == "* @admin"
        )

    async def test_handle_event_without_attached_files(
        self,
        repository_webhook_processor: RepositoryWebhookProcessor,
        webhook_client_mock: MagicMock,
        sample_repo: dict[str, Any],
    ) -> None:
        """Test that handle_event does not enrich when attachedFiles is empty."""
        payload = {"repository": {"uuid": "repo-123"}}
        resource_config = MagicMock()
        resource_config.selector.attached_files = []

        webhook_client_mock.get_repository.return_value = sample_repo

        result = await repository_webhook_processor.handle_event(
            payload, resource_config
        )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 1
        assert "__attachedFiles" not in result.updated_raw_results[0]
