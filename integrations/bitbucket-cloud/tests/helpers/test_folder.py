import pytest
from unittest.mock import AsyncMock
from typing import Any, AsyncGenerator, Dict, List, Optional, Set

from bitbucket_cloud.helpers.folder import (
    extract_repo_names_from_patterns,
    create_pattern_mapping,
    find_matching_folders,
    process_folder_patterns,
    process_repo_folders,
)
from integration import FolderPattern, RepositoryBranchMapping
from bitbucket_cloud.client import BitbucketClient


@pytest.fixture
def sample_folder_patterns() -> List[FolderPattern]:
    return [
        FolderPattern(
            path="src/main",
            repos=[
                RepositoryBranchMapping(name="repo1", branch="main"),
                RepositoryBranchMapping(name="repo2", branch="main"),
            ],
        ),
        FolderPattern(
            path="docs/*",
            repos=[
                RepositoryBranchMapping(name="repo2", branch="main"),
                RepositoryBranchMapping(name="repo3", branch="main"),
            ],
        ),
        FolderPattern(
            path="tests/unit",
            repos=[RepositoryBranchMapping(name="repo1", branch="main")],
        ),
    ]


@pytest.mark.asyncio
async def test_extract_repo_names_from_patterns(
    sample_folder_patterns: List[FolderPattern],
) -> None:
    result = extract_repo_names_from_patterns(sample_folder_patterns)
    expected: Set[str] = {"repo1", "repo2", "repo3"}
    assert result == expected


@pytest.mark.asyncio
async def test_extract_repo_names_from_patterns_empty() -> None:
    result = extract_repo_names_from_patterns([])
    assert result == set()


@pytest.mark.asyncio
async def test_extract_repo_names_from_patterns_no_repos() -> None:
    patterns = [FolderPattern(path="src/main", repos=[])]
    result = extract_repo_names_from_patterns(patterns)
    assert result == set()


@pytest.mark.asyncio
async def test_create_pattern_mapping(
    sample_folder_patterns: List[FolderPattern],
) -> None:
    result = create_pattern_mapping(sample_folder_patterns)
    expected: Dict[str, Dict[str, List[str]]] = {
        "repo1": {"main": ["src/main", "tests/unit"]},
        "repo2": {"main": ["src/main", "docs/*"]},
        "repo3": {"main": ["docs/*"]},
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

    result = find_matching_folders(contents, patterns, repo, "main")
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

    result = find_matching_folders(contents, patterns, repo, "main")
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
    assert len(results) >= 1  # At least one result should be present
    paths: Set[str] = {item["folder"]["path"] for item in results}
    assert any(path in paths for path in ["src/main", "tests/unit", "docs/api"])


@pytest.mark.asyncio
async def test_process_repo_folders() -> None:
    # Setup
    repo: Dict[str, Any] = {
        "name": "repo1",
        "slug": "repo1",
        "mainbranch": {"name": "main"},
    }
    pattern_by_repo: Dict[str, Dict[str, List[str]]] = {
        "repo1": {"main": ["src/main", "tests/unit"]}
    }
    folder_patterns: List[FolderPattern] = [
        FolderPattern(
            path="src/main",
            repos=[RepositoryBranchMapping(name="repo1", branch="main")],
        ),
        FolderPattern(
            path="tests/unit",
            repos=[RepositoryBranchMapping(name="repo1", branch="main")],
        ),
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
