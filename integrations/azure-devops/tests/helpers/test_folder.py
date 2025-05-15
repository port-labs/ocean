import pytest
from unittest.mock import AsyncMock
from typing import Any, AsyncGenerator, Dict, List

from azure_devops.helpers.folder import process_folder_patterns
from azure_devops.misc import FolderPattern, RepositoryBranchMapping
from azure_devops.client.azure_devops_client import AzureDevopsClient


@pytest.fixture
def sample_folder_patterns() -> List[FolderPattern]:
    return [
        FolderPattern(
            path="/src/main",
            repos=[
                RepositoryBranchMapping(name="repo1", branch="main"),
                RepositoryBranchMapping(name="repo2", branch="main"),
            ],
        ),
        FolderPattern(
            path="/docs",
            repos=[
                RepositoryBranchMapping(name="repo2", branch="main"),
                RepositoryBranchMapping(name="repo3", branch="develop"),
            ],
        ),
    ]


@pytest.mark.asyncio
async def test_process_folder_patterns(
    sample_folder_patterns: List[FolderPattern],
) -> None:
    mock_client = AsyncMock(spec=AzureDevopsClient)

    async def mock_generate_repositories() -> (
        AsyncGenerator[List[Dict[str, Any]], None]
    ):
        repos_data = [
            {"name": "repo1", "id": "repo1-id"},
            {"name": "repo2", "id": "repo2-id"},
            {"name": "repo3", "id": "repo3-id"},
        ]
        yield repos_data

    async def mock_get_repository_folders(
        repo_id: str, paths: List[str]
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        folders_data = []
        if repo_id == "repo1-id" and "/src/main" in paths:
            folders_data = [
                {"path": "/src/main", "type": "folder"},
                {"path": "/src/main/code", "type": "folder"},
            ]
        elif repo_id == "repo2-id":
            if "/src/main" in paths:
                folders_data = [{"path": "/src/main", "type": "folder"}]
            elif "/docs" in paths:
                folders_data = [{"path": "/docs", "type": "folder"}]
        elif repo_id == "repo3-id" and "/docs" in paths:
            folders_data = [{"path": "/docs", "type": "folder"}]
        yield folders_data

    mock_client.generate_repositories = mock_generate_repositories
    mock_client.get_repository_folders = mock_get_repository_folders

    results: List[Dict[str, Any]] = []
    async for folders in process_folder_patterns(sample_folder_patterns, mock_client):
        results.extend(folders)

    assert len(results) > 0

    paths = {folder["path"] for folder in results}
    assert "/src/main" in paths
    assert "/docs" in paths
    repo_branches = {
        (folder["__repository"]["name"], folder["__branch"]) for folder in results
    }
    expected_repo_branches = {
        ("repo1", "main"),
        ("repo2", "main"),
        ("repo3", "develop"),
    }
    assert repo_branches.intersection(expected_repo_branches)

    patterns = {folder["__pattern"] for folder in results}
    assert "/src/main" in patterns
    assert "/docs" in patterns


@pytest.mark.asyncio
async def test_process_folder_patterns_empty_folders() -> None:
    """Test with empty folder patterns"""
    mock_client = AsyncMock(spec=AzureDevopsClient)
    results = []
    async for folders in process_folder_patterns([], mock_client):
        results.extend(folders)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_process_folder_patterns_no_matching_repos() -> None:
    """Create patterns with non-existent repos"""
    patterns = [
        FolderPattern(
            path="/src",
            repos=[RepositoryBranchMapping(name="non-existent-repo", branch="main")],
        )
    ]

    mock_client = AsyncMock(spec=AzureDevopsClient)

    async def mock_generate_repositories() -> (
        AsyncGenerator[List[Dict[str, Any]], None]
    ):
        yield []

    mock_client.generate_repositories = mock_generate_repositories
    results = []
    async for folders in process_folder_patterns(patterns, mock_client):
        results.extend(folders)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_process_folder_patterns_no_matching_folders() -> None:
    """Create patterns with valid repo but non-existent folders"""
    patterns = [
        FolderPattern(
            path="/non-existent-folder",
            repos=[RepositoryBranchMapping(name="repo1", branch="main")],
        )
    ]
    mock_client = AsyncMock(spec=AzureDevopsClient)

    async def mock_generate_repositories() -> (
        AsyncGenerator[List[Dict[str, Any]], None]
    ):
        yield [{"name": "repo1", "id": "repo1-id"}]

    async def mock_get_repository_folders(
        repo_id: str, paths: List[str]
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        yield []

    mock_client.generate_repositories = mock_generate_repositories
    mock_client.get_repository_folders = mock_get_repository_folders

    results = []
    async for folders in process_folder_patterns(patterns, mock_client):
        results.extend(folders)
    assert len(results) == 0
