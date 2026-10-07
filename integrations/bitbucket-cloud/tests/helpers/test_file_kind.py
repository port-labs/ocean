import pytest
from unittest.mock import AsyncMock, patch
from httpx import HTTPStatusError, Request, Response
from bitbucket_cloud.helpers.file_kind import (
    build_search_terms,
    extract_filename_extension,
    process_file_patterns,
    validate_file_match,
)
from integration import BitbucketFilePattern
from bitbucket_cloud.helpers.exceptions import BitbucketFileWalkError
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
    path = "/"  # Using root path as minimal value

    query = build_search_terms(filename, None, path, "")

    assert query == '"test.py" path:/'


@pytest.mark.parametrize(
    ("filename", "extension"),
    [
        (".nvmrc", ""),
        (".gitignore", ""),
        (".env", ""),
        ("Dockerfile", ""),
        ("test.py", "py"),
        ("test.js", "js"),
        ("catalog.yaml", "yaml"),
        ("package.json", "json"),
        ("archive.tar.gz", "gz"),
        (".eslintrc.js", "js"),
    ],
)
def test_extract_filename_extension(filename: str, extension: str) -> None:
    """Dotfiles have no extension; ordinary files keep theirs."""
    assert extract_filename_extension(filename) == extension


def test_validate_file_match() -> None:
    """Test validate_file_match function."""
    assert validate_file_match("src/main/test.py", "test.py", "src/main")
    assert validate_file_match("test.py", "test.py", "")
    assert validate_file_match("test.py", "test.py", "/")
    assert validate_file_match(".nvmrc", ".nvmrc", "/")
    assert validate_file_match("src/.gitignore", ".gitignore", "src")
    assert validate_file_match(".env", ".env", "")
    assert not validate_file_match("src/main/other.py", "test.py", "src/main")
    assert not validate_file_match("src/test/test.py", "test.py", "src/main")


@pytest.mark.parametrize(
    "expected_path",
    ["hello/test", "/hello/test", "/hello/test/", "hello/test/"],
)
def test_validate_file_match_ignores_path_slash_variants(expected_path: str) -> None:
    """Leading/trailing slashes on the configured path must not change matching."""
    assert validate_file_match("hello/test/file.txt", "file.txt", expected_path)
    assert not validate_file_match("hello/other/file.txt", "file.txt", expected_path)


def test_build_search_terms_normalizes_path_slashes() -> None:
    """Search path: qualifier should not keep a leading or trailing slash."""
    for path in ("hello/test", "/hello/test", "/hello/test/", "hello/test/"):
        query = build_search_terms("file.txt", None, path, "txt")
        assert "path:hello/test" in query
        assert "path:/hello/test" not in query
        assert "path:hello/test/" not in query


@pytest.mark.asyncio
async def test_process_file_patterns() -> None:
    """Test process_file_patterns function."""
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

    async def mock_get_repository_files(*args: Any, **kwargs: Any) -> str:
        return "file content"

    # Mock the retrieve_file_content function to return a simple result
    async def mock_retrieve_file_content(
        *args: Any, **kwargs: Any
    ) -> AsyncGenerator[Dict[str, Any], None]:
        yield {
            "content": "file content",
            "metadata": {"path": "src/test.py"},
            "repo": {"name": "test-repo"},
            "branch": "main",
        }

    with patch("bitbucket_cloud.helpers.file_kind.init_client") as mock_init_client:
        mock_client = AsyncMock()
        mock_client.search_files = mock_search_files
        mock_client.get_repository_files = mock_get_repository_files
        mock_init_client.return_value = mock_client

        # Patch the retrieve_file_content function
        with patch(
            "bitbucket_cloud.helpers.file_kind.retrieve_file_content",
            side_effect=mock_retrieve_file_content,
        ):
            file_pattern = BitbucketFilePattern(
                path="src",
                repos=["test-repo"],
                filenames=["test.py"],
                skipParsing=False,
            )

            results = []
            async for result in process_file_patterns(file_pattern):
                results.extend(result)

            assert len(results) == 1
            assert results[0]["content"] == "file content"
            assert results[0]["metadata"]["path"] == "src/test.py"


@pytest.mark.asyncio
async def test_process_file_patterns_keeps_readable_files_when_one_cannot_be_read() -> (
    None
):
    """One unreadable file must not discard the rest, and must still end the kind in error."""
    results = [
        {
            "path_matches": [{"match": "a.yaml"}],
            "file": {
                "path": "a.yaml",
                "commit": {
                    "repository": {"name": "test-repo", "mainbranch": {"name": "main"}}
                },
            },
        },
        {
            "path_matches": [{"match": "b.yaml"}],
            "file": {
                "path": "b.yaml",
                "commit": {
                    "repository": {"name": "test-repo", "mainbranch": {"name": "main"}}
                },
            },
        },
    ]

    async def mock_search_files(
        *args: Any, **kwargs: Any
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        yield results

    async def mock_get_repository_files(
        repo: str, branch: str, path: str
    ) -> str | None:
        return None if path == "a.yaml" else "content of b"

    with patch("bitbucket_cloud.helpers.file_kind.init_client") as mock_init_client:
        mock_client = AsyncMock()
        mock_client.search_files = mock_search_files
        mock_client.get_repository_files = mock_get_repository_files
        mock_init_client.return_value = mock_client

        pattern = BitbucketFilePattern(
            path="/", filenames=["a.yaml", "b.yaml"], skipParsing=True
        )

        yielded: List[Dict[str, Any]] = []
        with pytest.raises(BitbucketFileWalkError) as raised:
            async for batch in process_file_patterns(pattern):
                yielded.extend(batch)

    assert [item["metadata"]["path"] for item in yielded] == ["b.yaml"]
    assert "1 file could not be read" in str(raised.value)
    cause = raised.value.__cause__
    assert isinstance(cause, ExceptionGroup)
    assert [str(error) for error in cause.exceptions] == [
        "Bitbucket returned no content for a.yaml in repository test-repo on branch main"
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [403, 500, 555])
async def test_process_file_patterns_collects_a_failure_about_one_file(
    status: int,
) -> None:
    """A refused repository or a server fault on one file keeps the rest of the walk."""
    results = [
        {
            "path_matches": [{"match": "a.yaml"}],
            "file": {
                "path": "a.yaml",
                "commit": {
                    "repository": {"name": "test-repo", "mainbranch": {"name": "main"}}
                },
            },
        },
        {
            "path_matches": [{"match": "b.yaml"}],
            "file": {
                "path": "b.yaml",
                "commit": {
                    "repository": {"name": "test-repo", "mainbranch": {"name": "main"}}
                },
            },
        },
    ]

    async def mock_search_files(
        *args: Any, **kwargs: Any
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        yield results

    failed = Response(status, request=Request("GET", "https://example/src"))

    async def mock_get_repository_files(repo: str, branch: str, path: str) -> str:
        if path == "a.yaml":
            raise HTTPStatusError(f"{status}", request=failed.request, response=failed)
        return "content of b"

    with patch("bitbucket_cloud.helpers.file_kind.init_client") as mock_init_client:
        mock_client = AsyncMock()
        mock_client.search_files = mock_search_files
        mock_client.get_repository_files = mock_get_repository_files
        mock_init_client.return_value = mock_client

        pattern = BitbucketFilePattern(
            path="/", filenames=["a.yaml", "b.yaml"], skipParsing=True
        )

        yielded: List[Dict[str, Any]] = []
        with pytest.raises(BitbucketFileWalkError) as raised:
            async for batch in process_file_patterns(pattern):
                yielded.extend(batch)

    assert [item["metadata"]["path"] for item in yielded] == ["b.yaml"]
    cause = raised.value.__cause__
    assert isinstance(cause, ExceptionGroup)
    assert isinstance(cause.exceptions[0], HTTPStatusError)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 429])
async def test_process_file_patterns_stops_when_the_credential_or_quota_is_gone(
    status: int,
) -> None:
    """These affect every repository still to be walked, so the walk does not continue."""
    results = [
        {
            "path_matches": [{"match": "a.yaml"}],
            "file": {
                "path": "a.yaml",
                "commit": {
                    "repository": {"name": "test-repo", "mainbranch": {"name": "main"}}
                },
            },
        }
    ]

    async def mock_search_files(
        *args: Any, **kwargs: Any
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        yield results

    response = Response(status, request=Request("GET", "https://example/src"))

    async def mock_get_repository_files(repo: str, branch: str, path: str) -> str:
        raise HTTPStatusError(f"{status}", request=response.request, response=response)

    with patch("bitbucket_cloud.helpers.file_kind.init_client") as mock_init_client:
        mock_client = AsyncMock()
        mock_client.search_files = mock_search_files
        mock_client.get_repository_files = mock_get_repository_files
        mock_init_client.return_value = mock_client

        pattern = BitbucketFilePattern(path="/", filenames=["a.yaml"], skipParsing=True)

        with pytest.raises(HTTPStatusError):
            async for _ in process_file_patterns(pattern):
                pass


@pytest.mark.asyncio
async def test_process_file_patterns_with_extensions() -> None:
    """Test process_file_patterns with file extensions."""
    search_calls: List[str] = []

    async def mock_search_files(
        query: str,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        search_calls.append(query)
        yield []

    with patch("bitbucket_cloud.helpers.file_kind.init_client") as mock_init_client:
        mock_client = AsyncMock()
        mock_client.search_files = mock_search_files
        mock_init_client.return_value = mock_client

        file_pattern = BitbucketFilePattern(
            path="src",
            repos=["test-repo"],
            filenames=["test.py", "test.js"],
            skipParsing=False,
        )

        async for _ in process_file_patterns(file_pattern):
            pass

        assert len(search_calls) == 2
        assert "ext:py" in search_calls[0]
        assert "ext:js" in search_calls[1]


@pytest.mark.asyncio
async def test_process_file_patterns_ingests_dotfiles() -> None:
    """Dotfiles are searched without an ext filter; plain-text content is returned via retrieve_file_content."""
    filenames = [".nvmrc", ".gitignore", ".env"]
    file_contents = {
        ".nvmrc": "18",
        ".gitignore": "node_modules/\n.env\n",
        ".env": "SECRET=value\n",
    }
    search_calls: List[str] = []

    async def mock_search_files(
        query: str,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        search_calls.append(query)
        filename = query.split('"')[1]
        yield [
            {
                "path_matches": [{"match": filename}],
                "file": {
                    "path": filename,
                    "commit": {
                        "repository": {
                            "name": "test-repo",
                            "mainbranch": {"name": "main"},
                        }
                    },
                },
            }
        ]

    async def mock_get_repository_files(
        repo_slug: str, branch: str, file_path: str
    ) -> str:
        return file_contents[file_path]

    with patch("bitbucket_cloud.helpers.file_kind.init_client") as mock_init_client:
        mock_client = AsyncMock()
        mock_client.search_files = mock_search_files
        mock_client.get_repository_files = mock_get_repository_files
        mock_init_client.return_value = mock_client

        file_pattern = BitbucketFilePattern(
            path="/",
            repos=["test-repo"],
            filenames=filenames,
            skipParsing=False,
        )

        results = []
        async for result in process_file_patterns(file_pattern):
            results.extend(result)

    assert [result["metadata"]["path"] for result in results] == filenames
    assert [result["content"] for result in results] == [
        file_contents[filename] for filename in filenames
    ]
    assert len(search_calls) == len(filenames)
    for query, filename in zip(search_calls, filenames):
        assert f'"{filename}"' in query
        assert "ext:" not in query


@pytest.mark.asyncio
async def test_process_file_patterns_keeps_extension_for_regular_files() -> None:
    """Files with a real extension still search by that extension."""
    search_calls: List[str] = []

    async def mock_search_files(
        query: str,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        search_calls.append(query)
        yield []

    with patch("bitbucket_cloud.helpers.file_kind.init_client") as mock_init_client:
        mock_client = AsyncMock()
        mock_client.search_files = mock_search_files
        mock_init_client.return_value = mock_client

        file_pattern = BitbucketFilePattern(
            path="src",
            repos=["test-repo"],
            filenames=["catalog.yaml", "package.json", "archive.tar.gz"],
            skipParsing=False,
        )

        async for _ in process_file_patterns(file_pattern):
            pass

    assert len(search_calls) == 3
    assert "ext:yaml" in search_calls[0]
    assert "ext:json" in search_calls[1]
    assert "ext:gz" in search_calls[2]
    assert "ext:tar" not in search_calls[2]


@pytest.mark.asyncio
async def test_process_file_patterns_skip_non_matching() -> None:
    """Test process_file_patterns skips non-matching files."""
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

    # Mock the retrieve_file_content function to return a simple result
    async def mock_retrieve_file_content(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        return {
            "content": "file content",
            "metadata": {"path": "other/test.py"},
            "repo": {"name": "test-repo"},
            "branch": "main",
        }

    with patch("bitbucket_cloud.helpers.file_kind.init_client") as mock_init_client:
        mock_client = AsyncMock()
        mock_client.search_files = mock_search_files
        mock_init_client.return_value = mock_client

        # Patch the retrieve_file_content function
        with patch(
            "bitbucket_cloud.helpers.file_kind.retrieve_file_content",
            side_effect=mock_retrieve_file_content,
        ):
            file_pattern = BitbucketFilePattern(
                path="src",
                repos=["test-repo"],
                filenames=["test.py"],
                skipParsing=False,
            )

            results = []
            async for result in process_file_patterns(file_pattern):
                results.extend(result)

            # Verify no results due to path mismatch
            assert not results
