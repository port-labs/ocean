import pytest
from unittest.mock import AsyncMock, MagicMock

from gitlab.webhook.webhook_processors.file_push_webhook_processor import (
    FilePushWebhookProcessor,
)
from gitlab.helpers.utils import ObjectKind
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from typing import Any


@pytest.mark.asyncio
class TestFilePushWebhookProcessor:
    """Test the file push webhook processor"""

    @pytest.fixture
    def mock_event(self) -> WebhookEvent:
        """Create a mock webhook event"""
        return WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "Push Hook"},
            payload={},
        )

    @pytest.fixture
    def processor(self, mock_event: WebhookEvent) -> FilePushWebhookProcessor:
        """Create a FilePushWebhookProcessor instance"""
        processor = FilePushWebhookProcessor(event=mock_event)
        # Don't initialize the client here - we'll do it in each test
        return processor

    @pytest.fixture
    def push_payload(self) -> dict[str, Any]:
        """Create a sample push webhook payload"""
        return {
            "object_kind": "push",
            "event_name": "push",
            "before": "abc123",
            "after": "def456",
            "ref": "refs/heads/main",
            "checkout_sha": "def456",
            "user_id": 1,
            "user_name": "Test User",
            "project_id": 68204746,
            "project": {
                "id": 68204746,
                "name": "project7",
                "path_with_namespace": "getport-labs/project7",
                "url": "https://gitlab.example.com/getport-labs/project7.git",
                "description": "Test repository",
                "homepage": "https://gitlab.example.com/getport-labs/project7",
            },
            "commits": [
                {
                    "id": "def4567890",
                    "added": ["package.json"],
                    "modified": ["src/data.json", "readme.md"],
                }
            ],
        }

    @pytest.fixture
    def mock_files_selector(self) -> MagicMock:
        """Mock the FilesSelector class with default no-repos config"""
        files_selector = MagicMock()
        files_selector.path = "*.json"
        files_selector.repos = None  # Default case: no repos provided
        files_selector.skip_parsing = False
        return files_selector

    @pytest.fixture
    def mock_gitlab_files_selector(self, mock_files_selector: MagicMock) -> MagicMock:
        """Mock the GitLabFilesSelector class"""
        gitlab_files_selector = MagicMock()
        gitlab_files_selector.files = mock_files_selector
        return gitlab_files_selector

    @pytest.fixture
    def resource_config(self, mock_gitlab_files_selector: MagicMock) -> ResourceConfig:
        """Create a mocked GitLabFilesResourceConfig with default no-repos config"""
        config = MagicMock(spec=ResourceConfig)
        config.selector = mock_gitlab_files_selector
        config.kind = "file"
        return config

    async def test_get_matching_kinds(
        self, processor: FilePushWebhookProcessor, mock_event: WebhookEvent
    ) -> None:
        """Test that get_matching_kinds returns the FILE kind"""
        assert await processor.get_matching_kinds(mock_event) == [ObjectKind.FILE]

    async def test_handle_event_with_no_repos(
        self,
        processor: FilePushWebhookProcessor,
        push_payload: dict[str, Any],
        resource_config: ResourceConfig,
    ) -> None:
        """Test handling a push event with *.json path and no repos specified"""
        project_id = push_payload["project_id"]

        # Mock file data returned by _process_file_batch
        file_data = [
            {
                "project_id": str(project_id),
                "path": "package.json",
                "ref": push_payload["after"],
                "content": {"name": "my-app", "version": "1.0.0"},
            },
            {
                "project_id": str(project_id),
                "path": "src/data.json",
                "ref": push_payload["after"],
                "content": {"key": "value"},
            },
        ]

        # Mock enriched data returned by _enrich_files_with_repos
        enriched_data = [
            {"file": file_data[0], "repo": push_payload["project"]},
            {"file": file_data[1], "repo": push_payload["project"]},
        ]

        # Create a fresh MagicMock for the client
        processor._gitlab_webhook_client = MagicMock()

        # Assign AsyncMock objects with return values to methods
        processor._gitlab_webhook_client._process_file_batch = AsyncMock(
            return_value=file_data
        )
        processor._gitlab_webhook_client._enrich_files_with_repos = AsyncMock(
            return_value=enriched_data
        )

        result = await processor.handle_event(push_payload, resource_config)

        # Verify _enrich_files_with_repos was called with processed batch
        processor._gitlab_webhook_client._enrich_files_with_repos.assert_called_once_with(
            file_data
        )

        # Verify results
        assert len(result.updated_raw_results) == 2
        assert result.updated_raw_results == enriched_data
        assert not result.deleted_raw_results

    async def test_handle_event_with_matching_repo(
        self, processor: FilePushWebhookProcessor, push_payload: dict[str, Any]
    ) -> None:
        """Test handling a push event when repo matches configured repos"""
        # Mock FilesSelector with matching repo
        files_selector = MagicMock()
        files_selector.path = "*.json"
        files_selector.repos = ["getport-labs/project7"]  # Matches payload repo
        files_selector.skip_parsing = False

        # Mock GitLabFilesSelector
        gitlab_files_selector = MagicMock()
        gitlab_files_selector.files = files_selector

        # Mock ResourceConfig
        resource_config = MagicMock(spec=ResourceConfig)
        resource_config.selector = gitlab_files_selector
        resource_config.kind = "file"

        project_id = push_payload["project_id"]

        # Mock file data returned by _process_file_batch
        file_data = [
            {
                "project_id": str(project_id),
                "path": "package.json",
                "ref": push_payload["after"],
                "content": {"name": "my-app", "version": "1.0.0"},
            },
            {
                "project_id": str(project_id),
                "path": "src/data.json",
                "ref": push_payload["after"],
                "content": {"key": "value"},
            },
        ]

        # Mock enriched data returned by _enrich_files_with_repos
        enriched_data = [
            {"file": file_data[0], "repo": push_payload["project"]},
            {"file": file_data[1], "repo": push_payload["project"]},
        ]

        processor._gitlab_webhook_client = MagicMock()

        # Assign AsyncMock objects with return values to methods
        processor._gitlab_webhook_client._process_file_batch = AsyncMock(
            return_value=file_data
        )
        processor._gitlab_webhook_client._enrich_files_with_repos = AsyncMock(
            return_value=enriched_data
        )

        result = await processor.handle_event(push_payload, resource_config)

        # Verify _process_file_batch was called with correct file batch
        expected_file_batch = [
            {
                "project_id": str(project_id),
                "path": "package.json",
                "ref": push_payload["after"],
            },
            {
                "project_id": str(project_id),
                "path": "src/data.json",
                "ref": push_payload["after"],
            },
        ]
        processor._gitlab_webhook_client._process_file_batch.assert_called_once_with(
            expected_file_batch, context=f"project:{project_id}", skip_parsing=False
        )

        # Verify _enrich_files_with_repos was called with processed batch
        processor._gitlab_webhook_client._enrich_files_with_repos.assert_called_once_with(
            file_data
        )

        # Verify results
        assert len(result.updated_raw_results) == 2
        assert result.updated_raw_results == enriched_data
        assert not result.deleted_raw_results

    async def test_handle_event_with_non_matching_repo(
        self, processor: FilePushWebhookProcessor, push_payload: dict[str, Any]
    ) -> None:
        """Test handling a push event when repo doesn't match configured repos"""
        # Mock FilesSelector with non-matching repo
        files_selector = MagicMock()
        files_selector.path = "*.json"
        files_selector.repos = ["other/repo"]
        files_selector.skip_parsing = False

        # Mock GitLabFilesSelector
        gitlab_files_selector = MagicMock()
        gitlab_files_selector.files = files_selector

        # Mock ResourceConfig
        resource_config = MagicMock(spec=ResourceConfig)
        resource_config.selector = gitlab_files_selector
        resource_config.kind = "file"

        processor._gitlab_webhook_client = MagicMock()

        processor._gitlab_webhook_client._process_file_batch = AsyncMock()
        processor._gitlab_webhook_client._enrich_files_with_repos = AsyncMock()

        result = await processor.handle_event(push_payload, resource_config)

        # Verify no processing happens
        processor._gitlab_webhook_client._process_file_batch.assert_not_called()
        processor._gitlab_webhook_client._enrich_files_with_repos.assert_not_called()
        assert not result.updated_raw_results
        assert not result.deleted_raw_results
