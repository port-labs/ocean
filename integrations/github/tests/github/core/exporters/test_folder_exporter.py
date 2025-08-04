from typing import Any
from unittest.mock import AsyncMock, MagicMock
import pytest
from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.folder_exporter import (
    RestFolderExporter,
    _DEFAULT_BRANCH,
    create_path_mapping,
)
from github.core.options import ListFolderOptions, SingleFolderOptions
from integration import FolderSelector, RepositoryBranchMapping as Repo

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
            "type": "tree",
            "size": 0,
            "url": "https://api.github.com/repos/test-org/test-repo/contents/src",
        },
        "__repository": {"name": "test-repo", "default_branch": "main"},
    },
    {
        "folder": {
            "path": "docs",
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
            "type": "tree",
            "size": 0,
            "url": "https://api.github.com/repos/test-org/test-repo/contents/src/components",
        },
        "__repository": {"name": "test-repo", "default_branch": "main"},
    },
    {
        "folder": {
            "path": "src/hooks",
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

    @pytest.mark.parametrize(
        "path, expected_recursive",
        [
            ("", False),
            ("*", False),
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
    async def test_get_paginated_resources(
        self, rest_client: GithubRestClient, monkeypatch: Any
    ) -> None:
        exporter = RestFolderExporter(rest_client)
        repo_mapping = {"test-repo": {"main": ["src/*"], _DEFAULT_BRANCH: ["docs"]}}
        options = ListFolderOptions(repo_mapping=repo_mapping)

        mock_repos = [
            {"name": "test-repo", "default_branch": "develop"},
            {"name": "another-repo", "default_branch": "main"},
        ]

        async def search_results_gen(*args: Any, **kwargs: Any) -> Any:
            yield mock_repos

        search_repositories_mock = MagicMock(return_value=search_results_gen())
        monkeypatch.setattr(
            exporter, "_search_for_repositories", search_repositories_mock
        )

        get_tree_mock = AsyncMock(return_value=TEST_FULL_CONTENTS)
        monkeypatch.setattr(exporter, "_get_tree", get_tree_mock)

        results = [res async for res in exporter.get_paginated_resources(options)]

        search_repositories_mock.assert_called_once_with(repo_mapping.keys())

        # it is called for 'main' and for default branch 'develop' for 'test-repo'
        assert get_tree_mock.call_count == 2
        assert len(results) == 2

        # sort results to have a predictable order for assertions
        results.sort(key=len, reverse=True)

        # Check src/* results
        src_results = results[0]
        assert len(src_results) == 2
        assert src_results[0]["folder"]["path"] == "src/components"
        assert src_results[1]["folder"]["path"] == "src/hooks"
        assert src_results[0]["__repository"]["name"] == "test-repo"

        # Check docs results
        docs_results = results[1]
        assert len(docs_results) == 1
        assert docs_results[0]["folder"]["path"] == "docs"
        assert docs_results[0]["__repository"]["name"] == "test-repo"


def test_create_path_mapping() -> None:
    # Test case 1: Empty list
    assert create_path_mapping([]) == {}

    # Test case 2: Single pattern, single repo, with branch
    patterns = [FolderSelector(path="src", repos=[Repo(name="repo1", branch="main")])]
    expected = {"repo1": {"main": ["src"]}}
    assert create_path_mapping(patterns) == expected

    # Test case 3: Single pattern, single repo, without branch
    patterns = [FolderSelector(path="src", repos=[Repo(name="repo1", branch=None)])]
    expected = {"repo1": {_DEFAULT_BRANCH: ["src"]}}
    assert create_path_mapping(patterns) == expected

    # Test case 4: Multiple repos for a single pattern
    patterns = [
        FolderSelector(
            path="docs",
            repos=[Repo(name="repo1", branch="dev"), Repo(name="repo2", branch="main")],
        )
    ]
    expected = {"repo1": {"dev": ["docs"]}, "repo2": {"main": ["docs"]}}
    assert create_path_mapping(patterns) == expected

    # Test case 5: Multiple patterns for the same repo/branch
    patterns = [
        FolderSelector(path="src", repos=[Repo(name="repo1", branch="main")]),
        FolderSelector(path="tests", repos=[Repo(name="repo1", branch="main")]),
    ]
    expected = {"repo1": {"main": ["src", "tests"]}}
    assert create_path_mapping(patterns) == expected

    # Test case 6: Complex case
    patterns = [
        FolderSelector(
            path="src",
            repos=[Repo(name="repo1", branch="main"), Repo(name="repo2", branch="dev")],
        ),
        FolderSelector(path="docs", repos=[Repo(name="repo1", branch="main")]),
        FolderSelector(path="assets", repos=[Repo(name="repo2", branch=None)]),
    ]
    expected = {
        "repo1": {"main": ["src", "docs"]},
        "repo2": {"dev": ["src"], _DEFAULT_BRANCH: ["assets"]},
    }
    assert create_path_mapping(patterns) == expected
