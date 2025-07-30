from typing import Any, NamedTuple
import pytest
from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.folder_exporter import (
    RestFolderExporter,
    create_path_mapping,
    create_search_params,
)
from github.core.options import SingleFolderOptions

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


Repo = NamedTuple("Repo", [("name", str), ("branch", str | None)])
FolderSelector = NamedTuple("FolderSelector", [("path", str), ("repos", list[Repo])])


def test_create_pattern_mapping() -> None:
    # Test case 1: Empty list
    assert create_path_mapping([]) == {}

    # Test case 2: Single pattern, single repo, with branch
    patterns = [FolderSelector("src", [Repo("repo1", "main")])]
    expected = {"repo1": {"main": ["src"]}}
    assert create_path_mapping(patterns) == expected

    # Test case 3: Single pattern, single repo, without branch
    patterns = [FolderSelector("src", [Repo("repo1", None)])]
    expected = {"repo1": {"default": ["src"]}}
    assert create_path_mapping(patterns) == expected

    # Test case 4: Multiple repos for a single pattern
    patterns = [FolderSelector("docs", [Repo("repo1", "dev"), Repo("repo2", "main")])]
    expected = {"repo1": {"dev": ["docs"]}, "repo2": {"main": ["docs"]}}
    assert create_path_mapping(patterns) == expected

    # Test case 5: Multiple patterns for the same repo/branch
    patterns = [
        FolderSelector("src", [Repo("repo1", "main")]),
        FolderSelector("tests", [Repo("repo1", "main")]),
    ]
    expected = {"repo1": {"main": ["src", "tests"]}}
    assert create_path_mapping(patterns) == expected

    # Test case 6: Complex case
    patterns = [
        FolderSelector("src", [Repo("repo1", "main"), Repo("repo2", "dev")]),
        FolderSelector("docs", [Repo("repo1", "main")]),
        FolderSelector("assets", [Repo("repo2", None)]),
    ]
    expected = {
        "repo1": {"main": ["src", "docs"]},
        "repo2": {"dev": ["src"], "default": ["assets"]},
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
    with pytest.raises(
        ValueError, match=f"Repository name '{long_repo_name}' is too long"
    ):
        list(create_search_params(repos))
