import pytest
from unittest.mock import AsyncMock
from typing import Any, AsyncGenerator, Dict, List, Optional, Set

from helpers.folder import (
    extract_repo_names_from_patterns,
    create_pattern_mapping,
    find_matching_folders,
    process_folder_patterns,
    process_repo_folders,
)
from integration import FolderPattern
from client import BitbucketClient


@pytest.fixture
def sample_folder_patterns() -> List[FolderPattern]:
    return [
        FolderPattern(path="src/main", repos=["repo1", "repo2"]),
        FolderPattern(path="docs/*", repos=["repo2", "repo3"]),
        FolderPattern(path="tests/unit", repos=["repo1"]),
    ]


@pytest.mark.asyncio
async def test_extract_repo_names_from_patterns(
    sample_folder_patterns: List[FolderPattern],
) -> None:
    result = await extract_repo_names_from_patterns(sample_folder_patterns)
    expected: Set[str] = {"repo1", "repo2", "repo3"}
    assert result == expected


@pytest.mark.asyncio
async def test_extract_repo_names_from_patterns_empty() -> None:
    result = await extract_repo_names_from_patterns([])
    assert result == set()


@pytest.mark.asyncio
async def test_extract_repo_names_from_patterns_no_repos() -> None:
    patterns = [FolderPattern(path="src/main", repos=[])]
    result = await extract_repo_names_from_patterns(patterns)
    assert result == set()


@pytest.mark.asyncio
async def test_create_pattern_mapping(
    sample_folder_patterns: List[FolderPattern],
) -> None:
    result = await create_pattern_mapping(sample_folder_patterns)
    expected: Dict[str, List[str]] = {
        "repo1": ["src/main", "tests/unit"],
        "repo2": ["src/main", "docs/*"],
        "repo3": ["docs/*"],
    }
    assert result == expected


@pytest.mark.asyncio
async def test_find_matching_folders() -> None:
    # Test exact match
    contents: List[Dict[str, Any]] = [
        {"path": "src/main", "type": "commit_directory"},
        {"path": "src/test", "type": "commit_directory"},
        {"path": "src/main/file.txt", "type": "commit_file"},
    ]
    patterns: List[str] = ["src/main"]
    repo: Dict[str, Any] = {"name": "test_repo"}

    result = await find_matching_folders(contents, patterns, repo)
    assert len(result) == 1
    assert result[0]["folder"]["path"] == "src/main"
    assert result[0]["repo"] == repo
    assert result[0]["pattern"] == "src/main"

    # Test wildcard match
    contents = [
        {"path": "docs/api", "type": "commit_directory"},
        {"path": "docs/guide", "type": "commit_directory"},
        {"path": "docs/README.md", "type": "commit_file"},
    ]
    patterns = ["docs/*"]
    repo = {"name": "test_repo"}

    result = await find_matching_folders(contents, patterns, repo)
    assert len(result) == 2
    assert {item["folder"]["path"] for item in result} == {"docs/api", "docs/guide"}


@pytest.mark.asyncio
async def test_process_folder_patterns(
    sample_folder_patterns: List[FolderPattern],
) -> None:
    # Create mock client with simple async generators
    mock_client = AsyncMock(spec=BitbucketClient)

    # Mock repositories generator
    async def mock_get_repositories(
        params: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        repos_data: List[Dict[str, Any]] = [
            {"name": "repo1", "slug": "repo1", "mainbranch": {"name": "main"}},
            {"name": "repo2", "slug": "repo2", "mainbranch": {"name": "master"}},
        ]
        yield repos_data

    # Mock directory contents generator
    async def mock_get_directory_contents(
        repo_slug: str, branch: str, path: str, max_depth: Optional[int] = None
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        if repo_slug == "repo1":
            yield [
                {"path": "src/main", "type": "commit_directory"},
                {"path": "tests/unit", "type": "commit_directory"},
            ]
        else:
            yield [
                {"path": "src/main", "type": "commit_directory"},
                {"path": "docs/api", "type": "commit_directory"},
            ]

    # Assign the generators to the mock methods
    mock_client.get_repositories = mock_get_repositories
    mock_client.get_directory_contents = mock_get_directory_contents

    # Call the function and collect results
    results: List[Dict[str, Any]] = []
    async for folders in process_folder_patterns(sample_folder_patterns, mock_client):
        results.extend(folders)

    # Verify results
    assert len(results) == 4  # 2 from repo1 + 2 from repo2
    paths: Set[str] = {item["folder"]["path"] for item in results}
    assert "src/main" in paths
    assert "tests/unit" in paths
    assert "docs/api" in paths


@pytest.mark.asyncio
async def test_process_repo_folders() -> None:
    # Setup
    repo: Dict[str, Any] = {
        "name": "repo1",
        "slug": "repo1",
        "mainbranch": {"name": "main"},
    }
    pattern_by_repo: Dict[str, List[str]] = {"repo1": ["src/main", "tests/unit"]}
    folder_patterns: List[FolderPattern] = [
        FolderPattern(path="src/main", repos=["repo1"]),
        FolderPattern(path="tests/unit", repos=["repo1"]),
    ]

    # Create mock client with simple async generator
    mock_client = AsyncMock(spec=BitbucketClient)

    # Mock directory contents generator
    async def mock_get_directory_contents(
        repo_slug: str, branch: str, path: str, max_depth: Optional[int] = None
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        yield [
            {"path": "src/main", "type": "commit_directory"},
            {"path": "tests/unit", "type": "commit_directory"},
            {"path": "docs", "type": "commit_directory"},
        ]

    mock_client.get_directory_contents = mock_get_directory_contents
    results: List[Dict[str, Any]] = []
    async for folders in process_repo_folders(
        repo, pattern_by_repo, folder_patterns, mock_client
    ):
        results.extend(folders)

    # Verify results
    assert len(results) == 2
    assert {item["folder"]["path"] for item in results} == {"src/main", "tests/unit"}
    assert all(item["repo"] == repo for item in results)
