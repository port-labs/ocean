from unittest.mock import AsyncMock, MagicMock

import pytest

from azure_devops.enrichments.included_files import (
    FileIncludedFilesStrategy,
    FolderIncludedFilesStrategy,
    IncludedFilesEnricher,
)
from azure_devops.misc import AzureDevopsFolderSelector, RepositoryBranchMapping


@pytest.mark.asyncio
class TestIncludedFilesRelativeResolution:
    async def test_folder_included_files_resolves_relative_to_folder_path(self) -> None:
        folder_selectors = [
            AzureDevopsFolderSelector(
                path="apps/*",
                repos=[RepositoryBranchMapping(name="test-repo", branch="main")],
                includedFiles=["README.md"],
            )
        ]
        folders = [
            {
                "path": "apps/service-a",
                "__repository": {
                    "id": "repo-1",
                    "name": "test-repo",
                    "defaultBranch": "refs/heads/main",
                    "project": {"id": "project-1"},
                },
                "__branch": "main",
            },
            {
                "path": "apps/service-b",
                "__repository": {
                    "id": "repo-1",
                    "name": "test-repo",
                    "defaultBranch": "refs/heads/main",
                    "project": {"id": "project-1"},
                },
                "__branch": "main",
            },
        ]

        mock_client = MagicMock()

        async def get_file_by_branch_side_effect(
            path: str, repo_id: str, branch: str
        ) -> bytes:
            return f"content:{path}".encode("utf-8")

        mock_client.get_file_by_branch = AsyncMock(
            side_effect=get_file_by_branch_side_effect
        )

        enricher = IncludedFilesEnricher(
            client=mock_client,
            strategy=FolderIncludedFilesStrategy(folder_selectors=folder_selectors),
        )
        enriched = await enricher.enrich_batch(folders)

        assert (
            enriched[0]["folder"]["__includedFiles"]["README.md"]
            == "content:apps/service-a/README.md"
        )
        assert (
            enriched[1]["folder"]["__includedFiles"]["README.md"]
            == "content:apps/service-b/README.md"
        )

    async def test_folder_global_included_files_attaches_to_top_level(self) -> None:
        folder_selectors = [
            AzureDevopsFolderSelector(
                path="apps/*",
                repos=[RepositoryBranchMapping(name="test-repo", branch="main")],
                includedFiles=["README.md"],
            )
        ]
        folders = [
            {
                "path": "apps/service-a",
                "__repository": {
                    "id": "repo-1",
                    "name": "test-repo",
                    "defaultBranch": "refs/heads/main",
                    "project": {"id": "project-1"},
                },
                "__branch": "main",
            }
        ]

        mock_client = MagicMock()

        async def get_file_by_branch_side_effect(
            path: str, repo_id: str, branch: str
        ) -> bytes:
            return f"content:{path}".encode("utf-8")

        mock_client.get_file_by_branch = AsyncMock(
            side_effect=get_file_by_branch_side_effect
        )

        enricher = IncludedFilesEnricher(
            client=mock_client,
            strategy=FolderIncludedFilesStrategy(
                folder_selectors=folder_selectors,
                global_included_files=["README.md"],
            ),
        )
        enriched = await enricher.enrich_batch(folders)

        assert enriched[0]["__includedFiles"]["README.md"] == "content:README.md"
        assert (
            enriched[0]["folder"]["__includedFiles"]["README.md"]
            == "content:apps/service-a/README.md"
        )

    async def test_file_included_files_resolves_relative_to_file_directory(
        self,
    ) -> None:
        files = [
            {
                "repo": {
                    "id": "repo-1",
                    "name": "test-repo",
                    "defaultBranch": "refs/heads/main",
                    "project": {"id": "project-1"},
                },
                "branch": "main",
                "path": "apps/service-a/service.yaml",
            }
        ]

        mock_client = MagicMock()
        mock_client.get_file_by_branch = AsyncMock(
            return_value=b"service-a-readme"
        )

        enricher = IncludedFilesEnricher(
            client=mock_client,
            strategy=FileIncludedFilesStrategy(included_files=["README.md"]),
        )
        enriched = await enricher.enrich_batch(files)

        assert enriched[0]["__includedFiles"]["README.md"] == "service-a-readme"
        mock_client.get_file_by_branch.assert_called_once_with(
            "apps/service-a/README.md", "repo-1", "main"
        )
