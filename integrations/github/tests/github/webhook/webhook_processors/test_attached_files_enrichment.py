"""Tests for the attachedFiles enrichment feature in the GitHub integration."""

import pytest
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import (
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from github.webhook.webhook_processors.repository_webhook_processor import (
    RepositoryWebhookProcessor,
)
from integration import GithubRepositoryConfig, GithubRepositorySelector


@pytest.fixture
def mock_webhook_event() -> WebhookEvent:
    return WebhookEvent(trace_id="test-trace-id", payload={}, headers={})


@pytest.fixture
def repository_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> RepositoryWebhookProcessor:
    return RepositoryWebhookProcessor(event=mock_webhook_event)


@pytest.fixture
def sample_repo() -> dict[str, Any]:
    return {
        "id": 1,
        "name": "test-repo",
        "full_name": "test-org/test-repo",
        "owner": {"login": "test-org"},
        "default_branch": "main",
        "description": "A test repository",
    }


@pytest.fixture
def resource_config_with_attached_files() -> GithubRepositoryConfig:
    return GithubRepositoryConfig(
        kind="repository",
        selector=GithubRepositorySelector(
            query="true",
            attachedFiles=["README.md", "CODEOWNERS"],
        ),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".full_name",
                    title=".name",
                    blueprint='"githubRepository"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def resource_config_without_attached_files() -> GithubRepositoryConfig:
    return GithubRepositoryConfig(
        kind="repository",
        selector=GithubRepositorySelector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".full_name",
                    title=".name",
                    blueprint='"githubRepository"',
                    properties={},
                )
            )
        ),
    )


@pytest.mark.asyncio
class TestGithubAttachedFilesEnrichment:
    """Tests for the _enrich_with_attached_files static method on RepositoryWebhookProcessor."""

    async def test_enrich_with_attached_files_success(
        self, sample_repo: dict[str, Any]
    ) -> None:
        """Test enriching a repo with attached files successfully fetches content."""
        mock_rest_client = MagicMock()
        mock_file_exporter = AsyncMock()
        mock_file_exporter.get_resource.side_effect = [
            {"content": "# README content"},
            {"content": "* @owner"},
        ]

        with patch(
            "github.webhook.webhook_processors.repository_webhook_processor.RestFileExporter",
            return_value=mock_file_exporter,
        ):
            result = await RepositoryWebhookProcessor._enrich_with_attached_files(
                mock_rest_client, sample_repo, ["README.md", "CODEOWNERS"]
            )

        assert "__attachedFiles" in result
        assert result["__attachedFiles"]["README.md"] == "# README content"
        assert result["__attachedFiles"]["CODEOWNERS"] == "* @owner"
        assert mock_file_exporter.get_resource.call_count == 2

    async def test_enrich_with_attached_files_missing_file(
        self, sample_repo: dict[str, Any]
    ) -> None:
        """Test that missing files are stored as None."""
        mock_rest_client = MagicMock()
        mock_file_exporter = AsyncMock()
        mock_file_exporter.get_resource.side_effect = [
            {"content": "# README content"},
            Exception("404 Not Found"),
        ]

        with patch(
            "github.webhook.webhook_processors.repository_webhook_processor.RestFileExporter",
            return_value=mock_file_exporter,
        ):
            result = await RepositoryWebhookProcessor._enrich_with_attached_files(
                mock_rest_client, sample_repo, ["README.md", "MISSING.md"]
            )

        assert result["__attachedFiles"]["README.md"] == "# README content"
        assert result["__attachedFiles"]["MISSING.md"] is None

    async def test_enrich_with_attached_files_empty_list(
        self, sample_repo: dict[str, Any]
    ) -> None:
        """Test that an empty file list results in an empty __attachedFiles dict."""
        mock_rest_client = MagicMock()

        result = await RepositoryWebhookProcessor._enrich_with_attached_files(
            mock_rest_client, sample_repo, []
        )

        assert result["__attachedFiles"] == {}

    async def test_enrich_with_attached_files_correct_options(
        self, sample_repo: dict[str, Any]
    ) -> None:
        """Test that FileContentOptions are constructed correctly."""
        mock_rest_client = MagicMock()
        mock_file_exporter = AsyncMock()
        mock_file_exporter.get_resource.return_value = {"content": "file content"}

        with patch(
            "github.webhook.webhook_processors.repository_webhook_processor.RestFileExporter",
            return_value=mock_file_exporter,
        ):
            await RepositoryWebhookProcessor._enrich_with_attached_files(
                mock_rest_client, sample_repo, ["README.md"]
            )

        call_args = mock_file_exporter.get_resource.call_args[0][0]
        assert call_args["organization"] == "test-org"
        assert call_args["repo_name"] == "test-repo"
        assert call_args["file_path"] == "README.md"
        assert call_args["branch"] == "main"

    async def test_handle_event_with_attached_files(
        self,
        repository_webhook_processor: RepositoryWebhookProcessor,
        resource_config_with_attached_files: GithubRepositoryConfig,
        sample_repo: dict[str, Any],
    ) -> None:
        """Test that handle_event enriches with attached files when configured."""
        payload = {
            "action": "created",
            "repository": sample_repo,
            "organization": {"login": "test-org"},
        }

        mock_exporter = AsyncMock()
        mock_exporter.get_resource.return_value = sample_repo

        mock_file_exporter = AsyncMock()
        mock_file_exporter.get_resource.side_effect = [
            {"content": "# Hello"},
            {"content": "* @admin"},
        ]

        with (
            patch(
                "github.webhook.webhook_processors.repository_webhook_processor.RestRepositoryExporter",
                return_value=mock_exporter,
            ),
            patch(
                "github.webhook.webhook_processors.repository_webhook_processor.RestFileExporter",
                return_value=mock_file_exporter,
            ),
        ):
            result = await repository_webhook_processor.handle_event(
                payload, resource_config_with_attached_files
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
        resource_config_without_attached_files: GithubRepositoryConfig,
        sample_repo: dict[str, Any],
    ) -> None:
        """Test that handle_event does not enrich when attachedFiles is empty."""
        payload = {
            "action": "created",
            "repository": sample_repo,
            "organization": {"login": "test-org"},
        }

        mock_exporter = AsyncMock()
        mock_exporter.get_resource.return_value = sample_repo

        with patch(
            "github.webhook.webhook_processors.repository_webhook_processor.RestRepositoryExporter",
            return_value=mock_exporter,
        ):
            result = await repository_webhook_processor.handle_event(
                payload, resource_config_without_attached_files
            )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 1
        assert "__attachedFiles" not in result.updated_raw_results[0]
