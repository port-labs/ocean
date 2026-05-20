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
    """Tests for included files enrichment in RepositoryWebhookProcessor."""

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
