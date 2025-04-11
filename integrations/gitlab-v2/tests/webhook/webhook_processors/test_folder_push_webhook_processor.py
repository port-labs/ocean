import pytest
from unittest.mock import AsyncMock, MagicMock

from gitlab.webhook.webhook_processors.folder_push_webhook_processor import (
    FolderPushWebhookProcessor,
)
from gitlab.helpers.utils import ObjectKind
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from typing import Any, AsyncGenerator


@pytest.mark.asyncio
class TestFolderPushWebhookProcessor:
    """Test the folder push webhook processor"""

    @pytest.fixture
    def mock_event(self) -> WebhookEvent:
        """Create a mock webhook event"""
        return WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "Push Hook"},
            payload={},
        )

    @pytest.fixture
    def processor(self, mock_event: WebhookEvent) -> FolderPushWebhookProcessor:
        """Create a FolderPushWebhookProcessor instance"""
        processor = FolderPushWebhookProcessor(event=mock_event)
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
                    "added": ["src/folder1/"],
                    "modified": ["src/folder1/data.txt"],
                }
            ],
        }

    @pytest.fixture
    def mock_folder_pattern(self) -> MagicMock:
        """Mock the FolderPattern class with default no-repos config"""
        folder_pattern = MagicMock()
        folder_pattern.path = "src/folder1"
        folder_pattern.repos = None
        return folder_pattern

    @pytest.fixture
    def mock_gitlab_folder_selector(self, mock_folder_pattern: MagicMock) -> MagicMock:
        """Mock the GitlabFolderSelector class"""
        gitlab_folder_selector = MagicMock()
        gitlab_folder_selector.folders = [mock_folder_pattern]
        return gitlab_folder_selector

    @pytest.fixture
    def resource_config(self, mock_gitlab_folder_selector: MagicMock) -> ResourceConfig:
        """Create a mocked GitLabFoldersResourceConfig with default no-repos config"""
        config = MagicMock(spec=ResourceConfig)
        config.selector = mock_gitlab_folder_selector
        config.kind = "folder"
        return config

    async def test_get_matching_kinds(
        self, processor: FolderPushWebhookProcessor, mock_event: WebhookEvent
    ) -> None:
        """Test that get_matching_kinds returns the FOLDER kind"""
        assert await processor.get_matching_kinds(mock_event) == [ObjectKind.FOLDER]

    async def test_handle_event_with_matching_repo(
        self,
        processor: FolderPushWebhookProcessor,
        push_payload: dict[str, Any],
    ) -> None:
        """Test handling a push event when repo and branch match"""
        # Mock FolderPattern with matching repo
        folder_pattern = MagicMock()
        folder_pattern.path = "src/folder1"
        repo = MagicMock()
        repo.name = "getport-labs/project7"
        repo.branch = "main"
        folder_pattern.repos = [repo]

        # Mock GitlabFolderSelector
        gitlab_folder_selector = MagicMock()
        gitlab_folder_selector.folders = [folder_pattern]

        # Mock ResourceConfig
        resource_config = MagicMock(spec=ResourceConfig)
        resource_config.selector = gitlab_folder_selector
        resource_config.kind = "folder"

        # Mock folder data
        folder_data = [
            {
                "project_id": str(push_payload["project_id"]),
                "path": "src/folder1",
                "ref": push_payload["after"],
                "content": ["data.txt"],
            }
        ]

        # Define async generator for folders
        async def folder_generator() -> AsyncGenerator[list[dict[str, Any]], None]:
            yield folder_data

        processor._gitlab_webhook_client = MagicMock()
        generator = folder_generator()
        processor._gitlab_webhook_client.get_repository_folders = MagicMock(
            return_value=generator
        )

        result = await processor.handle_event(push_payload, resource_config)

        # Verify folder fetching
        processor._gitlab_webhook_client.get_repository_folders.assert_called_once_with(
            path="src/folder1",
            repository="getport-labs/project7",
            branch="main",
        )

        # Verify results
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results == folder_data
        assert not result.deleted_raw_results

    async def test_handle_event_with_non_matching_repo(
        self,
        processor: FolderPushWebhookProcessor,
        push_payload: dict[str, Any],
    ) -> None:
        """Test handling a push event when repo doesn't match"""
        # Mock FolderPattern with non-matching repo
        folder_pattern = MagicMock()
        folder_pattern.path = "src/folder1"
        repo = MagicMock()
        repo.name = "other/repo"
        repo.branch = "main"
        folder_pattern.repos = [repo]

        # Mock GitlabFolderSelector
        gitlab_folder_selector = MagicMock()
        gitlab_folder_selector.folders = [folder_pattern]

        # Mock ResourceConfig
        resource_config = MagicMock(spec=ResourceConfig)
        resource_config.selector = gitlab_folder_selector
        resource_config.kind = "folder"

        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_repository_folders = AsyncMock()

        result = await processor.handle_event(push_payload, resource_config)

        # Verify no folders are processed
        processor._gitlab_webhook_client.get_repository_folders.assert_not_called()
        assert not result.updated_raw_results
        assert not result.deleted_raw_results

    async def test_handle_event_with_non_matching_branch(
        self,
        processor: FolderPushWebhookProcessor,
        push_payload: dict[str, Any],
    ) -> None:
        """Test handling a push event when branch doesn't match"""
        # Mock FolderPattern with matching repo but non-matching branch
        folder_pattern = MagicMock()
        folder_pattern.path = "src/folder1"
        repo = MagicMock()
        repo.name = "getport-labs/project7"
        repo.branch = "develop"
        folder_pattern.repos = [repo]

        # Mock GitlabFolderSelector
        gitlab_folder_selector = MagicMock()
        gitlab_folder_selector.folders = [folder_pattern]

        # Mock ResourceConfig
        resource_config = MagicMock(spec=ResourceConfig)
        resource_config.selector = gitlab_folder_selector
        resource_config.kind = "folder"

        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_repository_folders = AsyncMock()

        result = await processor.handle_event(push_payload, resource_config)

        # Verify no folders are processed
        processor._gitlab_webhook_client.get_repository_folders.assert_not_called()
        assert not result.updated_raw_results
        assert not result.deleted_raw_results
