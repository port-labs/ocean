from datetime import datetime, timezone
from typing import Any, AsyncIterator
from unittest.mock import patch

import pytest

from gitlab.helpers.folder_incremental import (
    ancestor_directories,
    iter_incremental_folders,
    path_matches_folder_pattern,
    resync_folders_incremental,
)
from integration import FolderPattern, GitlabFolderSelector, RepositoryBranchMapping

CURSOR = datetime(2026, 10, 18, 9, 0, tzinfo=timezone.utc)

PROJECT = {
    "id": 7,
    "path_with_namespace": "group/project",
    "default_branch": "main",
    "updated_at": "2026-10-18T10:00:00Z",
}


def test_ancestor_directories() -> None:
    assert ancestor_directories(["apps/service-a/src/main.py", "README.md"]) == {
        "apps",
        "apps/service-a",
        "apps/service-a/src",
    }


def test_wildcard_folder_pattern_matching() -> None:
    assert path_matches_folder_pattern("apps/service-a", "apps/*")
    assert not path_matches_folder_pattern("apps/service-a/src", "apps/*")
    assert path_matches_folder_pattern("apps/service-a/terraform", "**/terraform")


def test_concrete_folder_pattern_matching() -> None:
    assert path_matches_folder_pattern("src", "src")
    assert path_matches_folder_pattern("src/folder1", "src")
    assert not path_matches_folder_pattern("src/folder1/nested", "src")
    assert path_matches_folder_pattern("top", "")
    assert not path_matches_folder_pattern("top/nested", "")


class _FakeFolderClient:
    def __init__(self) -> None:
        self.commits: list[dict[str, Any]] = []
        self.compare: dict[str, Any] = {"diffs": []}
        self.compare_calls: list[tuple[Any, ...]] = []
        self.tree_calls: list[tuple[str, str, str]] = []
        self.tree_items: list[dict[str, Any]] = [
            {"type": "tree", "name": "service-a", "path": "apps/service-a"},
            {"type": "tree", "name": "service-b", "path": "apps/service-b"},
            {"type": "blob", "name": "README.md", "path": "apps/README.md"},
        ]
        self.included: dict[str, str] = {"README.md": "readme"}
        self.project_pages: list[list[dict[str, Any]]] = [[PROJECT]]
        self.list_params: dict[str, Any] | None = None
        self.skipped: list[str] = []

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

    async def get_repository_tree(
        self,
        project: dict[str, Any],
        path: str,
        ref: str = "main",
        *,
        recursive: bool | None = None,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        self.tree_calls.append((project["path_with_namespace"], path, ref))
        yield self.tree_items

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


async def _collect(client: _FakeFolderClient, **overrides: Any) -> list[dict[str, Any]]:
    options: dict[str, Any] = {
        "cursor": CURSOR,
        "path": "apps/*",
        "folder_selectors": [FolderPattern(path="apps/*")],
        "included_files": [],
    }
    options.update(overrides)
    batches: list[dict[str, Any]] = []
    async for batch in iter_incremental_folders(client, [PROJECT], **options):
        batches.extend(batch)
    return batches


@pytest.mark.asyncio
async def test_empty_commit_list_skips_compare_and_tree() -> None:
    client = _FakeFolderClient()
    assert await _collect(client) == []
    assert client.compare_calls == []
    assert client.tree_calls == []


@pytest.mark.asyncio
async def test_changed_file_emits_only_affected_folder() -> None:
    client = _FakeFolderClient()
    client.commits = [{"id": "new", "parent_ids": ["base"]}]
    client.compare = {
        "compare_timeout": False,
        "diffs": [
            {
                "new_path": "apps/service-a/main.py",
                "new_file": False,
                "deleted_file": False,
            },
        ],
    }

    entities = await _collect(client)

    assert client.compare_calls == [("group/project", "base", "main", True)]
    assert client.tree_calls == [("group/project", "apps/*", "main")]
    assert len(entities) == 1
    assert entities[0] == {
        "folder": {"type": "tree", "name": "service-a", "path": "apps/service-a"},
        "repo": PROJECT,
        "__branch": "main",
    }


@pytest.mark.asyncio
async def test_unrelated_file_change_skips_tree() -> None:
    client = _FakeFolderClient()
    client.commits = [{"id": "new", "parent_ids": ["base"]}]
    client.compare = {
        "compare_timeout": False,
        "diffs": [
            {"new_path": "docs/guide.md", "new_file": True, "deleted_file": False},
        ],
    }

    assert await _collect(client) == []
    assert client.tree_calls == []


@pytest.mark.asyncio
async def test_root_commit_falls_back_to_all_matching_folders() -> None:
    client = _FakeFolderClient()
    client.commits = [{"id": "root", "parent_ids": []}]

    entities = await _collect(client)

    assert client.compare_calls == []
    assert [e["folder"]["path"] for e in entities] == [
        "apps/service-a",
        "apps/service-b",
    ]


@pytest.mark.asyncio
async def test_compare_timeout_falls_back_to_all_matching_folders() -> None:
    client = _FakeFolderClient()
    client.commits = [{"id": "new", "parent_ids": ["base"]}]
    client.compare = {"compare_timeout": True, "diffs": []}

    entities = await _collect(client)

    assert [e["folder"]["path"] for e in entities] == [
        "apps/service-a",
        "apps/service-b",
    ]


@pytest.mark.asyncio
async def test_included_file_change_falls_back_and_enriches_all_folders() -> None:
    client = _FakeFolderClient()
    client.commits = [{"id": "new", "parent_ids": ["base"]}]
    client.compare = {
        "diffs": [
            {"new_path": "README.md", "new_file": False, "deleted_file": False},
        ]
    }

    entities = await _collect(client, included_files=["README.md"])

    assert [e["folder"]["path"] for e in entities] == [
        "apps/service-a",
        "apps/service-b",
    ]
    assert entities[0]["__includedFiles"] == {"README.md": "readme"}
    assert entities[1]["__includedFiles"] == {"README.md": "readme"}


@pytest.mark.asyncio
async def test_resync_folders_incremental_all_projects_uses_updated_after() -> None:
    client = _FakeFolderClient()
    client.project_pages = [
        [
            PROJECT,
            {"id": 8, "path_with_namespace": "group/empty", "default_branch": None},
        ]
    ]
    selector = GitlabFolderSelector(
        query="true",
        folders=[FolderPattern(path="apps/*")],
    )
    with patch(
        "gitlab.helpers.folder_incremental.build_project_params",
        return_value={"min_access_level": 30},
    ):
        batches = [
            batch
            async for batch in resync_folders_incremental(client, selector, CURSOR)
        ]

    assert batches == []
    assert client.skipped == ["group/empty"]
    assert client.list_params == {
        "min_access_level": 30,
        "order_by": "updated_at",
        "updated_after": CURSOR.isoformat(),
    }


@pytest.mark.asyncio
async def test_resync_folders_incremental_named_repos_uses_branch_and_skips_idle() -> (
    None
):
    client = _FakeFolderClient()
    client.commits = [{"id": "new", "parent_ids": ["base"]}]
    client.compare = {
        "diffs": [
            {
                "new_path": "apps/service-b/config.yaml",
                "new_file": False,
                "deleted_file": False,
            },
        ]
    }
    selector = GitlabFolderSelector(
        query="true",
        folders=[
            FolderPattern(
                path="apps/*",
                repos=[
                    RepositoryBranchMapping(name="group/project", branch="develop"),
                    RepositoryBranchMapping(name="group/idle", branch="main"),
                ],
            )
        ],
    )

    batches = [
        batch async for batch in resync_folders_incremental(client, selector, CURSOR)
    ]

    assert len(batches) == 1
    assert batches[0][0]["folder"]["path"] == "apps/service-b"
    assert batches[0][0]["__branch"] == "develop"
    assert client.compare_calls == [("group/project", "base", "develop", True)]
