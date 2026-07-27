from typing import Any, AsyncIterator, Optional

import pytest

from gitlab.helpers.skill_plugin_resync import resync_plugins, resync_skills
from gitlab.helpers.utils import SearchQuery
from integration import GitLabPluginSelector, GitLabSkillPath, GitLabSkillSelector

SKILL_CONTENT = "---\nname: hello\ndescription: hi\n---\nbody"


class FakeGitLabClient:
    """Minimal stand-in for GitLabClient covering the discovery calls."""

    def __init__(
        self,
        files_by_path: dict[str, list[dict[str, Any]]] | None = None,
        projects: list[dict[str, Any]] | None = None,
    ) -> None:
        self.files_by_path = files_by_path or {}
        self.projects = projects or []
        self.projects_by_id = {str(p["id"]): p for p in self.projects}
        self.search_calls: list[dict[str, Any]] = []
        self.pattern_search_calls: list[dict[str, Any]] = []

    async def search_files(
        self,
        scope: str,
        query: SearchQuery,
        skip_parsing: bool = False,
        repositories: list[str] | None = None,
        params: Optional[dict[str, Any]] = None,
        max_concurrent: int = 10,
        strategy: str = "groupSearch",
    ) -> AsyncIterator[list[dict[str, Any]]]:
        self.search_calls.append(
            {
                "scope": scope,
                "query": query,
                "repositories": repositories,
                "params": params,
                "strategy": strategy,
            }
        )
        files = self.files_by_path.get(query.path, [])
        if files:
            yield files

    async def search_files_matching_patterns(
        self,
        path_patterns: list[str],
        *,
        skip_parsing: bool = False,
        repositories: list[str | dict[str, Any]] | None = None,
        params: Optional[dict[str, Any]] = None,
        max_concurrent: int = 10,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        self.pattern_search_calls.append(
            {
                "path_patterns": path_patterns,
                "repositories": repositories,
                "params": params,
                "skip_parsing": skip_parsing,
            }
        )
        repo_paths: set[str] | None = None
        if repositories:
            repo_paths = {
                (repo["path_with_namespace"] if isinstance(repo, dict) else repo)
                for repo in repositories
            }
        seen: set[str] = set()
        batch: list[dict[str, Any]] = []
        for pattern in path_patterns:
            for file_data in self.files_by_path.get(pattern, []):
                key = f"{file_data.get('project_id')}:{file_data.get('path')}"
                if key in seen:
                    continue
                if repo_paths is not None:
                    project = self.projects_by_id.get(str(file_data["project_id"]))
                    if not project or project["path_with_namespace"] not in repo_paths:
                        continue
                seen.add(key)
                batch.append(file_data)
        if batch:
            yield batch

    async def _enrich_files_with_repos(
        self, files_batch: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return [
            {
                "file": file_data,
                "repo": self.projects_by_id[str(file_data["project_id"])],
            }
            for file_data in files_batch
        ]

    async def get_projects(
        self, params: Optional[dict[str, Any]] = None
    ) -> AsyncIterator[list[dict[str, Any]]]:
        yield self.projects

    async def get_project(self, project_path: str) -> dict[str, Any]:
        return next(
            project
            for project in self.projects
            if project["path_with_namespace"] == project_path
        )


def make_project(project_id: int, path: str) -> dict[str, Any]:
    return {
        "id": project_id,
        "name": path.split("/")[-1],
        "path": path.split("/")[-1],
        "path_with_namespace": path,
        "default_branch": "main",
    }


PROJECT = make_project(1, "group/project")


@pytest.mark.asyncio
async def test_resync_skills_walks_configured_globs_with_tree_strategy() -> None:
    selector = GitLabSkillSelector(
        query="true",
        paths=[
            GitLabSkillPath(path=".cursor/skills/**/SKILL.md"),
            GitLabSkillPath(path="skills/**/SKILL.md", repos=["group/project"]),
        ],
    )
    client = FakeGitLabClient(
        files_by_path={
            ".cursor/skills/**/SKILL.md": [
                {
                    "path": ".cursor/skills/hello/SKILL.md",
                    "content": SKILL_CONTENT,
                    "ref": "main",
                    "project_id": 1,
                }
            ],
            "skills/**/SKILL.md": [],
        },
        projects=[PROJECT],
    )

    batches = [
        batch
        async for batch in resync_skills(client, selector, {"min_access_level": 30})  # type: ignore[arg-type]
    ]

    assert client.search_calls == []
    assert len(client.pattern_search_calls) == 1
    assert set(client.pattern_search_calls[0]["path_patterns"]) == {
        ".cursor/skills/**/SKILL.md",
        "skills/**/SKILL.md",
    }
    assert client.pattern_search_calls[0]["repositories"] == [PROJECT]

    assert len(batches) == 1
    skill = batches[0][0]["skill"]
    assert skill["name"] == "hello"
    assert skill["skillMdPath"] == ".cursor/skills/hello/SKILL.md"
    assert skill["root"] == ".cursor/skills"


@pytest.mark.asyncio
async def test_resync_skills_emits_each_skill_once_across_overlapping_globs() -> None:
    selector = GitLabSkillSelector(
        query="true",
        paths=[
            GitLabSkillPath(path=".cursor/skills/**/SKILL.md"),
            GitLabSkillPath(path="**/SKILL.md"),
        ],
    )
    skill_file = {
        "path": ".cursor/skills/hello/SKILL.md",
        "content": SKILL_CONTENT,
        "ref": "main",
        "project_id": 1,
    }
    client = FakeGitLabClient(
        files_by_path={
            ".cursor/skills/**/SKILL.md": [skill_file],
            "**/SKILL.md": [skill_file],
        },
        projects=[PROJECT],
    )

    batches = [batch async for batch in resync_skills(client, selector, None)]  # type: ignore[arg-type]

    assert sum(len(batch) for batch in batches) == 1
    assert len(client.pattern_search_calls) == 1
    assert set(client.pattern_search_calls[0]["path_patterns"]) == {
        ".cursor/skills/**/SKILL.md",
        "**/SKILL.md",
    }


@pytest.mark.asyncio
async def test_resync_plugins_accumulates_manifests_per_project() -> None:
    selector = GitLabPluginSelector(query="true", providers=["claude", "opencode"])
    client = FakeGitLabClient(
        files_by_path={
            ".claude-plugin/plugin.json": [
                {
                    "path": ".claude-plugin/plugin.json",
                    "content": {"name": "superpowers"},
                    "ref": "main",
                    "project_id": 1,
                }
            ],
            ".opencode/plugins/*": [
                {
                    "path": ".opencode/plugins/superpowers.js",
                    "content": "export default {}",
                    "ref": "main",
                    "project_id": 1,
                }
            ],
        },
        projects=[PROJECT, make_project(2, "group/empty")],
    )

    batches = [
        batch async for batch in resync_plugins(client, selector, {"active": True})  # type: ignore[arg-type]
    ]

    assert client.search_calls == []
    assert len(client.pattern_search_calls) == 1
    assert client.pattern_search_calls[0]["repositories"] == [
        PROJECT,
        make_project(2, "group/empty"),
    ]

    assert len(batches) == 1
    assert len(batches[0]) == 1
    item = batches[0][0]
    assert item["plugin"]["name"] == "superpowers"
    assert item["plugin"]["supports"]["claude"] is True
    assert item["plugin"]["supports"]["opencode"] is True
    assert item["repo"]["path_with_namespace"] == "group/project"
    assert item["__branch"] == "main"


@pytest.mark.asyncio
async def test_resync_plugins_scopes_to_configured_repos() -> None:
    selector = GitLabPluginSelector(
        query="true", providers=["cursor"], repos=["group/project"]
    )
    client = FakeGitLabClient(
        files_by_path={
            ".cursor-plugin/plugin.json": [
                {
                    "path": ".cursor-plugin/plugin.json",
                    "content": {"name": "cursor-plugin"},
                    "ref": "main",
                    "project_id": 1,
                }
            ]
        },
        projects=[PROJECT, make_project(2, "group/other")],
    )

    batches = [batch async for batch in resync_plugins(client, selector, None)]  # type: ignore[arg-type]

    assert client.pattern_search_calls[0]["repositories"] == [PROJECT]
    assert len(batches) == 1
    assert batches[0][0]["plugin"]["supports"]["cursor"] is True


@pytest.mark.asyncio
async def test_resync_plugins_yields_nothing_without_manifests() -> None:
    selector = GitLabPluginSelector(query="true", providers=["cursor"])
    client = FakeGitLabClient(projects=[PROJECT])

    batches = [batch async for batch in resync_plugins(client, selector, None)]  # type: ignore[arg-type]

    assert batches == []
