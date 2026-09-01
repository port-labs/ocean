"""
Repos with no commits/branches have no default branch in the ADO API
(`defaultBranch` is null). Folder sync must skip those repos and continue.
"""

from typing import Any, AsyncGenerator

import pytest

from azure_devops.client.auth import PatAuthProvider
from azure_devops.client.azure_devops_client import AzureDevopsClient
from azure_devops.misc import FolderPattern, RepositoryBranchMapping


@pytest.mark.asyncio
async def test_process_folder_patterns_skips_repo_without_default_branch() -> None:
    client = AzureDevopsClient("https://dev.azure.com/test", PatAuthProvider("token"))
    patterns = [
        FolderPattern(
            path="src",
            repos=[
                RepositoryBranchMapping(name="empty-repo"),
                RepositoryBranchMapping(name="good-repo"),
            ],
        )
    ]

    async def mock_get_repositories_for_project(
        project_name: str,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        yield [
            {"name": "empty-repo", "id": "empty-id", "defaultBranch": None},
            {
                "name": "good-repo",
                "id": "good-id",
                "defaultBranch": "refs/heads/main",
            },
        ]

    async def mock_get_repository_folders(
        repo_id: str, paths: list[str], **kwargs: Any
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        if repo_id == "good-id":
            yield [{"path": "src", "gitObjectType": "tree"}]

    client._get_repositories_for_project = mock_get_repositories_for_project  # type: ignore[method-assign]
    client.get_repository_folders = mock_get_repository_folders  # type: ignore[method-assign]

    results = []
    async for folders in client.process_folder_patterns(patterns, project_name="proj"):
        results.extend(folders)

    assert len(results) == 1
    assert results[0]["__repository"]["name"] == "good-repo"
