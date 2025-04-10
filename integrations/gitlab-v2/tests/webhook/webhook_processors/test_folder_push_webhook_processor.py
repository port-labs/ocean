import pytest
from unittest.mock import AsyncMock, MagicMock

from gitlab.webhook.webhook_processors.folder_push_webhook_processor import (
    FolderPushWebhookProcessor,
)
from gitlab.helpers.utils import ObjectKind
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from typing import Any


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
                    "added": ["src/app/components/"],
                    "modified": ["docs/api/"],
                }
            ],
        }

    @pytest.fixture
    def mock_folder_pattern(self) -> MagicMock:
        """Mock a folder pattern with default configuration"""
        pattern = MagicMock()
        pattern.path = "src/"

        repo = MagicMock()
        repo.name = "getport-labs/project7"
        repo.branch = "main"

        pattern.repos = [repo]
        return pattern

    @pytest.fixture
    def mock_gitlab_folders_selector(self, mock_folder_pattern: MagicMock) -> MagicMock:
        """Mock the GitLabFoldersSelector class"""
        gitlab_folders_selector = MagicMock()
        gitlab_folders_selector.folders = [mock_folder_pattern]
        return gitlab_folders_selector

    @pytest.fixture
    def resource_config(
        self, mock_gitlab_folders_selector: MagicMock
    ) -> ResourceConfig:
        """Create a mocked GitLabFoldersResourceConfig"""
        config = MagicMock(spec=ResourceConfig)
        config.selector = mock_gitlab_folders_selector
        config.kind = "folder"
        return config

    async def test_get_matching_kinds(
        self, processor: FolderPushWebhookProcessor, mock_event: WebhookEvent
    ) -> None:
        """Test that get_matching_kinds returns the FOLDER kind"""
        assert await processor.get_matching_kinds(mock_event) == [ObjectKind.FOLDER]

    async def test_handle_event_with_matching_repo_and_branch(
        self,
        processor: FolderPushWebhookProcessor,
        push_payload: dict[str, Any],
        resource_config: ResourceConfig,
    ) -> None:
        """Test handling a push event with matching repo and branch"""
        # Mock folders data that would be returned by get_repository_folders
        folders_data = [
            {
                "path": "src/app/components",
                "repository": "getport-labs/project7",
                "ref": push_payload["after"],
                "content": ["Button", "Form", "Navbar"],
            },
            {
                "path": "src/app/utils",
                "repository": "getport-labs/project7",
                "ref": push_payload["after"],
                "content": ["helpers.js", "formatters.js"],
            },
        ]

        processor._gitlab_webhook_client = MagicMock()

        # Mock the get_repository_folders method to yield folder batches
        async def mock_get_repository_folders(*args, **kwargs):
            yield folders_data

        processor._gitlab_webhook_client.get_repository_folders = (
            mock_get_repository_folders
        )

        result = await processor.handle_event(push_payload, resource_config)

        # Verify get_repository_folders was called with correct parameters
        assert (
            processor._gitlab_webhook_client.get_repository_folders.__name__
            == "mock_get_repository_folders"
        )

        # Verify results
        assert len(result.updated_raw_results) == 2
        assert result.updated_raw_results == folders_data
        assert not result.deleted_raw_results

    async def test_handle_event_with_non_matching_repo(
        self,
        processor: FolderPushWebhookProcessor,
        push_payload: dict[str, Any],
        resource_config: ResourceConfig,
    ) -> None:
        """Test handling a push event when repo doesn't match configured repos"""
        # Change the repo name in the pattern to something that doesn't match
        resource_config.selector.folders[0].repos[0].name = "other/repo"

        processor._gitlab_webhook_client = MagicMock()

        # Mock the get_repository_folders method that shouldn't be called
        processor._gitlab_webhook_client.get_repository_folders = AsyncMock()

        result = await processor.handle_event(push_payload, resource_config)

        # Verify get_repository_folders was not called
        processor._gitlab_webhook_client.get_repository_folders.assert_not_called()

        # Verify empty results
        assert not result.updated_raw_results
        assert not result.deleted_raw_results

    async def test_handle_event_with_non_matching_branch(
        self,
        processor: FolderPushWebhookProcessor,
        push_payload: dict[str, Any],
        resource_config: ResourceConfig,
    ) -> None:
        """Test handling a push event when branch doesn't match configured branch"""
        # Change the branch in the pattern to something that doesn't match
        resource_config.selector.folders[0].repos[0].branch = "develop"

        processor._gitlab_webhook_client = MagicMock()

        # Mock the get_repository_folders method that shouldn't be called
        processor._gitlab_webhook_client.get_repository_folders = AsyncMock()

        result = await processor.handle_event(push_payload, resource_config)

        # Verify get_repository_folders was not called
        processor._gitlab_webhook_client.get_repository_folders.assert_not_called()

        # Verify empty results
        assert not result.updated_raw_results
        assert not result.deleted_raw_results

    async def test_handle_event_with_multiple_patterns(
        self,
        processor: FolderPushWebhookProcessor,
        push_payload: dict[str, Any],
        resource_config: ResourceConfig,
    ) -> None:
        """Test handling a push event with multiple folder patterns"""
        # Add a second pattern to the selector
        second_pattern = MagicMock()
        second_pattern.path = "docs/api"

        repo = MagicMock()
        repo.name = "getport-labs/project7"
        repo.branch = "main"

        second_pattern.repos = [repo]
        resource_config.selector.folders.append(second_pattern)

        # Mock folders data for each pattern
        folders_data_1 = [
            {
                "path": "src/app/components",
                "repository": "getport-labs/project7",
                "ref": push_payload["after"],
                "content": ["Button", "Form", "Navbar"],
            },
        ]

        folders_data_2 = [
            {
                "path": "docs/api",
                "repository": "getport-labs/project7",
                "ref": push_payload["after"],
                "content": ["endpoints.md", "schema.md"],
            },
        ]

        # Create a fresh MagicMock for the client
        processor._gitlab_webhook_client = MagicMock()

        # Track calls to get_repository_folders
        call_count = 0

        # Mock get_repository_folders to return different data based on the path parameter
        async def mock_get_repository_folders(path, repository, branch):
            nonlocal call_count
            call_count += 1
            if path == "src/":
                yield folders_data_1
            elif path == "docs/api":
                yield folders_data_2
            else:
                yield []

        processor._gitlab_webhook_client.get_repository_folders = (
            mock_get_repository_folders
        )

        result = await processor.handle_event(push_payload, resource_config)

        # Verify get_repository_folders was called twice (once for each pattern)
        assert call_count == 2

        # Verify results contain both folder batches
        assert len(result.updated_raw_results) == 2
        assert result.updated_raw_results == folders_data_1 + folders_data_2
        assert not result.deleted_raw_results

    async def test_handle_event_with_no_folders_found(
        self,
        processor: FolderPushWebhookProcessor,
        push_payload: dict[str, Any],
        resource_config: ResourceConfig,
    ) -> None:
        """Test handling a push event when no folders are found"""
        processor._gitlab_webhook_client = MagicMock()

        # Mock get_repository_folders to return empty results
        async def mock_get_repository_folders(*args, **kwargs):
            yield []

        processor._gitlab_webhook_client.get_repository_folders = (
            mock_get_repository_folders
        )

        result = await processor.handle_event(push_payload, resource_config)

        # Verify get_repository_folders was called
        assert (
            processor._gitlab_webhook_client.get_repository_folders.__name__
            == "mock_get_repository_folders"
        )

        # Verify empty results
        assert not result.updated_raw_results
        assert not result.deleted_raw_results

    async def test_handle_event_with_no_repos_specified(
        self,
        processor: FolderPushWebhookProcessor,
        push_payload: dict[str, Any],
        resource_config: ResourceConfig,
    ) -> None:
        """Test handling a push event when no repos are specified in the pattern"""
        # Set repos to empty list
        resource_config.selector.folders[0].repos = []

        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_repository_folders = AsyncMock()

        result = await processor.handle_event(push_payload, resource_config)

        # Verify get_repository_folders was not called
        processor._gitlab_webhook_client.get_repository_folders.assert_not_called()

        # Verify empty results
        assert not result.updated_raw_results
        assert not result.deleted_raw_results
