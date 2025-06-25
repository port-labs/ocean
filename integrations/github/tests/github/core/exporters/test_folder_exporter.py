from typing import Any, AsyncGenerator
import pytest
from unittest.mock import patch
from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.folder_exporter import (
    RestFolderExporter,
)
from port_ocean.context.event import event_context
from github.core.options import SingleFolderOptions, ListFolderOptions

TEST_FILE = {
    "path": "README.md",
    "type": "blob",
    "size": 123,
    "url": "https://api.github.com/repos/test-org/test-repo/contents/README.md",
}

TEST_DIR_1 = {
    "path": "src",
    "type": "tree",
    "size": 0,
    "url": "https://api.github.com/repos/test-org/test-repo/contents/src",
}

TEST_DIR_2 = {
    "path": "docs",
    "type": "tree",
    "size": 0,
    "url": "https://api.github.com/repos/test-org/test-repo/contents/docs",
}

TEST_FULL_CONTENTS = [
    TEST_DIR_1,
    TEST_FILE,
    TEST_DIR_2,
    {
        "path": "src/components",
        "type": "tree",
        "size": 0,
        "url": "https://api.github.com/repos/test-org/test-repo/contents/src/components",
    },
    {
        "path": "src/hooks",
        "type": "tree",
        "size": 0,
        "url": "https://api.github.com/repos/test-org/test-repo/contents/src/hooks",
    },
]

TEST_FOLDERS_ROOT = [
    {
        "folder": {
            "path": "src",
            "name": "src",
            "type": "tree",
            "size": 0,
            "url": "https://api.github.com/repos/test-org/test-repo/contents/src",
        },
        "__repository": {"name": "test-repo", "default_branch": "main"},
    },
    {
        "folder": {
            "path": "docs",
            "name": "docs",
            "type": "tree",
            "size": 0,
            "url": "https://api.github.com/repos/test-org/test-repo/contents/docs",
        },
        "__repository": {"name": "test-repo", "default_branch": "main"},
    },
]

TEST_FOLDERS_SRC = [
    {
        "folder": {
            "path": "src/components",
            "name": "components",
            "type": "tree",
            "size": 0,
            "url": "https://api.github.com/repos/test-org/test-repo/contents/src/components",
        },
        "__repository": {"name": "test-repo", "default_branch": "main"},
    },
    {
        "folder": {
            "path": "src/hooks",
            "name": "hooks",
            "type": "tree",
            "size": 0,
            "url": "https://api.github.com/repos/test-org/test-repo/contents/src/hooks",
        },
        "__repository": {"name": "test-repo", "default_branch": "main"},
    },
]

TEST_REPO_INFO = {"name": "test-repo", "default_branch": "main"}


class TestRestFolderExporter:
    @pytest.mark.asyncio
    async def test_get_resource(self, rest_client: GithubRestClient) -> None:
        exporter = RestFolderExporter(rest_client)
        with pytest.raises(NotImplementedError):
            await exporter.get_resource(
                SingleFolderOptions(repo="test-repo", path="README.md")
            )

    def setup_method(self):
        # Clear the cache before each test method in this class
        # This is crucial if _caches is a class-level dictionary
        RestFolderExporter._caches.clear()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "options, expected_endpoint, initial_expected_params, expected_folders",
        [
            (
                ListFolderOptions(repo=TEST_REPO_INFO, path="", branch="main"),
                "{base_url}/repos/{organization}/test-repo/git/trees/main",
                {},
                TEST_FOLDERS_ROOT + TEST_FOLDERS_SRC,
            ),
            (
                ListFolderOptions(repo=TEST_REPO_INFO, path="src", branch="main"),
                "{base_url}/repos/{organization}/test-repo/git/trees/main",
                {},
                [TEST_FOLDERS_ROOT[0]],
            ),
            (
                ListFolderOptions(repo=TEST_REPO_INFO, path="src/**", branch="main"),
                "{base_url}/repos/{organization}/test-repo/git/trees/main",
                {"recursive": "true"},
                TEST_FOLDERS_SRC,
            ),
            (
                ListFolderOptions(
                    repo=TEST_REPO_INFO, path="src/components", branch="main"
                ),
                "{base_url}/repos/{organization}/test-repo/git/trees/main",
                {"recursive": "true"},
                [TEST_FOLDERS_SRC[0]],  # Only src/components
            ),
        ],
    )
    async def test_get_paginated_resources_with_caching(
        self,
        rest_client: GithubRestClient,
        options: ListFolderOptions,
        expected_endpoint: str,
        initial_expected_params: dict[str, Any],
        expected_folders: list[dict[str, Any]],
    ) -> None:
        async def mock_branch_tree_fetch(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[dict[str, Any], None]:
            # This mock simulates the underlying API call that fetches the tree for a branch.
            # It's called when the cache for (repo, branch, recursive_flag_for_api_call) is missed.
            yield {"tree": TEST_FULL_CONTENTS}

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_branch_tree_fetch
        ) as mock_api_call:
            exporter = RestFolderExporter(rest_client)

            # First call: should fetch from API and populate cache
            async with event_context("test_event_first_call"):
                folders_batch_1: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]
                assert len(folders_batch_1) == 1
                assert folders_batch_1[0] == expected_folders

                mock_api_call.assert_called_once_with(
                    expected_endpoint.format(
                        base_url=rest_client.base_url,
                        organization=rest_client.organization,
                    ),
                    params=initial_expected_params,
                )

            # Second call with the same options: should use cached data
            async with event_context("test_event_second_call_cached"):
                folders_batch_2: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]
                assert len(folders_batch_2) == 1
                assert folders_batch_2[0] == expected_folders

                # Assert that the API was NOT called again (call_count is still 1)
                assert mock_api_call.call_count == 1

    @pytest.mark.parametrize(
        "folder_path, expected_name",
        [
            ("src", "src"),
            ("src/components", "components"),
            ("root/sub/folder", "folder"),
            ("file.txt", "file.txt"),
            ("", ""),
            ("/", ""),
        ],
    )
    def test_get_folder_name(self, folder_path: str, expected_name: str) -> None:
        assert RestFolderExporter._get_folder_name(folder_path) == expected_name

    @pytest.mark.parametrize(
        "path, expected_recursive",
        [
            ("", False),
            ("*", True),
            ("src/*", True),
            ("src", False),
            ("src/components", True),
            ("src/**", True),
        ],
    )
    def test_needs_recursive_search(self, path: str, expected_recursive: bool) -> None:
        assert RestFolderExporter._needs_recursive_search(path) == expected_recursive

    @pytest.mark.parametrize(
        "contents, path, expected_filtered_folders",
        [
            (
                [TEST_DIR_1, TEST_FILE, TEST_DIR_2],
                "",
                [TEST_DIR_1, TEST_DIR_2],
            ),
            (
                [TEST_DIR_1, TEST_FILE, TEST_DIR_2],
                "*",
                [TEST_DIR_1, TEST_DIR_2],
            ),
            (
                TEST_FULL_CONTENTS,
                "src",
                [TEST_DIR_1],  # Only src
            ),
            (
                TEST_FULL_CONTENTS,
                "src/**",
                [
                    {
                        "path": "src/components",
                        "type": "tree",
                        "size": 0,
                        "url": "https://api.github.com/repos/test-org/test-repo/contents/src/components",
                    },
                    {
                        "path": "src/hooks",
                        "type": "tree",
                        "size": 0,
                        "url": "https://api.github.com/repos/test-org/test-repo/contents/src/hooks",
                    },
                ],
            ),
            (
                TEST_FULL_CONTENTS,
                "src/components",
                [
                    {
                        "path": "src/components",
                        "type": "tree",
                        "size": 0,
                        "url": "https://api.github.com/repos/test-org/test-repo/contents/src/components",
                    }
                ],
            ),
            (
                TEST_FULL_CONTENTS,
                "nonexistent",
                [],
            ),
            (
                [],
                "",
                [],
            ),
        ],
    )
    def test_filter_folder_contents(
        self,
        contents: list[dict[str, Any]],
        path: str,
        expected_filtered_folders: list[dict[str, Any]],
    ) -> None:
        assert (
            RestFolderExporter._filter_folder_contents(contents, path)
            == expected_filtered_folders
        )

    @pytest.mark.asyncio
    async def test_folder_caching_across_different_configurations(
        self, rest_client: GithubRestClient
    ) -> None:
        exporter = RestFolderExporter(rest_client)
        # self.setup_method() or RestFolderExporter._caches.clear() is called before this test

        repo1_main_non_recursive_options = ListFolderOptions(
            repo={"name": "repo1", "default_branch": "main"}, branch="main", path=""
        )
        repo1_main_recursive_options = ListFolderOptions(
            repo={"name": "repo1", "default_branch": "main"}, branch="main", path="**/*"
        )  # Path that implies recursive
        repo1_dev_non_recursive_options = ListFolderOptions(
            repo={"name": "repo1", "default_branch": "develop"},
            branch="develop",
            path="",
        )
        repo2_main_non_recursive_options = ListFolderOptions(
            repo={"name": "repo2", "default_branch": "main"}, branch="main", path=""
        )

        # Mock API responses
        # TEST_DIR_1, TEST_DIR_2, TEST_FILE are defined globally in the test file
        tree_repo1_main = [
            TEST_DIR_1,
            TEST_FILE,
        ]  # Non-recursive or specific content for repo1/main
        tree_repo1_main_recursive = (
            TEST_FULL_CONTENTS  # Recursive content for repo1/main
        )
        tree_repo1_dev = [TEST_DIR_2]  # Content for repo1/develop
        tree_repo2_main = [TEST_FILE, TEST_DIR_1, TEST_DIR_2]  # Content for repo2/main

        async def mock_api_call_effect(
            endpoint_url: str, params: dict[str, Any] | None = None, **kwargs: Any
        ):
            is_recursive = params and params.get("recursive") == "true"
            if "repo1" in endpoint_url and "/trees/main" in endpoint_url:
                yield {
                    "tree": (
                        tree_repo1_main_recursive if is_recursive else tree_repo1_main
                    )
                }
            elif (
                "repo1" in endpoint_url and "/trees/develop" in endpoint_url
            ):  # Assuming branch name is in endpoint
                yield {
                    "tree": tree_repo1_dev
                }  # Assuming non-recursive for this simplified test branch
            elif "repo2" in endpoint_url and "/trees/main" in endpoint_url:
                yield {"tree": tree_repo2_main}
            else:  # Fallback, though test should hit specific cases
                yield {"tree": []}

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_api_call_effect
        ) as mock_api_call:
            # Call 1: repo1, main, non-recursive path
            _ = [
                b
                async for b in exporter.get_paginated_resources(
                    repo1_main_non_recursive_options
                )
            ]
            assert mock_api_call.call_count == 1
            call_args_1 = mock_api_call.call_args_list[0]
            assert "repo1" in call_args_1[0][0] and "/trees/main" in call_args_1[0][0]
            assert call_args_1[1].get("params", {}).get("recursive") != "true"

            # Call 2: repo1, main, non-recursive path (cached)
            _ = [
                b
                async for b in exporter.get_paginated_resources(
                    repo1_main_non_recursive_options
                )
            ]
            assert mock_api_call.call_count == 1  # No new call

            # Call 3: repo1, main, recursive path (new API call if cache is per recursive_flag)
            _ = [
                b
                async for b in exporter.get_paginated_resources(
                    repo1_main_recursive_options
                )
            ]
            assert mock_api_call.call_count == 2  # New call for recursive data
            call_args_3 = mock_api_call.call_args_list[1]
            assert "repo1" in call_args_3[0][0] and "/trees/main" in call_args_3[0][0]
            assert call_args_3[1].get("params", {}).get("recursive") == "true"

            # Call 4: repo1, main, recursive path (cached)
            _ = [
                b
                async for b in exporter.get_paginated_resources(
                    repo1_main_recursive_options
                )
            ]
            assert mock_api_call.call_count == 2  # No new call

            # Call 5: repo1, develop branch (new branch, new call)
            _ = [
                b
                async for b in exporter.get_paginated_resources(
                    repo1_dev_non_recursive_options
                )
            ]
            assert mock_api_call.call_count == 3
            call_args_5 = mock_api_call.call_args_list[2]
            assert (
                "repo1" in call_args_5[0][0] and "/trees/develop" in call_args_5[0][0]
            )

            # Call 6: repo2, main branch (new repo, new call)
            _ = [
                b
                async for b in exporter.get_paginated_resources(
                    repo2_main_non_recursive_options
                )
            ]
            assert mock_api_call.call_count == 4
            call_args_6 = mock_api_call.call_args_list[3]
            assert "repo2" in call_args_6[0][0] and "/trees/main" in call_args_6[0][0]
