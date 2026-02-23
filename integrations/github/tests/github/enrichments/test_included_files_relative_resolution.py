from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any

import pytest

from github.enrichments.included_files import (
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
                organization="test-org",
                path="apps/*",
                repos=[RepositoryBranchMapping(name="Port", branch="main")],
                includedFiles=["README.md"],
            )
        ]
        folders = [
            {
                "folder": {"path": "apps/service-a"},
                "__organization": "test-org",
                "__repository": {"name": "Port", "default_branch": "main"},
                "__branch": "main",
            },
            {
                "folder": {"path": "apps/service-b"},
                "__organization": "test-org",
                "__repository": {"name": "Port", "default_branch": "main"},
                "__branch": "main",
            },
        ]

        mock_file_exporter = AsyncMock()

        async def get_resource_side_effect(
            options: dict[str, Any],
        ) -> dict[str, Any]:
            return {"content": f"content:{options['file_path']}"}

        mock_file_exporter.get_resource.side_effect = get_resource_side_effect

        with patch(
            "github.enrichments.included_files.fetcher.RestFileExporter",
            return_value=mock_file_exporter,
        ):
            enricher = IncludedFilesEnricher(
                rest_client=MagicMock(),
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

    async def test_folder_included_files_leading_slash_is_relative_when_base_path_present(
        self,
    ) -> None:
        folder_selectors = [
            FolderSelector(
                organization="test-org",
                path="apps/*",
                repos=[RepositoryBranchMapping(name="Port", branch="main")],
                includedFiles=["/README.md"],
            )
        ]
        folders = [
            {
                "folder": {"path": "apps/service-a"},
                "__organization": "test-org",
                "__repository": {"name": "Port", "default_branch": "main"},
                "__branch": "main",
            }
        ]

        mock_file_exporter = AsyncMock()
        mock_file_exporter.get_resource.return_value = {"content": "folder-readme"}

        with patch(
            "github.enrichments.included_files.fetcher.RestFileExporter",
            return_value=mock_file_exporter,
        ):
            enricher = IncludedFilesEnricher(
                rest_client=MagicMock(),
                strategy=FolderIncludedFilesStrategy(folder_selectors=folder_selectors),
            )
            enriched = await enricher.enrich_batch(folders)

        assert enriched[0]["folder"]["__includedFiles"]["/README.md"] == "folder-readme"
        call_args = mock_file_exporter.get_resource.call_args[0][0]
        assert call_args["file_path"] == "apps/service-a/README.md"

    async def test_folder_global_included_files_attaches_to_top_level(self) -> None:
        folder_selectors = [
            FolderSelector(
                organization="test-org",
                path="apps/*",
                repos=[RepositoryBranchMapping(name="Port", branch="main")],
                includedFiles=["README.md"],
            )
        ]
        folders = [
            {
                "folder": {"path": "apps/service-a"},
                "__organization": "test-org",
                "__repository": {"name": "Port", "default_branch": "main"},
                "__branch": "main",
            }
        ]

        mock_file_exporter = AsyncMock()

        async def get_resource_side_effect(
            options: dict[str, Any],
        ) -> dict[str, Any]:
            return {"content": f"content:{options['file_path']}"}

        mock_file_exporter.get_resource.side_effect = get_resource_side_effect

        with patch(
            "github.enrichments.included_files.fetcher.RestFileExporter",
            return_value=mock_file_exporter,
        ):
            enricher = IncludedFilesEnricher(
                rest_client=MagicMock(),
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

    async def test_global_leading_slash_is_repo_root(self) -> None:
        folder_selectors = [
            FolderSelector(
                organization="test-org",
                path="apps/*",
                repos=[RepositoryBranchMapping(name="Port", branch="main")],
                includedFiles=["README.md"],
            )
        ]
        folders = [
            {
                "folder": {"path": "apps/service-a"},
                "__organization": "test-org",
                "__repository": {"name": "Port", "default_branch": "main"},
                "__branch": "main",
            }
        ]

        mock_file_exporter = AsyncMock()

        async def get_resource_side_effect(
            options: dict[str, Any],
        ) -> dict[str, Any]:
            return {"content": f"content:{options['file_path']}"}

        mock_file_exporter.get_resource.side_effect = get_resource_side_effect

        with patch(
            "github.enrichments.included_files.fetcher.RestFileExporter",
            return_value=mock_file_exporter,
        ):
            enricher = IncludedFilesEnricher(
                rest_client=MagicMock(),
                strategy=FolderIncludedFilesStrategy(
                    folder_selectors=folder_selectors,
                    global_included_files=["/README.md"],
                ),
            )
            enriched = await enricher.enrich_batch(folders)

        assert enriched[0]["__includedFiles"]["/README.md"] == "content:README.md"

    async def test_file_included_files_resolves_relative_to_file_directory(
        self,
    ) -> None:
        files = [
            {
                "organization": "test-org",
                "repository": {"name": "Port", "default_branch": "main"},
                "branch": "main",
                "path": "apps/service-a/service.yaml",
            }
        ]

        mock_file_exporter = AsyncMock()
        mock_file_exporter.get_resource.return_value = {"content": "service-a-readme"}

        with patch(
            "github.enrichments.included_files.fetcher.RestFileExporter",
            return_value=mock_file_exporter,
        ):
            enricher = IncludedFilesEnricher(
                rest_client=MagicMock(),
                strategy=FileIncludedFilesStrategy(included_files=["README.md"]),
            )
            enriched = await enricher.enrich_batch(files)

        assert enriched[0]["__includedFiles"]["README.md"] == "service-a-readme"
        call_args = mock_file_exporter.get_resource.call_args[0][0]
        assert call_args["file_path"] == "apps/service-a/README.md"
