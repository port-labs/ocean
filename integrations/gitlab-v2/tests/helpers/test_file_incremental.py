from datetime import datetime, timezone
from typing import Any, AsyncIterator, Literal
from unittest.mock import patch

import pytest

from gitlab.helpers.file_incremental import (
    iter_incremental_files,
    path_matches_file_pattern,
    resync_files_incremental,
)
from gitlab.helpers.incremental import (
    compare_is_incomplete,
    load_named_projects,
    oldest_commit_parent,
    project_updated_before_cursor,
)
from gitlab.helpers.utils import file_match_pattern
from integration import FilesSelector, GitLabFilesSelector

CURSOR = datetime(2026, 10, 18, 9, 0, tzinfo=timezone.utc)

PROJECT = {
    "id": 7,
    "path_with_namespace": "group/project",
    "default_branch": "main",
    "updated_at": "2026-10-18T10:00:00Z",
}


def test_pathless_pattern_matches_nested_files() -> None:
    assert file_match_pattern("*.yaml") == "**/*.yaml"
    assert path_matches_file_pattern("service/catalog-info.yaml", "*.yaml")


def test_directory_pattern_matches_full_path() -> None:
    assert file_match_pattern("**/catalog-info.yaml") == "**/catalog-info.yaml"
    assert path_matches_file_pattern(
        "service/catalog-info.yaml", "**/catalog-info.yaml"
    )
    assert not path_matches_file_pattern("README.md", "**/catalog-info.yaml")


def test_project_updated_before_cursor() -> None:
    assert project_updated_before_cursor({"updated_at": "2026-10-01T00:00:00Z"}, CURSOR)
    assert not project_updated_before_cursor(
        {"updated_at": "2026-10-18T09:00:00Z"}, CURSOR
    )
    assert not project_updated_before_cursor({}, CURSOR)


def test_oldest_commit_parent_uses_last_commit() -> None:
    commits = [
        {"id": "new", "parent_ids": ["mid"]},
        {"id": "mid", "parent_ids": ["base"]},
    ]
    assert oldest_commit_parent(commits) == "base"


def test_oldest_commit_parent_is_none_for_root_commit() -> None:
    assert oldest_commit_parent([{"id": "root", "parent_ids": []}]) is None


def test_compare_timeout_is_incomplete() -> None:
    assert compare_is_incomplete({"compare_timeout": True, "diffs": []})
    assert compare_is_incomplete({})
    assert compare_is_incomplete({"diffs": None})
    assert not compare_is_incomplete(
        {"compare_timeout": False, "diffs": [{"new_path": "a", "too_large": True}]}
    )


class _FakeClient:
    def __init__(self) -> None:
        self.commits: list[dict[str, Any]] = []
        self.compare: dict[str, Any] = {"diffs": []}
        self.compare_calls: list[tuple[Any, ...]] = []
        self.processed: list[list[dict[str, Any]]] = []
        self.tree_batches: list[list[dict[str, Any]]] = []
        self.tree_calls = 0
        self.included: dict[str, str] = {"README.md": "readme"}

    async def get_repository_commits(
        self, project_path: str, ref: str, since: datetime
    ) -> AsyncIterator[list[dict[str, Any]]]:
        if self.commits:
            yield self.commits

    async def compare_repository(
        self,
        project_path: str,
        from_sha: str,
        to_sha: str,
        *,
        straight: bool = False,
    ) -> dict[str, Any]:
        self.compare_calls.append((project_path, from_sha, to_sha, straight))
        return self.compare

    async def _process_file_batch(
        self, batch: list[dict[str, Any]], context: str, skip_parsing: bool = False
    ) -> list[dict[str, Any]]:
        self.processed.append(batch)
        return [{"path": item["path"], "content": "body"} for item in batch]

    async def search_files_matching_patterns(
        self, patterns: list[str], **kwargs: Any
    ) -> AsyncIterator[list[dict[str, Any]]]:
        self.tree_calls += 1
        for batch in self.tree_batches:
            yield batch

    async def get_file_content(self, project_id: str, file_path: str, ref: str) -> str:
        return self.included[file_path]

    async def get_project(self, repo: str) -> dict[str, Any]:
        if repo == "group/idle":
            return {
                **PROJECT,
                "path_with_namespace": repo,
                "updated_at": "2020-01-01T00:00:00Z",
            }
        if repo == "group/empty":
            return {"id": 1, "path_with_namespace": repo, "default_branch": None}
        return {**PROJECT, "path_with_namespace": repo}


async def _collect(client: _FakeClient, **overrides: Any) -> list[dict[str, Any]]:
    options: dict[str, Any] = {
        "cursor": CURSOR,
        "search_path": "**/catalog-info.yaml",
        "skip_parsing": False,
        "included_files": [],
    }
    options.update(overrides)
    batches: list[dict[str, Any]] = []
    async for batch in iter_incremental_files(
        client,  # type: ignore[arg-type]
        [PROJECT],
        **options,
    ):
        batches.extend(batch)
    return batches


@pytest.mark.asyncio
async def test_empty_commit_list_skips_compare() -> None:
    client = _FakeClient()
    assert await _collect(client) == []
    assert client.compare_calls == []
    assert client.tree_calls == 0


@pytest.mark.asyncio
async def test_added_and_edited_paths_are_downloaded() -> None:
    client = _FakeClient()
    client.commits = [{"id": "new", "parent_ids": ["base"]}]
    client.compare = {
        "compare_timeout": False,
        "diffs": [
            {
                "new_path": "service/catalog-info.yaml",
                "new_file": False,
                "deleted_file": False,
            },
            {"new_path": "other.txt", "new_file": True, "deleted_file": False},
            {"old_path": "gone.yaml", "deleted_file": True},
        ],
    }

    entities = await _collect(client)

    assert client.compare_calls == [("group/project", "base", "main", True)]
    assert client.processed == [
        [
            {
                "project_id": "7",
                "path": "service/catalog-info.yaml",
                "ref": "main",
            }
        ]
    ]
    assert entities == [
        {
            "file": {"path": "service/catalog-info.yaml", "content": "body"},
            "repo": PROJECT,
        }
    ]
    assert client.tree_calls == 0


@pytest.mark.asyncio
async def test_root_commit_falls_back_to_tree() -> None:
    client = _FakeClient()
    client.commits = [{"id": "root", "parent_ids": []}]
    client.tree_batches = [[{"path": "service/catalog-info.yaml", "content": "tree"}]]

    entities = await _collect(client)

    assert client.compare_calls == []
    assert client.tree_calls == 1
    assert entities[0]["file"]["content"] == "tree"
    assert entities[0]["repo"] is PROJECT


@pytest.mark.asyncio
async def test_compare_timeout_falls_back_to_tree() -> None:
    client = _FakeClient()
    client.commits = [{"id": "new", "parent_ids": ["base"]}]
    client.compare = {"compare_timeout": True, "diffs": []}
    client.tree_batches = [[{"path": "a.yaml", "content": "full"}]]

    entities = await _collect(client)

    assert client.tree_calls == 1
    assert entities[0]["file"]["content"] == "full"


@pytest.mark.asyncio
async def test_included_file_only_falls_back_to_tree() -> None:
    client = _FakeClient()
    client.commits = [{"id": "new", "parent_ids": ["base"]}]
    client.compare = {
        "diffs": [
            {"new_path": "README.md", "new_file": False, "deleted_file": False},
        ]
    }
    client.tree_batches = [
        [{"path": "service/catalog-info.yaml", "content": "catalog"}]
    ]

    entities = await _collect(client, included_files=["README.md"])

    assert client.tree_calls == 1
    assert entities[0]["__includedFiles"] == {"README.md": "readme"}
    assert client.processed == []


@pytest.mark.asyncio
async def test_selector_and_included_file_download_selector_only() -> None:
    client = _FakeClient()
    client.commits = [{"id": "new", "parent_ids": ["base"]}]
    client.compare = {
        "diffs": [
            {
                "new_path": "service/catalog-info.yaml",
                "new_file": False,
                "deleted_file": False,
            },
            {"new_path": "README.md", "new_file": False, "deleted_file": False},
        ]
    }

    entities = await _collect(client, included_files=["README.md"])

    assert client.tree_calls == 0
    assert entities[0]["file"]["path"] == "service/catalog-info.yaml"
    assert entities[0]["__includedFiles"] == {"README.md": "readme"}


class _ResyncClient(_FakeClient):
    def __init__(self) -> None:
        super().__init__()
        self.project_pages: list[list[dict[str, Any]]] = [[PROJECT]]
        self.list_params: dict[str, Any] | None = None
        self.skipped: list[str] = []
        self.search_calls: list[dict[str, Any]] = []

    async def get_projects(
        self,
        params: dict[str, Any] | None = None,
        max_concurrent: int = 10,
        include_languages: bool = False,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        self.list_params = params
        for page in self.project_pages:
            yield page

    def _partition_projects_with_tree_ref(
        self, projects: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[str]]:
        searchable = [project for project in projects if project.get("default_branch")]
        skipped = [
            str(project.get("path_with_namespace", project.get("id")))
            for project in projects
            if not project.get("default_branch")
        ]
        return searchable, skipped

    def _log_skipped_projects_without_default_branch(self, skipped: list[str]) -> None:
        self.skipped = skipped

    async def search_files(
        self, scope: str, query: Any, **kwargs: Any
    ) -> AsyncIterator[list[dict[str, Any]]]:
        self.search_calls.append({"scope": scope, "query": query, **kwargs})
        yield [{"path": "service/catalog-info.yaml", "project_id": "7"}]

    async def _enrich_files_with_repos(
        self, files_batch: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return [{"file": item, "repo": PROJECT} for item in files_batch]


def _selector(
    strategy: Literal[
        "groupSearch", "projectSearch", "repositoryTree"
    ] = "repositoryTree",
    repos: list[str] | None = None,
) -> GitLabFilesSelector:
    return GitLabFilesSelector(
        query="true",
        files=FilesSelector(
            path="**/catalog-info.yaml",
            repos=repos or [],
            searchStrategy=strategy,
        ),
    )


@pytest.mark.asyncio
async def test_repository_tree_lists_projects_updated_after_cursor() -> None:
    client = _ResyncClient()
    client.project_pages = [
        [
            PROJECT,
            {"id": 8, "path_with_namespace": "group/empty", "default_branch": None},
        ]
    ]
    with patch(
        "gitlab.helpers.file_incremental.build_project_params",
        return_value={"min_access_level": 30},
    ):
        batches = [
            batch
            async for batch in resync_files_incremental(
                client, _selector(), CURSOR  # type: ignore[arg-type]
            )
        ]

    assert batches == []
    assert client.search_calls == []
    assert client.compare_calls == []
    assert client.skipped == ["group/empty"]
    assert client.list_params == {
        "min_access_level": 30,
        "order_by": "updated_at",
        "updated_after": CURSOR.isoformat(),
    }


@pytest.mark.asyncio
async def test_project_search_uses_the_resync_search() -> None:
    client = _ResyncClient()
    selector = _selector("projectSearch")
    with patch(
        "gitlab.helpers.file_incremental.build_project_params",
        return_value={"min_access_level": 30},
    ):
        batches = [
            batch
            async for batch in resync_files_incremental(
                client, selector, CURSOR  # type: ignore[arg-type]
            )
        ]

    assert client.compare_calls == []
    assert client.search_calls[0]["strategy"] == "projectSearch"
    assert client.search_calls[0]["params"] == {
        "min_access_level": 30,
        "order_by": "updated_at",
        "updated_after": CURSOR.isoformat(),
    }
    assert batches[0][0]["file"]["path"] == "service/catalog-info.yaml"
    assert batches[0][0]["repo"] is PROJECT


@pytest.mark.asyncio
async def test_project_search_skips_named_repo_before_cursor() -> None:
    client = _ResyncClient()
    selector = _selector("projectSearch", repos=["group/idle"])
    batches = [
        batch
        async for batch in resync_files_incremental(
            client, selector, CURSOR  # type: ignore[arg-type]
        )
    ]

    assert batches == []
    assert client.search_calls == []


@pytest.mark.asyncio
async def test_group_search_uses_the_resync_search() -> None:
    client = _ResyncClient()
    selector = _selector("groupSearch")
    with patch(
        "gitlab.helpers.file_incremental.build_group_params",
        return_value={"active": True},
    ):
        batches = [
            batch
            async for batch in resync_files_incremental(
                client, selector, CURSOR  # type: ignore[arg-type]
            )
        ]

    assert client.compare_calls == []
    assert client.search_calls[0]["strategy"] == "groupSearch"
    assert client.search_calls[0]["params"] == {"active": True}
    assert batches[0][0]["repo"] is PROJECT


@pytest.mark.asyncio
async def test_load_named_projects_skips_idle_and_branchless() -> None:
    client = _FakeClient()
    projects = await load_named_projects(
        client,  # type: ignore[arg-type]
        ["group/project", "group/idle", "group/empty"],
        CURSOR,
    )
    assert [project["path_with_namespace"] for project in projects] == ["group/project"]
