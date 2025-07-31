from typing import Any
import pytest
from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.folder_exporter import (
    RestFolderExporter,
    _DEFAULT_BRANCH,
    create_path_mapping,
    create_search_params,
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
        self, rest_client: GithubRestClient, mocker: Any
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

        search_repositories_mock = mocker.patch.object(
            exporter, "_search_for_repositories", side_effect=search_results_gen
        )
        get_tree_mock = mocker.patch.object(
            exporter, "_get_tree", return_value=TEST_FULL_CONTENTS
        )

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


def test_create_search_params() -> None:
    # Test case 1: Empty list of repos
    assert list(create_search_params([])) == [""]

    # Test case 2: List with less than max_operators repos
    repos = ["repo1", "repo2", "repo3"]
    expected = ["repo1+in+nameORrepo2+in+nameORrepo3+in+name"]
    assert list(create_search_params(repos)) == expected

    # Test case 3: List with exactly max_operators + 1 repos (default is 5+1=6).
    # All repo names are short, so they should fit in one query.
    repos = ["r1", "r2", "r3", "r4", "r5", "r6"]
    expected = [
        "r1+in+nameORr2+in+nameORr3+in+nameORr4+in+nameORr5+in+nameORr6+in+name"
    ]
    assert list(create_search_params(repos)) == expected

    # Test case 4: List with more than max_operators + 1 repos.
    repos = ["r1", "r2", "r3", "r4", "r5", "r6", "r7"]
    expected = [
        "r1+in+nameORr2+in+nameORr3+in+nameORr4+in+nameORr5+in+nameORr6+in+name",
        "r7+in+name",
    ]
    assert list(create_search_params(repos)) == expected

    # Test case 5: List of repos where the total length exceeds the character limit.
    # A repo name of length 42, becomes 50 characters with "+in+name".
    # 5 such repos with 4 "OR"s is 5 * 50 + 4 * 2 = 258 characters, which is > 256.
    # So the query should be split into a chunk of 4 and a chunk of 3.
    repo_base = "a" * 40
    repos = [f"{repo_base}-{i}" for i in range(7)]
    expected = [
        "OR".join([f"{r}+in+name" for r in repos[:4]]),
        "OR".join([f"{r}+in+name" for r in repos[4:]]),
    ]
    assert list(create_search_params(repos)) == expected

    # Test case 6: A single repo name that is too long to fit in a query.
    long_repo_name = "a" * 250
    repos = [long_repo_name]
    # The function logs a warning and aborts by yielding an empty string.
    assert list(create_search_params(repos)) == [""]
