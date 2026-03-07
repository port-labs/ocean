"""Tests for AzureDevopsClient.generate_files behaviour."""

from typing import Any, AsyncGenerator

import pytest

from azure_devops.client.azure_devops_client import AzureDevopsClient
from azure_devops.client.file_processing import PathDescriptor


@pytest.mark.asyncio
async def test_generate_files_does_not_stop_after_empty_project() -> None:
    """Regression test for PORT-17439.

    When generate_repositories yields an empty batch (a project with no repos),
    generate_files must skip it and continue processing subsequent batches rather
    than returning early and dropping all remaining projects.
    """
    paths = ["**/*.md"]

    mock_repo = {
        "name": "repo1",
        "id": "repo1-id",
        "defaultBranch": "refs/heads/main",
        "project": {"id": "project2-id"},
    }

    client = AzureDevopsClient("https://dev.azure.com/test", "token")

    # First yield is an empty project; second yield has one real repo.
    async def mock_generate_repositories(
        include_disabled_repositories: bool = True,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        yield []  # empty project — must NOT stop processing
        yield [mock_repo]

    async def mock__get_files_by_descriptors(
        repository: dict[str, Any],
        descriptors: list[PathDescriptor],
        branch: str,
    ) -> list[dict[str, Any]]:
        return [
            {
                "path": "/README.md",
                "objectId": "readme123",
                "gitObjectType": "blob",
                "isFolder": False,
                "commitId": "commit123",
            }
        ]

    async def mock_download_single_file(
        file: dict[str, Any], repository: dict[str, Any], branch: str
    ) -> dict[str, Any] | None:
        return {
            "file": {
                "path": file["path"].lstrip("/"),
                "content": {"raw": "# README", "parsed": {}},
                "size": 9,
                "objectId": file["objectId"],
                "isFolder": False,
            },
            "repo": repository,
        }

    client.generate_repositories = mock_generate_repositories  # type: ignore
    client._get_files_by_descriptors = mock__get_files_by_descriptors  # type: ignore
    client.download_single_file = mock_download_single_file  # type: ignore

    results = []
    async for batch in client.generate_files(paths):
        results.extend(batch)

    # The file from repo1 (second project) must be returned despite the empty first project.
    assert len(results) == 1
    assert results[0]["file"]["path"] == "README.md"
    assert results[0]["repo"]["name"] == "repo1"
