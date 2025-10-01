from typing import Any, AsyncGenerator

import pytest
from github.core.options import ListFolderOptions
from github.helpers.utils import ObjectKind
from github.webhook.webhook_processors.folder_webhook_processor import (
    FolderWebhookProcessor,
)
from integration import (
    FolderSelector,
    GithubFolderResourceConfig,
    GithubFolderSelector,
    RepositoryBranchMapping,
)
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def folder_resource_config() -> GithubFolderResourceConfig:
    return GithubFolderResourceConfig(
        kind=ObjectKind.FOLDER,
        selector=GithubFolderSelector(
            query="true",
            folders=[
                FolderSelector(
                    path="folder1/*",
                    repos=[
                        RepositoryBranchMapping(name="test-repo", branch="main"),
                        RepositoryBranchMapping(name="another-repo", branch="dev"),
                    ],
                ),
                FolderSelector(
                    path="folder2/*",
                    repos=[RepositoryBranchMapping(name="test-repo", branch="main")],
                ),
            ],
        ),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".path",
                    title=".name",
                    blueprint='"githubFolder"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def folder_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> FolderWebhookProcessor:
    return FolderWebhookProcessor(event=mock_webhook_event)


@pytest.mark.asyncio
class TestFolderWebhookProcessor:
    @pytest.mark.parametrize(
        "github_event,result",
        [("push", True), ("invalid", False), ("repository", False)],
    )
    async def test_should_process_event(
        self,
        folder_webhook_processor: FolderWebhookProcessor,
        github_event: str,
        result: bool,
    ) -> None:
        mock_request = AsyncMock()
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={},
            headers={"x-github-event": github_event},
        )
        event._original_request = mock_request

        assert await folder_webhook_processor._should_process_event(event) is result

    @pytest.mark.parametrize(
        "payload,expected",
        [
            (
                {
                    "ref": "refs/heads/main",
                    "repository": {"name": "test"},
                    "before": "ldl",
                    "after": "jdj",
                    "organization": {"login": "test-org"},
                },
                True,
            ),
            ({"ref": "refs/heads/main"}, False),
            ({"repository": {"name": "test"}}, False),
            ({}, False),
        ],
    )
    async def test_validate_payload(
        self,
        folder_webhook_processor: FolderWebhookProcessor,
        payload: dict[str, Any],
        expected: bool,
    ) -> None:
        result = await folder_webhook_processor.validate_payload(payload)
        assert result is expected

    async def test_get_matching_kinds(
        self, folder_webhook_processor: FolderWebhookProcessor
    ) -> None:
        kinds = await folder_webhook_processor.get_matching_kinds(
            folder_webhook_processor.event
        )
        assert ObjectKind.FOLDER in kinds

    @patch(
        "github.webhook.webhook_processors.folder_webhook_processor.create_github_client"
    )
    @patch(
        "github.webhook.webhook_processors.folder_webhook_processor.fetch_commit_diff",
        new_callable=AsyncMock,
    )
    @patch(
        "github.webhook.webhook_processors.folder_webhook_processor.extract_changed_files"
    )
    @patch(
        "github.webhook.webhook_processors.folder_webhook_processor.RestFolderExporter"
    )
    async def test_handle_event_with_changed_folders(
        self,
        mock_exporter_class: MagicMock,
        mock_extract_changed_files: MagicMock,
        mock_fetch_commit_diff: AsyncMock,
        mock_create_client: MagicMock,
        folder_webhook_processor: FolderWebhookProcessor,
        folder_resource_config: GithubFolderResourceConfig,
    ) -> None:
        repo_name = "test-repo"
        branch_name = "main"
        ref_sha_after = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0"
        ref_sha_before = "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0a1"

        payload: dict[str, Any] = {
            "repository": {"name": repo_name},
            "ref": f"refs/heads/{branch_name}",
            "after": ref_sha_after,
            "before": ref_sha_before,
            "organization": {"login": "test-org"},
        }

        all_folders_from_exporter = [
            {
                "folder": {
                    "path": "folder1/subfolder1",
                    "name": "subfolder1",
                    "repo": repo_name,
                    "branch": branch_name,
                }
            },
            {
                "folder": {
                    "path": "folder1/subfolder2",
                    "name": "subfolder2",
                    "repo": repo_name,
                    "branch": branch_name,
                }
            },
            {
                "folder": {
                    "path": "folder2/subfolderA",
                    "name": "subfolderA",
                    "repo": repo_name,
                    "branch": branch_name,
                }
            },
        ]
        changed_files = [
            "folder1/subfolder1/file.txt",
            "folder2/subfolderA/another_file.log",
        ]
        expected_folders = [
            all_folders_from_exporter[0],
            all_folders_from_exporter[2],
        ]

        mock_client = MagicMock()
        mock_client.send_api_request = AsyncMock(return_value={"name": repo_name})
        mock_create_client.return_value = mock_client
        mock_fetch_commit_diff.return_value = {"files": [{"filename": "dummy"}]}
        mock_extract_changed_files.return_value = ([], changed_files)

        async def async_generator_for_exporter() -> (
            AsyncGenerator[list[dict[str, Any]], None]
        ):
            yield [all_folders_from_exporter[0], all_folders_from_exporter[1]]
            yield [all_folders_from_exporter[2]]

        mock_exporter_instance = MagicMock()
        mock_exporter_instance.get_paginated_resources.return_value = (
            async_generator_for_exporter()
        )
        mock_exporter_class.return_value = mock_exporter_instance

        result = await folder_webhook_processor.handle_event(
            payload, folder_resource_config
        )

        assert isinstance(result, WebhookEventRawResults)
        assert result.updated_raw_results == expected_folders
        assert not result.deleted_raw_results

        mock_fetch_commit_diff.assert_called_once_with(
            mock_client, repo_name, ref_sha_before, ref_sha_after
        )
        mock_extract_changed_files.assert_called_once_with([{"filename": "dummy"}])

        repo_mapping1 = {repo_name: {branch_name: ["folder1/*"]}}
        mock_exporter_instance.get_paginated_resources.assert_any_call(
            ListFolderOptions(repo_mapping=repo_mapping1)
        )

        repo_mapping2 = {repo_name: {branch_name: ["folder2/*"]}}
        mock_exporter_instance.get_paginated_resources.assert_any_call(
            ListFolderOptions(repo_mapping=repo_mapping2)
        )
        assert mock_exporter_instance.get_paginated_resources.call_count == 2

    @patch(
        "github.webhook.webhook_processors.folder_webhook_processor.create_github_client"
    )
    @patch(
        "github.webhook.webhook_processors.folder_webhook_processor.fetch_commit_diff",
        new_callable=AsyncMock,
    )
    @patch(
        "github.webhook.webhook_processors.folder_webhook_processor.extract_changed_files"
    )
    @patch(
        "github.webhook.webhook_processors.folder_webhook_processor.RestFolderExporter"
    )
    async def test_handle_event_no_changed_files(
        self,
        mock_exporter_class: MagicMock,
        mock_extract_changed_files: MagicMock,
        mock_fetch_commit_diff: AsyncMock,
        mock_create_client: MagicMock,
        folder_webhook_processor: FolderWebhookProcessor,
        folder_resource_config: GithubFolderResourceConfig,
    ) -> None:
        repo_name = "test-repo"
        branch_name = "main"
        ref_sha_after = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0"
        ref_sha_before = "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0a1"

        payload: dict[str, Any] = {
            "repository": {"name": repo_name},
            "ref": f"refs/heads/{branch_name}",
            "after": ref_sha_after,
            "before": ref_sha_before,
            "organization": {"login": "test-org"},
        }

        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        mock_fetch_commit_diff.return_value = {"files": []}
        mock_extract_changed_files.return_value = ([], [])
        mock_exporter_instance = MagicMock()
        mock_exporter_class.return_value = mock_exporter_instance

        result = await folder_webhook_processor.handle_event(
            payload, folder_resource_config
        )

        assert isinstance(result, WebhookEventRawResults)
        assert not result.updated_raw_results
        assert not result.deleted_raw_results

        mock_fetch_commit_diff.assert_called_once_with(
            mock_client, repo_name, ref_sha_before, ref_sha_after
        )
        mock_extract_changed_files.assert_called_once_with([])
        mock_exporter_instance.get_paginated_resources.assert_not_called()
