import pytest
from unittest.mock import AsyncMock, patch
from typing import Any, Dict, List, AsyncGenerator
from bitbucket_cloud.helpers.file_kind import (
    calculate_required_depth,
    calculate_base_path,
    _match_files_with_pattern,
    process_repository,
    process_file_patterns,
    retrieve_matched_file_contents,
    parse_file,
)
from loguru import logger
from integration import BitbucketFilePattern, BitbucketFileSelector
from bitbucket_cloud.client import BitbucketClient


@pytest.mark.parametrize(
    "pattern,depth,expected",
    [
        ("**/*.json", 20, 20),
        ("src/test/*.py", 20, 3),
        ("config.yaml", 20, 1),
        ("a/b/c/d/*.txt", 20, 5),
        ("a/b/c/d/*.txt", 3, 3),
    ],
)
def test_calculate_required_depth(pattern: str, depth: int, expected: int) -> None:
    assert calculate_required_depth(pattern, depth) == expected


@pytest.mark.parametrize(
    "selector,expected",
    [
        (
            BitbucketFileSelector(
                query="true",
                files=BitbucketFilePattern(
                    path="", repos=[], skipParsing=False, depth=20
                ),
            ),
            "/",
        ),
        (
            BitbucketFileSelector(
                query="true",
                files=BitbucketFilePattern(
                    path="config.yaml", repos=[], skipParsing=False, depth=20
                ),
            ),
            "/",
        ),
        (
            BitbucketFileSelector(
                query="true",
                files=BitbucketFilePattern(
                    path="src/config.yaml", repos=[], skipParsing=False, depth=20
                ),
            ),
            "src/",
        ),
        (
            BitbucketFileSelector(
                query="true",
                files=BitbucketFilePattern(
                    path="src/*.yaml", repos=[], skipParsing=False, depth=20
                ),
            ),
            "src/",
        ),
        (
            BitbucketFileSelector(
                query="true",
                files=BitbucketFilePattern(
                    path="src/**/*.yaml", repos=[], skipParsing=False, depth=20
                ),
            ),
            "src/",
        ),
        (
            BitbucketFileSelector(
                query="true",
                files=BitbucketFilePattern(
                    path="**/*.yaml", repos=[], skipParsing=False, depth=20
                ),
            ),
            "/",
        ),
        (
            BitbucketFileSelector(
                query="true",
                files=BitbucketFilePattern(
                    path="a/b/c/*.yaml", repos=[], skipParsing=False, depth=20
                ),
            ),
            "a/b/c/",
        ),
    ],
)
def test_calculate_base_path(selector: BitbucketFileSelector, expected: str) -> None:
    assert calculate_base_path(selector) == expected


@pytest.mark.parametrize(
    "files,pattern,expected_paths",
    [
        (
            [{"path": "config.yaml"}],
            "config.yaml",
            ["config.yaml"],
        ),
        (
            [{"path": "config.yaml"}, {"path": "config.yml"}],
            "config.*",
            ["config.yaml", "config.yml"],
        ),
        (
            [{"path": "src/config.yaml"}, {"path": "src/test/config.yaml"}],
            "src/**/*.yaml",
            ["src/test/config.yaml"],
        ),
        (
            [{"path": "config.yaml"}, {"path": "src/config.yaml"}],
            "**/config.yaml",
            ["config.yaml", "src/config.yaml"],
        ),
        (
            [{"path": "config.yaml"}, {"path": "config.yml"}],
            "*.txt",
            [],
        ),
        (
            [{"path": "config.yaml"}],
            "",
            ["config.yaml"],
        ),
        (
            [
                {"path": "src/test/config.yaml"},
                {"path": "src/test/data/config.yaml"},
                {"path": "test/new/config.yaml"},
                {"path": "config.yaml"},
            ],
            "**/test/**/config.yaml",
            ["test/new/config.yaml", "src/test/data/config.yaml"],
        ),
    ],
)
def test_match_files_with_pattern(
    files: List[Dict[str, str]], pattern: str, expected_paths: List[str]
) -> None:
    matched_files = _match_files_with_pattern(files, pattern)
    logger.info(f"Matched files: {matched_files}")
    assert sorted([f["path"] for f in matched_files]) == sorted(expected_paths)


@pytest.mark.asyncio
async def test_retrieve_matched_file_contents() -> None:
    client = AsyncMock()
    client.get_repository_files.return_value = '{"key": "value"}'

    matched_files = [{"path": "config.json"}]
    repo = {"name": "test-repo"}

    results: List[Dict[str, Any]] = []
    async for result in retrieve_matched_file_contents(
        matched_files, client, "repo-slug", "main", repo
    ):
        results.append(result)

    assert len(results) == 1
    assert results[0]["content"] == '{"key": "value"}'
    assert results[0]["repo"] == repo
    assert results[0]["branch"] == "main"
    assert results[0]["metadata"] == matched_files[0]
    client.get_repository_files.assert_called_once_with(
        "repo-slug", "main", "config.json"
    )


@pytest.mark.parametrize(
    "file_data,expected_content",
    [
        (
            {
                "metadata": {"path": "config.json"},
                "content": '{"key": "value"}',
            },
            {"key": "value"},
        ),
        (
            {
                "metadata": {"path": "config.yaml"},
                "content": "key: value",
            },
            {"key": "value"},
        ),
        (
            {
                "metadata": {"path": "config.txt"},
                "content": "plain text",
            },
            "plain text",
        ),
    ],
)
def test_parse_file(file_data: Dict[str, Any], expected_content: Any) -> None:
    result = parse_file(file_data)
    assert result[0]["content"] == expected_content


@pytest.mark.asyncio
async def test_process_repository() -> None:
    client = AsyncMock(spec=BitbucketClient)

    client.get_repository.return_value = {"mainbranch": {"name": "main"}}

    async def async_iter() -> AsyncGenerator[List[Dict[str, str]], None]:
        yield [{"path": "config.yaml", "type": "commit_file"}]

    client.get_directory_contents.return_value = async_iter()

    client.get_repository_files.return_value = "key: value"

    results: List[List[Dict[str, Any]]] = []
    async for result in process_repository(
        "repo-slug",
        "config.yaml",
        client,
        "/",
        skip_parsing=False,
        batch_size=100,
        depth=2,
    ):
        results.append(result)

    assert len(results) == 1
    assert results[0][0]["content"] == {"key": "value"}
    client.get_repository.assert_called_once_with("repo-slug")
    client.get_directory_contents.assert_called_once_with(
        "repo-slug",
        branch="main",
        path="/",
        params={"pagelen": 100, "max_depth": 1, "q": 'type="commit_file"'},
    )


@pytest.mark.asyncio
async def test_process_file_patterns() -> None:
    client = AsyncMock()
    file_pattern = BitbucketFilePattern(
        path="config.yaml",
        repos=["repo1", "repo2"],
        skipParsing=False,
        depth=2,
    )

    with patch("bitbucket_cloud.helpers.file_kind.process_repository") as mock_process:
        mock_process.return_value = AsyncMock()
        mock_process.return_value.__aiter__.return_value = [[{"content": "value"}]]

        results: List[List[Dict[str, Any]]] = []
        async for result in process_file_patterns(file_pattern, client, base_path="/"):
            results.append(result)

        assert len(results) == 2
        assert mock_process.call_count == 2
        assert results[0] == [{"content": "value"}]


@pytest.mark.asyncio
async def test_process_repository_error_handling() -> None:
    client = AsyncMock()
    client.get_repository.side_effect = Exception("API Error")

    results: List[List[Dict[str, Any]]] = []
    async for result in process_repository(
        "repo-slug",
        "config.yaml",
        client,
        "/",
        skip_parsing=False,
        batch_size=100,
        depth=2,
    ):
        results.append(result)

    assert not results
    client.get_repository.assert_called_once()


@pytest.mark.asyncio
async def test_process_file_patterns_empty_repos() -> None:
    client = AsyncMock()
    file_pattern = BitbucketFilePattern(
        path="config.yaml",
        repos=[],
        skipParsing=False,
        depth=2,
    )

    results: List[List[Dict[str, Any]]] = []
    async for result in process_file_patterns(file_pattern, client):
        results.append(result)

    assert not results
