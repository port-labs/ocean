import pytest
from unittest.mock import AsyncMock
from typing import Any, AsyncGenerator, Dict, List, Optional, Set

from bitbucket_cloud.helpers.folder import (
    extract_repo_names_from_patterns,
    extract_global_patterns,
    create_pattern_mapping,
    find_matching_folders,
    process_folder_patterns,
    process_repo_folders,
    process_repo_folders_global,
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
    assert result is None


@pytest.mark.asyncio
async def test_create_pattern_mapping(
    sample_folder_patterns: List[FolderPattern],
) -> None:
    repo_mapping, global_patterns = create_pattern_mapping(sample_folder_patterns)
    expected: Dict[str, Dict[str, List[str]]] = {
        "repo1": {"main": ["src/main", "tests/unit"]},
        "repo2": {"main": ["src/main", "docs/*"]},
        "repo3": {"main": ["docs/*"]},
    }
    assert repo_mapping == expected
    assert global_patterns == []


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
    global_patterns: List[str] = []

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
        repo, pattern_by_repo, global_patterns, mock_client
    ):
        results.extend(folders)

    # Verify results
    assert len(results) == 2
    assert {item["folder"]["path"] for item in results} == {"src/main", "tests/unit"}


@pytest.mark.asyncio
async def test_find_matching_folders_three_level_wildcard() -> None:
    """Test that */*/* pattern matches exactly 3-level deep folders."""
    contents: List[Dict[str, Any]] = [
        {"path": "src", "type": "commit_directory"},
        {"path": "src/main", "type": "commit_directory"},
        {"path": "src/main/java", "type": "commit_directory"},
        {"path": "src/main/java/com", "type": "commit_directory"},
        {"path": "docs/api/v1", "type": "commit_directory"},
        {"path": "tests/unit/helpers", "type": "commit_directory"},
    ]
    patterns: List[str] = ["*/*/*"]
    repo: Dict[str, Any] = {"name": "test_repo"}

    result = find_matching_folders(contents, patterns, repo, "main")

    # Should match exactly 3-level deep folders (2 slashes)
    assert len(result) == 3
    paths = {item["folder"]["path"] for item in result}
    assert paths == {"src/main/java", "docs/api/v1", "tests/unit/helpers"}


@pytest.mark.asyncio
async def test_process_repo_folders_global() -> None:
    """Test global folder processing without specific repos configured."""
    repo: Dict[str, Any] = {
        "name": "repo1",
        "slug": "repo1",
        "mainbranch": {"name": "main"},
    }
    global_patterns = ["*/*/*"]

    # Create mock client
    mock_client = AsyncMock(spec=BitbucketClient)

    async def mock_get_directory_contents(
        repo_slug: str, branch: str, path: str, max_depth: Optional[int] = None
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        yield [
            {"path": "src", "type": "commit_directory"},
            {"path": "src/main", "type": "commit_directory"},
            {"path": "src/main/java", "type": "commit_directory"},
            {"path": "docs/api/v1", "type": "commit_directory"},
            {"path": "a/b/c/d", "type": "commit_directory"},
        ]

    mock_client.get_directory_contents = mock_get_directory_contents

    results: List[Dict[str, Any]] = []
    async for folders in process_repo_folders_global(
        repo, global_patterns, mock_client
    ):
        results.extend(folders)

    # Verify only 3-level folders are matched
    assert len(results) == 2
    assert {item["folder"]["path"] for item in results} == {
        "src/main/java",
        "docs/api/v1",
    }


@pytest.mark.asyncio
async def test_create_pattern_mapping_no_repos() -> None:
    """Test that create_pattern_mapping returns None for repo mapping when no repos are specified."""
    patterns = [FolderPattern(path="*/*/*", repos=[])]
    repo_mapping, global_patterns = create_pattern_mapping(patterns)
    assert repo_mapping is None
    assert global_patterns == ["*/*/*"]


@pytest.mark.asyncio
async def test_extract_global_patterns() -> None:
    """Test extraction of global patterns (patterns without repos)."""
    patterns = [
        FolderPattern(
            path="src/*", repos=[RepositoryBranchMapping(name="repo1", branch="main")]
        ),
        FolderPattern(path="*/*/*", repos=[]),
        FolderPattern(path="docs/*", repos=[]),
    ]
    global_patterns = extract_global_patterns(patterns)
    assert global_patterns == ["*/*/*", "docs/*"]


@pytest.mark.asyncio
async def test_mixed_patterns() -> None:
    """Test handling of mixed repo-specific and global patterns."""
    patterns = [
        FolderPattern(
            path="src/*", repos=[RepositoryBranchMapping(name="repo1", branch="main")]
        ),
        FolderPattern(path="*/*/*", repos=[]),
    ]
    repo_mapping, global_patterns = create_pattern_mapping(patterns)

    assert repo_mapping == {"repo1": {"main": ["src/*"]}}
    assert global_patterns == ["*/*/*"]
