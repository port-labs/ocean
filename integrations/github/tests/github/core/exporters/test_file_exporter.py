import binascii
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import base64
from github.core.exporters.file_exporter.core import RestFileExporter
from github.core.exporters.file_exporter.utils import (
    decode_content,
    parse_content,
    filter_github_tree_entries_by_pattern,
    determine_api_client_type_by_file_size,
    get_graphql_file_metadata,
    build_batch_file_query,
    match_file_path_against_glob_pattern,
    group_file_patterns_by_repositories_in_selector,
    MAX_FILE_SIZE,
    GRAPHQL_MAX_FILE_SIZE,
)
from github.clients.http.rest_client import GithubRestClient
from github.core.options import (
    FileContentOptions,
    FileSearchOptions,
    ListFileSearchOptions,
)
from github.helpers.utils import GithubClientType
from port_ocean.context.event import event_context
from typing import AsyncGenerator, List, Dict, Any

from integration import GithubFilePattern, RepositoryBranchMapping


TEST_FILE_CONTENT = "Hello, World!"
TEST_FILE_CONTENT_BASE64 = base64.b64encode(TEST_FILE_CONTENT.encode()).decode()

TEST_FILE_RESPONSE = {
    "type": "file",
    "encoding": "base64",
    "size": 13,
    "name": "test.txt",
    "path": "test.txt",
    "content": TEST_FILE_CONTENT_BASE64,
    "sha": "abc123",
    "url": "https://api.github.com/repos/test-org/repo1/contents/test.txt",
    "git_url": "https://api.github.com/repos/test-org/repo1/git/blobs/abc123",
    "html_url": "https://github.com/test-org/repo1/blob/main/test.txt",
    "download_url": "https://raw.githubusercontent.com/test-org/repo1/main/test.txt",
}

TEST_REPO_METADATA = {
    "id": 1,
    "name": "repo1",
    "full_name": "test-org/repo1",
    "description": "Test repository",
    "private": False,
    "html_url": "https://github.com/test-org/repo1",
    "default_branch": "main",
}

TEST_TREE_ENTRIES: List[Dict[str, Any]] = [
    {
        "type": "blob",
        "path": "test.txt",
        "size": 13,
        "sha": "abc123",
    },
    {
        "type": "blob",
        "path": "config.yaml",
        "size": 50,
        "sha": "def456",
    },
    {
        "type": "tree",
        "path": "src",
        "sha": "ghi789",
    },
    {
        "type": "blob",
        "path": "large-file.txt",
        "size": MAX_FILE_SIZE + 1000,
        "sha": "jkl012",
    },
]

TEST_JSON_CONTENT = """{"name": "test", "value": 123}"""
TEST_YAML_CONTENT = "name: test\nvalue: 123"


@pytest.mark.asyncio
class TestRestFileExporter:
    async def test_get_resource(self, rest_client: GithubRestClient) -> None:
        exporter = RestFileExporter(rest_client)

        with patch.object(
            rest_client, "send_api_request", AsyncMock(return_value=TEST_FILE_RESPONSE)
        ) as mock_request:
            file_data = await exporter.get_resource(
                FileContentOptions(
                    repo_name="repo1",
                    file_path="test.txt",
                    branch="main",
                )
            )

            assert file_data["content"] == TEST_FILE_CONTENT
            assert file_data["name"] == "test.txt"
            assert file_data["path"] == "test.txt"

            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/repos/{rest_client.organization}/repo1/contents/test.txt",
                params={"ref": "main"},
            )

    async def test_get_resource_large_file(self, rest_client: GithubRestClient) -> None:
        large_file_response = {
            **TEST_FILE_RESPONSE,
            "size": MAX_FILE_SIZE + 1000,
        }

        exporter = RestFileExporter(rest_client)

        with patch.object(
            rest_client, "send_api_request", AsyncMock(return_value=large_file_response)
        ):
            file_data = await exporter.get_resource(
                FileContentOptions(
                    repo_name="repo1",
                    file_path="large-file.txt",
                    branch="main",
                )
            )

            assert file_data["content"] is None
            assert file_data["size"] == MAX_FILE_SIZE + 1000

    async def test_get_paginated_resources(self, rest_client: GithubRestClient) -> None:
        exporter = RestFileExporter(rest_client)

        options = [
            ListFileSearchOptions(
                repo_name="repo1",
                files=[
                    FileSearchOptions(path="*.txt", skip_parsing=False, branch="main"),
                    FileSearchOptions(path="*.yaml", skip_parsing=True, branch="main"),
                ],
            )
        ]

        # Create proper async generator mocks
        async def mock_graphql_generator() -> AsyncGenerator[list[str], None]:
            yield ["file1", "file2"]

        async def mock_rest_generator() -> AsyncGenerator[list[str], None]:
            yield ["file3", "file4"]

        with (
            patch.object(
                exporter, "collect_matched_files", AsyncMock(return_value=([], []))
            ),
            patch.object(
                exporter,
                "get_repository_metadata",
                AsyncMock(return_value=TEST_REPO_METADATA),
            ),
            patch.object(
                exporter, "process_graphql_files", return_value=mock_graphql_generator()
            ),
            patch.object(
                exporter, "process_rest_api_files", return_value=mock_rest_generator()
            ),
        ):
            async with event_context("test_event"):
                results = []
                async for batch in exporter.get_paginated_resources(options):
                    results.extend(batch)

                assert len(results) == 4
                assert results == ["file1", "file2", "file3", "file4"]

    async def test_get_paginated_resources_multiple_repos(
        self, rest_client: GithubRestClient
    ) -> None:
        exporter = RestFileExporter(rest_client)

        options = [
            ListFileSearchOptions(
                repo_name="repo1",
                files=[
                    FileSearchOptions(path="*.txt", skip_parsing=False, branch="main")
                ],
            ),
            ListFileSearchOptions(
                repo_name="repo2",
                files=[
                    FileSearchOptions(path="*.yaml", skip_parsing=True, branch="main")
                ],
            ),
        ]

        # Create proper async generator mocks
        async def mock_graphql_generator() -> AsyncGenerator[list[str], None]:
            yield ["file1"]

        async def mock_rest_generator() -> AsyncGenerator[list[str], None]:
            yield ["file2"]

        with (
            patch.object(
                exporter, "collect_matched_files", AsyncMock(return_value=([], []))
            ),
            patch.object(
                exporter,
                "get_repository_metadata",
                AsyncMock(return_value=TEST_REPO_METADATA),
            ),
            patch.object(
                exporter, "process_graphql_files", return_value=mock_graphql_generator()
            ),
            patch.object(
                exporter, "process_rest_api_files", return_value=mock_rest_generator()
            ),
        ):
            async with event_context("test_event"):
                results = []
                async for batch in exporter.get_paginated_resources(options):
                    results.extend(batch)

                assert len(results) == 2
                assert results == ["file1", "file2"]

    async def test_get_repository_metadata(self, rest_client: GithubRestClient) -> None:
        exporter = RestFileExporter(rest_client)

        with patch.object(
            rest_client, "send_api_request", AsyncMock(return_value=TEST_REPO_METADATA)
        ) as mock_request:
            metadata = await exporter.get_repository_metadata("repo1")

            assert metadata == TEST_REPO_METADATA
            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/repos/{rest_client.organization}/repo1"
            )

    async def test_collect_matched_files(self, rest_client: GithubRestClient) -> None:
        exporter = RestFileExporter(rest_client)

        with (
            patch.object(
                exporter, "get_branch_tree_sha", AsyncMock(return_value="tree-sha")
            ),
            patch.object(
                exporter,
                "get_tree_recursive",
                AsyncMock(return_value=TEST_TREE_ENTRIES),
            ),
            patch.object(
                exporter,
                "get_repository_metadata",
                AsyncMock(return_value=TEST_REPO_METADATA),
            ),
        ):
            file_patterns = [
                FileSearchOptions(path="*.txt", skip_parsing=False, branch="main"),
                FileSearchOptions(path="*.yaml", skip_parsing=True, branch="main"),
            ]

            graphql_files, rest_files = await exporter.collect_matched_files(
                "repo1", file_patterns
            )

            # Both files should be in GraphQL files since they're both small
            assert len(graphql_files) == 2
            assert graphql_files[0]["file_path"] == "test.txt"
            assert graphql_files[0]["skip_parsing"] is False
            assert graphql_files[1]["file_path"] == "config.yaml"
            assert graphql_files[1]["skip_parsing"] is True

            # No REST files since both are small enough for GraphQL
            assert len(rest_files) == 0

    async def test_collect_matched_files_size_threshold(
        self, rest_client: GithubRestClient
    ) -> None:
        exporter = RestFileExporter(rest_client)

        # Create tree entries with files of different sizes
        tree_entries_with_sizes = [
            {
                "type": "blob",
                "path": "small.txt",
                "size": GRAPHQL_MAX_FILE_SIZE,  # Exactly at threshold
                "sha": "abc123",
            },
            {
                "type": "blob",
                "path": "large.txt",
                "size": GRAPHQL_MAX_FILE_SIZE + 1,  # Just over threshold
                "sha": "def456",
            },
            {
                "type": "blob",
                "path": "medium.txt",
                "size": GRAPHQL_MAX_FILE_SIZE - 1,  # Just under threshold
                "sha": "ghi789",
            },
        ]

        with (
            patch.object(
                exporter, "get_branch_tree_sha", AsyncMock(return_value="tree-sha")
            ),
            patch.object(
                exporter,
                "get_tree_recursive",
                AsyncMock(return_value=tree_entries_with_sizes),
            ),
            patch.object(
                exporter,
                "get_repository_metadata",
                AsyncMock(return_value=TEST_REPO_METADATA),
            ),
        ):
            file_patterns = [
                FileSearchOptions(path="*.txt", skip_parsing=False, branch="main"),
            ]

            graphql_files, rest_files = await exporter.collect_matched_files(
                "repo1", file_patterns
            )

            # Files under or at threshold should use GraphQL
            assert len(graphql_files) == 2
            graphql_paths = [f["file_path"] for f in graphql_files]
            assert "small.txt" in graphql_paths
            assert "medium.txt" in graphql_paths

            # Files over threshold should use REST
            assert len(rest_files) == 1
            assert rest_files[0]["file_path"] == "large.txt"

    async def test_collect_matched_files_no_matches(
        self, rest_client: GithubRestClient
    ) -> None:
        exporter = RestFileExporter(rest_client)

        with (
            patch.object(
                exporter, "get_branch_tree_sha", AsyncMock(return_value="tree-sha")
            ),
            patch.object(
                exporter,
                "get_tree_recursive",
                AsyncMock(return_value=TEST_TREE_ENTRIES),
            ),
            patch.object(
                exporter,
                "get_repository_metadata",
                AsyncMock(return_value=TEST_REPO_METADATA),
            ),
        ):
            file_patterns = [
                FileSearchOptions(path="*.py", skip_parsing=False, branch="main"),
            ]

            graphql_files, rest_files = await exporter.collect_matched_files(
                "repo1", file_patterns
            )

            assert len(graphql_files) == 0
            assert len(rest_files) == 0

    async def test_process_rest_api_files(self, rest_client: GithubRestClient) -> None:
        exporter = RestFileExporter(rest_client)

        with (
            patch.object(
                exporter, "get_resource", AsyncMock(return_value=TEST_FILE_RESPONSE)
            ),
            patch.object(
                exporter,
                "get_repository_metadata",
                AsyncMock(return_value=TEST_REPO_METADATA),
            ),
            patch.object(
                exporter.file_processor, "process_file", AsyncMock()
            ) as mock_process,
        ):
            mock_process.return_value = MagicMock()

            files = [
                {
                    "repo_name": "repo1",
                    "file_path": "test.txt",
                    "skip_parsing": False,
                    "branch": "main",
                }
            ]

            results = []
            async for batch in exporter.process_rest_api_files(files):
                results.extend(batch)

            assert len(results) == 1
            mock_process.assert_called_once()

    async def test_process_rest_api_files_no_content(
        self, rest_client: GithubRestClient
    ) -> None:
        exporter = RestFileExporter(rest_client)

        file_response_no_content = {**TEST_FILE_RESPONSE, "content": None}

        with patch.object(
            exporter, "get_resource", AsyncMock(return_value=file_response_no_content)
        ):
            files = [
                {
                    "repo_name": "repo1",
                    "file_path": "test.txt",
                    "skip_parsing": False,
                    "branch": "main",
                }
            ]

            results = []
            async for batch in exporter.process_rest_api_files(files):
                results.extend(batch)

            assert len(results) == 0

    async def test_get_tree_recursive(self, rest_client: GithubRestClient) -> None:
        exporter = RestFileExporter(rest_client)

        tree_response = {"tree": TEST_TREE_ENTRIES}

        with patch.object(
            rest_client, "send_api_request", AsyncMock(return_value=tree_response)
        ) as mock_request:
            tree = await exporter.get_tree_recursive("repo1", "tree-sha")

            assert tree == TEST_TREE_ENTRIES
            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/repos/{rest_client.organization}/repo1/git/trees/tree-sha?recursive=1"
            )

    async def test_fetch_commit_diff(self, rest_client: GithubRestClient) -> None:
        exporter = RestFileExporter(rest_client)

        diff_response = {
            "url": "https://api.github.com/repos/test-org/repo1/compare/before...after",
            "files": [
                {
                    "filename": "test.txt",
                    "status": "modified",
                    "additions": 1,
                    "deletions": 1,
                }
            ],
        }

        with patch.object(
            rest_client, "send_api_request", AsyncMock(return_value=diff_response)
        ) as mock_request:
            diff = await exporter.fetch_commit_diff("repo1", "before-sha", "after-sha")

            assert diff == diff_response
            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/repos/{rest_client.organization}/repo1/compare/before-sha...after-sha"
            )


class TestFileExporterUtils:
    @pytest.mark.asyncio
    async def test_group_file_patterns_by_repositories_in_selector_no_repos_specified(
        self,
    ) -> None:
        """
        Test that when a file selector has no repositories specified, it defaults to all available repositories from the exporter.
        """
        # Arrange
        mock_file_pattern = GithubFilePattern(
            path="**/*.yaml", skipParsing=False, repos=None
        )
        files = [mock_file_pattern]

        repo_exporter = MagicMock()

        async def mock_paginated_resources(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield [
                {"name": "repo1", "default_branch": "main"},
                {"name": "repo2", "default_branch": "master"},
            ]

        repo_exporter.get_paginated_resources = mock_paginated_resources

        repo_type = "private"

        # Act
        result = await group_file_patterns_by_repositories_in_selector(
            files, repo_exporter, repo_type
        )

        # Assert
        assert len(result) == 2

        repo1_result = next(item for item in result if item["repo_name"] == "repo1")
        repo1_files = repo1_result["files"]
        assert repo1_files[0]["path"] == "**/*.yaml"
        assert repo1_files[0]["branch"] == "main"
        assert repo1_files[0]["skip_parsing"] is False

        repo2_result = next(item for item in result if item["repo_name"] == "repo2")
        repo2_files = repo2_result["files"]
        assert repo2_files[0]["path"] == "**/*.yaml"
        assert repo2_files[0]["branch"] == "master"
        assert repo2_files[0]["skip_parsing"] is False

    @pytest.mark.asyncio
    async def test_group_file_patterns_by_repositories_in_selector_with_repos_specified(
        self,
    ) -> None:
        """
        Test that when a file selector has repositories specified, it uses those repositories.
        """
        # Arrange
        mock_file_pattern = GithubFilePattern(
            path="**/*.yaml",
            skipParsing=False,
            repos=[
                RepositoryBranchMapping(name="repo3", branch="dev"),
                RepositoryBranchMapping(name="repo4", branch="main"),
            ],
        )
        files = [mock_file_pattern]

        repo_exporter = MagicMock()  # This should not be used
        repo_type = "private"

        # Act
        result = await group_file_patterns_by_repositories_in_selector(
            files, repo_exporter, repo_type
        )

        # Assert
        assert len(result) == 2

        repo3_result = next(item for item in result if item["repo_name"] == "repo3")
        repo3_files = repo3_result["files"]
        assert repo3_files[0]["path"] == "**/*.yaml"
        assert repo3_files[0]["branch"] == "dev"
        assert repo3_files[0]["skip_parsing"] is False

        repo4_result = next(item for item in result if item["repo_name"] == "repo4")
        repo4_files = repo4_result["files"]
        assert repo4_files[0]["path"] == "**/*.yaml"
        assert repo4_files[0]["branch"] == "main"
        assert repo4_files[0]["skip_parsing"] is False

    def test_decode_content_base64(self) -> None:
        content = decode_content(TEST_FILE_CONTENT_BASE64, "base64")
        assert content == TEST_FILE_CONTENT

    def test_decode_content_unsupported_encoding(self) -> None:
        with pytest.raises(ValueError, match="Unsupported encoding: utf-8"):
            decode_content("test", "utf-8")

    def test_decode_content_invalid_base64(self) -> None:
        with pytest.raises(binascii.Error):
            decode_content("invalid-base64", "base64")

    def test_parse_content_json(self) -> None:
        content = parse_content(TEST_JSON_CONTENT, "config.json")
        assert content == {"name": "test", "value": 123}

    def test_parse_content_yaml(self) -> None:
        content = parse_content(TEST_YAML_CONTENT, "config.yaml")
        assert content == {"name": "test", "value": 123}

    def test_parse_content_yml_extension(self) -> None:
        content = parse_content(TEST_YAML_CONTENT, "config.yml")
        assert content == {"name": "test", "value": 123}

    def test_parse_content_plain_text(self) -> None:
        content = parse_content(TEST_FILE_CONTENT, "test.txt")
        assert content == TEST_FILE_CONTENT

    def test_parse_content_invalid_json(self) -> None:
        # The parse_content function uses yaml.safe_load which can parse some invalid JSON
        # Let's test with truly invalid content that won't be parsed
        content = parse_content("this is not json at all", "config.json")
        assert content == "this is not json at all"

    def test_parse_content_invalid_yaml(self) -> None:
        content = parse_content("invalid: yaml: content:", "config.yaml")
        assert content == "invalid: yaml: content:"

    def test_match_file_path_against_glob_pattern_exact(self) -> None:
        assert match_file_path_against_glob_pattern("test.txt", "test.txt") is True

    def test_match_file_path_against_glob_pattern_glob(self) -> None:
        assert match_file_path_against_glob_pattern("test.txt", "*.txt") is True
        assert match_file_path_against_glob_pattern("config.yaml", "*.yaml") is True
        assert match_file_path_against_glob_pattern("test.txt", "*.yaml") is False

    def test_match_file_path_against_glob_pattern_recursive(self) -> None:
        assert match_file_path_against_glob_pattern("src/test.txt", "**/*.txt") is True
        assert (
            match_file_path_against_glob_pattern("src/nested/test.txt", "**/*.txt")
            is True
        )

    def test_match_file_path_against_glob_pattern_complex_patterns(self) -> None:
        assert (
            match_file_path_against_glob_pattern("src/config.yaml", "src/*.yaml")
            is True
        )
        assert (
            match_file_path_against_glob_pattern("src/nested/config.yaml", "src/*.yaml")
            is False
        )
        assert (
            match_file_path_against_glob_pattern(
                "src/nested/config.yaml", "src/**/*.yaml"
            )
            is True
        )

    def test_determine_api_client_type_by_file_size(self) -> None:
        assert (
            determine_api_client_type_by_file_size(GRAPHQL_MAX_FILE_SIZE)
            == GithubClientType.GRAPHQL
        )
        assert (
            determine_api_client_type_by_file_size(GRAPHQL_MAX_FILE_SIZE + 1)
            == GithubClientType.REST
        )
        assert determine_api_client_type_by_file_size(0) == GithubClientType.GRAPHQL

    def test_filter_github_tree_entries_by_pattern(self) -> None:
        matched = filter_github_tree_entries_by_pattern(TEST_TREE_ENTRIES, "*.txt")

        # Should match test.txt (blob, small size)
        assert len(matched) == 1
        assert matched[0]["path"] == "test.txt"
        assert matched[0]["fetch_method"] == GithubClientType.GRAPHQL

    def test_filter_github_tree_entries_by_pattern_no_matches(self) -> None:
        matched = filter_github_tree_entries_by_pattern(TEST_TREE_ENTRIES, "*.py")
        assert len(matched) == 0

    def test_filter_github_tree_entries_by_pattern_excludes_large_files(self) -> None:
        matched = filter_github_tree_entries_by_pattern(TEST_TREE_ENTRIES, "*")
        # Should not include large-file.txt due to size limit
        assert len(matched) == 2
        paths = [m["path"] for m in matched]
        assert "large-file.txt" not in paths

    def test_filter_github_tree_entries_by_pattern_excludes_trees(self) -> None:
        matched = filter_github_tree_entries_by_pattern(TEST_TREE_ENTRIES, "*")
        # Should not include src directory (tree type)
        paths = [m["path"] for m in matched]
        assert "src" not in paths

    def test_get_graphql_file_metadata(self) -> None:
        metadata = get_graphql_file_metadata(
            "https://api.github.com",
            "test-org",
            "repo1",
            "main",
            "src/test.txt",
            100,
        )

        assert (
            metadata["url"]
            == "https://api.github.com/repos/test-org/repo1/contents/src/test.txt?ref=main"
        )
        assert metadata["size"] == 100

    def test_build_batch_file_query(self) -> None:
        query = build_batch_file_query(
            "repo1",
            "test-org",
            "main",
            ["test1.txt", "test2.txt"],
        )

        assert "query" in query
        assert 'repository(owner: "test-org", name: "repo1")' in query["query"]
        assert 'file_0: object(expression: "main:test1.txt")' in query["query"]
        assert 'file_1: object(expression: "main:test2.txt")' in query["query"]

    def test_build_batch_file_query_empty_list(self) -> None:
        query = build_batch_file_query(
            "repo1",
            "test-org",
            "main",
            [],
        )

        assert "query" in query
        assert 'repository(owner: "test-org", name: "repo1")' in query["query"]
        # Should not contain any file objects
        assert "file_0: object" not in query["query"]
