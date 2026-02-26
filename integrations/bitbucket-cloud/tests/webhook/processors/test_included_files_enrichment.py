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
from bitbucket_cloud.enrichments.included_files import (
    IncludedFilesEnricher,
    RepositoryIncludedFilesStrategy,
)


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
class TestBitbucketIncludedFilesEnrichment:
    """Tests for the IncludedFilesEnricher with RepositoryIncludedFilesStrategy."""

    async def test_enrich_with_included_files_success(
        self,
        webhook_client_mock: MagicMock,
        sample_repo: dict[str, Any],
    ) -> None:
        """Test enriching a repo with included files successfully fetches content."""
        webhook_client_mock.get_repository_files = AsyncMock(
            side_effect=["# README content", "* @owner"]
        )

        enricher = IncludedFilesEnricher(
            client=webhook_client_mock,
            strategy=RepositoryIncludedFilesStrategy(
                included_files=["README.md", "CODEOWNERS"]
            ),
        )
        result = (await enricher.enrich_batch([sample_repo]))[0]

        assert "__includedFiles" in result
        assert result["__includedFiles"]["README.md"] == "# README content"
        assert result["__includedFiles"]["CODEOWNERS"] == "* @owner"
        assert webhook_client_mock.get_repository_files.call_count == 2
        webhook_client_mock.get_repository_files.assert_any_call(
            "test-repo", "main", "README.md"
        )
        webhook_client_mock.get_repository_files.assert_any_call(
            "test-repo", "main", "CODEOWNERS"
        )

    async def test_enrich_with_included_files_missing_file(
        self,
        webhook_client_mock: MagicMock,
        sample_repo: dict[str, Any],
    ) -> None:
        """Test that missing files are stored as None."""
        webhook_client_mock.get_repository_files = AsyncMock(
            side_effect=["# README content", Exception("404 Not Found")]
        )

        enricher = IncludedFilesEnricher(
            client=webhook_client_mock,
            strategy=RepositoryIncludedFilesStrategy(
                included_files=["README.md", "MISSING.md"]
            ),
        )
        result = (await enricher.enrich_batch([sample_repo]))[0]

        assert result["__includedFiles"]["README.md"] == "# README content"
        assert result["__includedFiles"]["MISSING.md"] is None

    async def test_enrich_with_included_files_empty_list(
        self,
        webhook_client_mock: MagicMock,
        sample_repo: dict[str, Any],
    ) -> None:
        """Test that an empty file list results in no __includedFiles dict."""
        enricher = IncludedFilesEnricher(
            client=webhook_client_mock,
            strategy=RepositoryIncludedFilesStrategy(included_files=[]),
        )
        result = (await enricher.enrich_batch([sample_repo]))[0]

        assert "__includedFiles" not in result

    async def test_enrich_with_included_files_uses_slug(
        self,
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

        enricher = IncludedFilesEnricher(
            client=webhook_client_mock,
            strategy=RepositoryIncludedFilesStrategy(included_files=["README.md"]),
        )
        await enricher.enrich_batch([repo])

        webhook_client_mock.get_repository_files.assert_called_once_with(
            "my-slug", "develop", "README.md"
        )

    async def test_enrich_with_included_files_fallback_branch(
        self,
        webhook_client_mock: MagicMock,
    ) -> None:
        """Test fallback to 'main' when mainbranch is missing."""
        repo = {
            "uuid": "repo-789",
            "slug": "test-repo",
            "name": "Test Repo",
            "mainbranch": {"name": "main"},
        }
        webhook_client_mock.get_repository_files = AsyncMock(
            return_value="file content"
        )

        enricher = IncludedFilesEnricher(
            client=webhook_client_mock,
            strategy=RepositoryIncludedFilesStrategy(included_files=["README.md"]),
        )
        await enricher.enrich_batch([repo])

        webhook_client_mock.get_repository_files.assert_called_once_with(
            "test-repo", "main", "README.md"
        )

    async def test_handle_event_with_included_files(
        self,
        repository_webhook_processor: RepositoryWebhookProcessor,
        webhook_client_mock: MagicMock,
        sample_repo: dict[str, Any],
    ) -> None:
        """Test that handle_event enriches with included files when configured."""
        payload = {"repository": {"uuid": "repo-123"}}
        resource_config = MagicMock()
        resource_config.selector.included_files = ["README.md", "CODEOWNERS"]

        webhook_client_mock.get_repository.return_value = sample_repo
        webhook_client_mock.get_repository_files = AsyncMock(
            side_effect=["# Hello", "* @admin"]
        )

        with patch(
            "bitbucket_cloud.enrichments.included_files.enricher.IncludedFilesEnricher"
        ) as mock_enricher_class:
            mock_enricher = AsyncMock()
            mock_enricher.enrich_batch = AsyncMock(
                return_value=[{**sample_repo, "__includedFiles": {"README.md": "# Hello", "CODEOWNERS": "* @admin"}}]
            )
            mock_enricher_class.return_value = mock_enricher

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
