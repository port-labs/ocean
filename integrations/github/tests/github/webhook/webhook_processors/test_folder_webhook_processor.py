from typing import Any, AsyncGenerator

import pytest
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
                    organization="test-org",
                    path="folder1/*",
                    repos=[
                        RepositoryBranchMapping(name="test-repo", branch="main"),
                        RepositoryBranchMapping(name="another-repo", branch="dev"),
                    ],
                ),
                FolderSelector(
                    organization="test-org",
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
def folder_resource_config_unset_branch_with_included_files() -> (
    GithubFolderResourceConfig
):
    """Mirrors the integ-service wipe case: folder kind, unset repo branch, includedFiles."""
    return GithubFolderResourceConfig(
        kind=ObjectKind.FOLDER,
        selector=GithubFolderSelector(
            query="true",
            folders=[
                FolderSelector(
                    organization="test-org",
                    path="apps/*",
                    repos=[
                        # branch omitted => default branch only (resync semantics)
                        RepositoryBranchMapping(name="Port"),
                    ],
                    includedFiles=["README.md", "docs/architecture.md"],
                ),
            ],
        ),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".folder.path",
                    title=".folder.name",
                    blueprint='"githubFolder"',
                    properties={
                        "readme": '.folder.__includedFiles["README.md"]',
                        "architecture": '.folder.__includedFiles["docs/architecture.md"]',
                    },
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
        "github.webhook.webhook_processors.folder_webhook_processor.create_github_client_for_org"
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
            mock_client, "test-org", "test-repo", ref_sha_before, ref_sha_after
        )
        mock_extract_changed_files.assert_called_once_with([{"filename": "dummy"}])

        # The new API passes a list of ListFolderOptions entries with concrete folders
        assert mock_exporter_instance.get_paginated_resources.called

        assert mock_exporter_instance.get_paginated_resources.call_count >= 1

    @patch(
        "github.webhook.webhook_processors.folder_webhook_processor.create_github_client_for_org"
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
            mock_client, "test-org", "test-repo", ref_sha_before, ref_sha_after
        )
        mock_extract_changed_files.assert_called_once_with([])
        mock_exporter_instance.get_paginated_resources.assert_not_called()

    @pytest.mark.parametrize(
        "selector_branch,push_branch,default_branch,expected",
        [
            (None, "main", "main", True),
            (None, "feature", "main", False),
            ("main", "main", "main", True),
            ("main", "feature", "main", False),
            ("default", "main", "main", True),
            ("default", "feature", "main", False),
        ],
    )
    async def test_has_matched_repo_branch_semantics(
        self,
        folder_webhook_processor: FolderWebhookProcessor,
        selector_branch: str | None,
        push_branch: str,
        default_branch: str,
        expected: bool,
    ) -> None:
        pattern = FolderSelector(
            organization="test-org",
            path="docs/*",
            repos=[
                RepositoryBranchMapping(name="test-repo", branch=selector_branch),
            ],
        )
        repository = {
            "name": "test-repo",
            "default_branch": default_branch,
        }

        assert (
            folder_webhook_processor._has_matched_repo(
                pattern, "test-org", repository, push_branch
            )
            is expected
        )

    async def test_has_matched_repo_empty_repos_means_default_branch_only(
        self,
        folder_webhook_processor: FolderWebhookProcessor,
    ) -> None:
        pattern = FolderSelector(
            organization="test-org",
            path="docs/*",
            repos=None,
        )
        repository = {"name": "test-repo", "default_branch": "main"}

        assert (
            folder_webhook_processor._has_matched_repo(
                pattern, "test-org", repository, "main"
            )
            is True
        )
        assert (
            folder_webhook_processor._has_matched_repo(
                pattern, "test-org", repository, "feature"
            )
            is False
        )

    @patch(
        "github.webhook.webhook_processors.folder_webhook_processor.create_github_client_for_org"
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
    @patch(
        "github.webhook.webhook_processors.folder_webhook_processor.RestRepositoryExporter"
    )
    async def test_handle_event_skips_non_default_branch_when_branch_unset_with_included_files(
        self,
        mock_repo_exporter_class: MagicMock,
        mock_folder_exporter_class: MagicMock,
        mock_extract_changed_files: MagicMock,
        mock_fetch_commit_diff: AsyncMock,
        mock_create_client: MagicMock,
        folder_webhook_processor: FolderWebhookProcessor,
        folder_resource_config_unset_branch_with_included_files: GithubFolderResourceConfig,
    ) -> None:
        """Non-default push must not upsert folders (would wipe README/architecture via LE)."""
        repo = {"name": "Port", "default_branch": "main"}
        payload: dict[str, Any] = {
            "repository": {"name": "Port"},
            "ref": "refs/heads/feature/integ-service",
            "after": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
            "before": "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0a1",
            "organization": {"login": "test-org"},
        }

        mock_create_client.return_value = MagicMock()
        mock_fetch_commit_diff.return_value = {"files": [{"filename": "dummy"}]}
        mock_extract_changed_files.return_value = (
            [],
            ["apps/integ-service/src/main.py"],
        )

        mock_repo_exporter = MagicMock()
        mock_repo_exporter.get_resource = AsyncMock(return_value=repo)
        mock_repo_exporter_class.return_value = mock_repo_exporter

        mock_folder_exporter = MagicMock()
        mock_folder_exporter_class.return_value = mock_folder_exporter

        result = await folder_webhook_processor.handle_event(
            payload, folder_resource_config_unset_branch_with_included_files
        )

        assert isinstance(result, WebhookEventRawResults)
        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []
        mock_folder_exporter.get_paginated_resources.assert_not_called()

    @patch(
        "github.webhook.webhook_processors.folder_webhook_processor.create_github_client_for_org"
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
    @patch(
        "github.webhook.webhook_processors.folder_webhook_processor.RestRepositoryExporter"
    )
    async def test_handle_event_enriches_included_files_on_default_branch_when_branch_unset(
        self,
        mock_repo_exporter_class: MagicMock,
        mock_folder_exporter_class: MagicMock,
        mock_extract_changed_files: MagicMock,
        mock_fetch_commit_diff: AsyncMock,
        mock_create_client: MagicMock,
        folder_webhook_processor: FolderWebhookProcessor,
        folder_resource_config_unset_branch_with_included_files: GithubFolderResourceConfig,
    ) -> None:
        """Default-branch push still updates folders and keeps README/architecture populated."""
        repo = {"name": "Port", "default_branch": "main"}
        folder_entity = {
            "folder": {
                "path": "apps/integ-service",
                "name": "integ-service",
                "repo": "Port",
                "branch": "main",
            },
            "__repository": repo,
            "__organization": "test-org",
            "__branch": "main",
        }
        payload: dict[str, Any] = {
            "repository": {"name": "Port"},
            "ref": "refs/heads/main",
            "after": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
            "before": "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0a1",
            "organization": {"login": "test-org"},
        }

        mock_create_client.return_value = MagicMock()
        mock_fetch_commit_diff.return_value = {"files": [{"filename": "dummy"}]}
        mock_extract_changed_files.return_value = (
            [],
            ["apps/integ-service/README.md"],
        )

        mock_repo_exporter = MagicMock()
        mock_repo_exporter.get_resource = AsyncMock(return_value=repo)
        mock_repo_exporter_class.return_value = mock_repo_exporter

        async def async_generator_for_exporter() -> (
            AsyncGenerator[list[dict[str, Any]], None]
        ):
            yield [folder_entity]

        mock_folder_exporter = MagicMock()
        mock_folder_exporter.get_paginated_resources.return_value = (
            async_generator_for_exporter()
        )
        mock_folder_exporter_class.return_value = mock_folder_exporter

        mock_file_exporter = AsyncMock()

        async def get_file_side_effect(options: dict[str, Any]) -> dict[str, Any]:
            contents = {
                "apps/integ-service/README.md": "# integ-service",
                "apps/integ-service/docs/architecture.md": "# architecture",
            }
            return {"content": contents[options["file_path"]]}

        mock_file_exporter.get_resource.side_effect = get_file_side_effect

        with patch(
            "github.enrichments.included_files.fetcher.RestFileExporter",
            return_value=mock_file_exporter,
        ):
            result = await folder_webhook_processor.handle_event(
                payload, folder_resource_config_unset_branch_with_included_files
            )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 1
        included = result.updated_raw_results[0]["folder"]["__includedFiles"]
        assert included["README.md"] == "# integ-service"
        assert included["docs/architecture.md"] == "# architecture"
        assert result.deleted_raw_results == []
