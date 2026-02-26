from unittest.mock import AsyncMock, MagicMock

import pytest

from gitlab.enrichments.included_files import (
    FileIncludedFilesStrategy,
    FolderIncludedFilesStrategy,
    IncludedFilesEnricher,
)
from integration import FolderSelector, RepositoryBranchMapping


@pytest.mark.asyncio
class TestIncludedFilesRelativeResolution:
    async def test_folder_included_files_resolves_relative_to_folder_path(self) -> None:
        folder_selectors = [
            FolderSelector(
                path="apps/*",
                repos=[RepositoryBranchMapping(name="test-project", branch="main")],
                includedFiles=["README.md"],
            )
        ]
        folders = [
            {
                "path": "apps/service-a",
                "__project": {
                    "id": "1",
                    "path_with_namespace": "test-group/test-project",
                    "default_branch": "main",
                },
                "__branch": "main",
            },
            {
                "path": "apps/service-b",
                "__project": {
                    "id": "1",
                    "path_with_namespace": "test-group/test-project",
                    "default_branch": "main",
                },
                "__branch": "main",
            },
        ]

        mock_client = MagicMock()

        async def get_file_content_side_effect(
            project_path: str, file_path: str, branch: str
        ) -> str:
            return f"content:{file_path}"

        mock_client.get_file_content = AsyncMock(
            side_effect=get_file_content_side_effect
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
            FolderSelector(
                path="apps/*",
                repos=[RepositoryBranchMapping(name="test-project", branch="main")],
                includedFiles=["README.md"],
            )
        ]
        folders = [
            {
                "path": "apps/service-a",
                "__project": {
                    "id": "1",
                    "path_with_namespace": "test-group/test-project",
                    "default_branch": "main",
                },
                "__branch": "main",
            }
        ]

        mock_client = MagicMock()

        async def get_file_content_side_effect(
            project_path: str, file_path: str, branch: str
        ) -> str:
            return f"content:{file_path}"

        mock_client.get_file_content = AsyncMock(
            side_effect=get_file_content_side_effect
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
                "project": {
                    "id": "1",
                    "path_with_namespace": "test-group/test-project",
                    "default_branch": "main",
                },
                "branch": "main",
                "path": "apps/service-a/service.yaml",
            }
        ]

        mock_client = MagicMock()
        mock_client.get_file_content = AsyncMock(return_value="service-a-readme")

        enricher = IncludedFilesEnricher(
            client=mock_client,
            strategy=FileIncludedFilesStrategy(included_files=["README.md"]),
        )
        enriched = await enricher.enrich_batch(files)

        assert enriched[0]["__includedFiles"]["README.md"] == "service-a-readme"
        mock_client.get_file_content.assert_called_once_with(
            "test-group/test-project", "apps/service-a/README.md", "main"
        )
