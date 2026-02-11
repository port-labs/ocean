"""Tests for the includedFiles enrichment feature in the Azure DevOps integration."""

import pytest
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock

from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from azure_devops.webhooks.webhook_processors.repository_processor import (
    RepositoryWebhookProcessor,
)
from azure_devops.client.azure_devops_client import AzureDevopsClient


@pytest.fixture
def mock_client() -> MagicMock:
    """Create a mocked AzureDevopsClient."""
    return MagicMock(spec=AzureDevopsClient)


@pytest.fixture
def sample_repo() -> Dict[str, Any]:
    return {
        "id": "repo-123",
        "name": "test-repo",
        "defaultBranch": "refs/heads/main",
        "project": {"id": "project-1", "name": "TestProject"},
    }


@pytest.fixture
def sample_repo_no_branch() -> Dict[str, Any]:
    return {
        "id": "repo-456",
        "name": "another-repo",
        "project": {"id": "project-2", "name": "AnotherProject"},
    }


@pytest.mark.asyncio
class TestAzureDevopsIncludedFilesEnrichment:
    """Tests for the _enrich_with_included_files static method on RepositoryWebhookProcessor."""

    async def test_enrich_with_included_files_success(
        self,
        mock_client: MagicMock,
        sample_repo: Dict[str, Any],
    ) -> None:
        """Test enriching a repo with included files successfully fetches content."""
        mock_client.get_file_by_branch = AsyncMock(
            side_effect=[b"# README content", b"* @owner"]
        )

        result = await RepositoryWebhookProcessor._enrich_with_included_files(
            mock_client, sample_repo, ["README.md", "CODEOWNERS"]
        )

        assert "__includedFiles" in result
        assert result["__includedFiles"]["README.md"] == "# README content"
        assert result["__includedFiles"]["CODEOWNERS"] == "* @owner"
        assert mock_client.get_file_by_branch.call_count == 2
        mock_client.get_file_by_branch.assert_any_call("README.md", "repo-123", "main")
        mock_client.get_file_by_branch.assert_any_call("CODEOWNERS", "repo-123", "main")

    async def test_enrich_with_included_files_missing_file(
        self,
        mock_client: MagicMock,
        sample_repo: Dict[str, Any],
    ) -> None:
        """Test that missing files are stored as None."""
        mock_client.get_file_by_branch = AsyncMock(
            side_effect=[b"# README content", Exception("404 Not Found")]
        )

        result = await RepositoryWebhookProcessor._enrich_with_included_files(
            mock_client, sample_repo, ["README.md", "MISSING.md"]
        )

        assert result["__includedFiles"]["README.md"] == "# README content"
        assert result["__includedFiles"]["MISSING.md"] is None

    async def test_enrich_with_included_files_empty_list(
        self,
        mock_client: MagicMock,
        sample_repo: Dict[str, Any],
    ) -> None:
        """Test that an empty file list results in an empty __includedFiles dict."""
        result = await RepositoryWebhookProcessor._enrich_with_included_files(
            mock_client, sample_repo, []
        )

        assert result["__includedFiles"] == {}

    async def test_enrich_with_included_files_strips_refs_heads(
        self,
        mock_client: MagicMock,
    ) -> None:
        """Test that refs/heads/ prefix is stripped from defaultBranch."""
        repo = {
            "id": "repo-789",
            "name": "test-repo",
            "defaultBranch": "refs/heads/develop",
        }
        mock_client.get_file_by_branch = AsyncMock(return_value=b"content")

        await RepositoryWebhookProcessor._enrich_with_included_files(
            mock_client, repo, ["README.md"]
        )

        mock_client.get_file_by_branch.assert_called_once_with(
            "README.md", "repo-789", "develop"
        )

    async def test_enrich_with_included_files_default_branch_fallback(
        self,
        mock_client: MagicMock,
        sample_repo_no_branch: Dict[str, Any],
    ) -> None:
        """Test fallback to refs/heads/main when defaultBranch is missing."""
        mock_client.get_file_by_branch = AsyncMock(return_value=b"content")

        await RepositoryWebhookProcessor._enrich_with_included_files(
            mock_client, sample_repo_no_branch, ["README.md"]
        )

        mock_client.get_file_by_branch.assert_called_once_with(
            "README.md", "repo-456", "main"
        )

    async def test_enrich_with_included_files_decodes_bytes(
        self,
        mock_client: MagicMock,
        sample_repo: Dict[str, Any],
    ) -> None:
        """Test that bytes content is decoded to UTF-8 string."""
        mock_client.get_file_by_branch = AsyncMock(
            return_value="héllo wörld".encode("utf-8")
        )

        result = await RepositoryWebhookProcessor._enrich_with_included_files(
            mock_client, sample_repo, ["file.txt"]
        )

        assert result["__includedFiles"]["file.txt"] == "héllo wörld"

    async def test_enrich_with_included_files_none_content(
        self,
        mock_client: MagicMock,
        sample_repo: Dict[str, Any],
    ) -> None:
        """Test that None content from get_file_by_branch is stored as None."""
        mock_client.get_file_by_branch = AsyncMock(return_value=None)

        result = await RepositoryWebhookProcessor._enrich_with_included_files(
            mock_client, sample_repo, ["file.txt"]
        )

        assert result["__includedFiles"]["file.txt"] is None

    async def test_handle_event_with_included_files(
        self,
        mock_client: MagicMock,
        sample_repo: Dict[str, Any],
        event: WebhookEvent,
        mock_event_context: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that handle_event enriches with included files when configured."""
        monkeypatch.setattr(
            "azure_devops.webhooks.webhook_processors.repository_processor.AzureDevopsClient.create_from_ocean_config",
            lambda: mock_client,
        )

        mock_client.get_repository = AsyncMock(return_value=sample_repo)
        mock_client.get_file_by_branch = AsyncMock(
            side_effect=[b"# Hello", b"* @admin"]
        )

        processor = RepositoryWebhookProcessor(event)
        payload = {
            "eventType": "git.push",
            "publisherId": "tfs",
            "resource": {
                "url": "http://example.com",
                "repository": {"id": "repo-123"},
            },
        }

        resource_config = MagicMock()
        resource_config.selector.included_files = ["README.md", "CODEOWNERS"]

        result = await processor.handle_event(payload, resource_config)

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
        mock_client: MagicMock,
        sample_repo: Dict[str, Any],
        event: WebhookEvent,
        mock_event_context: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that handle_event does not enrich when includedFiles is empty."""
        monkeypatch.setattr(
            "azure_devops.webhooks.webhook_processors.repository_processor.AzureDevopsClient.create_from_ocean_config",
            lambda: mock_client,
        )

        mock_client.get_repository = AsyncMock(return_value=sample_repo)

        processor = RepositoryWebhookProcessor(event)
        payload = {
            "eventType": "git.push",
            "publisherId": "tfs",
            "resource": {
                "url": "http://example.com",
                "repository": {"id": "repo-123"},
            },
        }

        resource_config = MagicMock()
        resource_config.selector.included_files = []

        result = await processor.handle_event(payload, resource_config)

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 1
        assert "__includedFiles" not in result.updated_raw_results[0]
