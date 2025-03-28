import pytest
from unittest.mock import AsyncMock
from bitbucket_cloud.helpers.file_kind import (
    build_search_terms,
    process_file_patterns,
    validate_file_match,
)
from integration import BitbucketFilePattern
from typing import AsyncGenerator, Dict, Any, List


def test_build_search_terms_with_all_parameters() -> None:
    """Test build_search_terms with all parameters provided."""
    filename = "test.py"
    repos = ["repo1", "repo2"]
    path = "src/main"
    extension = "py"

    query = build_search_terms(filename, repos, path, extension)

    assert '"test.py"' in query
    assert "repo:repo1" in query
    assert "repo:repo2" in query
    assert "path:src/main" in query
    assert "ext:py" in query


def test_build_search_terms_with_minimal_parameters() -> None:
    """Test build_search_terms with only required parameters."""
    filename = "test.py"

    query = build_search_terms(filename, None, None, "")

    assert query == '"test.py"'


def test_validate_file_match() -> None:
    """Test validate_file_match function."""
    assert validate_file_match("src/main/test.py", "test.py", "src/main")
    assert validate_file_match("test.py", "test.py", "")
    assert validate_file_match("test.py", "test.py", "/")
    assert not validate_file_match("src/main/other.py", "test.py", "src/main")
    assert not validate_file_match("src/test/test.py", "test.py", "src/main")


@pytest.mark.asyncio
async def test_process_file_patterns() -> None:
    """Test process_file_patterns function."""
    mock_client = AsyncMock()
    mock_results = [
        {
            "path_matches": [{"match": "test.py"}],
            "file": {
                "path": "src/test.py",
                "commit": {
                    "repository": {"name": "test-repo", "mainbranch": {"name": "main"}}
                },
            },
        }
    ]

    async def mock_search_files(
        *args: Any, **kwargs: Any
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        yield [mock_results[0]]

    mock_client.search_files = mock_search_files
    mock_client.get_repository_files.return_value = "file content"

    file_pattern = BitbucketFilePattern(
        path="src", repos=["test-repo"], filenames=["test.py"], skipParsing=False
    )

    results = []
    async for result in process_file_patterns(file_pattern, mock_client):
        results.extend(result)

    assert len(results) == 1
    assert results[0]["content"] == "file content"
    assert results[0]["metadata"]["path"] == "src/test.py"


@pytest.mark.asyncio
async def test_process_file_patterns_with_extensions() -> None:
    """Test process_file_patterns with file extensions."""
    mock_client = AsyncMock()
    search_calls: List[str] = []

    async def mock_search_files(
        query: str,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        search_calls.append(query)
        yield []

    mock_client.search_files = mock_search_files

    file_pattern = BitbucketFilePattern(
        path="src",
        repos=["test-repo"],
        filenames=["test.py", "test.js"],
        skipParsing=False,
    )

    async for _ in process_file_patterns(file_pattern, mock_client):
        pass

    assert len(search_calls) == 2
    assert "ext:py" in search_calls[0]
    assert "ext:js" in search_calls[1]


@pytest.mark.asyncio
async def test_process_file_patterns_skip_non_matching() -> None:
    """Test process_file_patterns skips non-matching files."""
    mock_client = AsyncMock()
    mock_results = [
        {
            "path_matches": [{"match": "test.py"}],
            "file": {
                "path": "other/test.py",  # Different path than expected
                "commit": {
                    "repository": {"name": "test-repo", "mainbranch": {"name": "main"}}
                },
            },
        }
    ]

    async def mock_search_files(
        *args: Any, **kwargs: Any
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        yield [mock_results[0]]

    mock_client.search_files = mock_search_files

    file_pattern = BitbucketFilePattern(
        path="src", repos=["test-repo"], filenames=["test.py"], skipParsing=False
    )

    results = []
    async for result in process_file_patterns(file_pattern, mock_client):
        results.extend(result)

    # Verify no results due to path mismatch
    assert not results
