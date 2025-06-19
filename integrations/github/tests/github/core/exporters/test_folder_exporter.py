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

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "options, expected_endpoint, expected_params, expected_folders",
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
    async def test_get_paginated_resources(
        self,
        rest_client: GithubRestClient,
        options: ListFolderOptions,
        expected_endpoint: str,
        expected_params: dict[str, Any],
        expected_folders: list[dict[str, Any]],
    ) -> None:
        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[dict[str, Any], None]:
            yield {"tree": TEST_FULL_CONTENTS}

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ) as mock_request:
            async with event_context("test_event"):
                exporter = RestFolderExporter(rest_client)
                folders: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(folders) == 1
                assert folders[0] == expected_folders

                mock_request.assert_called_once_with(
                    expected_endpoint.format(
                        base_url=rest_client.base_url,
                        organization=rest_client.organization,
                    ),
                    params=expected_params,
                )

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
