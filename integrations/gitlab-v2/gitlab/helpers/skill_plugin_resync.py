from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, AsyncIterator

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from gitlab.clients.gitlab_client import GitLabClient
from gitlab.helpers.skill_plugin import (
    PLUGIN_MANIFEST_PATHS,
    PluginProvider,
    detect_directory_providers,
    enrich_file_to_skill,
    normalize_plugin,
    plugin_search_paths,
    provider_for_manifest_path,
)
from integration import GitLabPluginSelector, GitLabSkillPath, GitLabSkillSelector

KNOWN_MANIFEST_PATHS = {
    path for paths in PLUGIN_MANIFEST_PATHS.values() for path in paths
}


async def resync_skills(
    client: GitLabClient,
    selector: GitLabSkillSelector,
    project_params: dict[str, Any] | None,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    path_entries = selector.paths
    path_globs = [entry.path for entry in path_entries]
    emitted_keys: set[str] = set()

    async for skills in _resync_skills_via_tree(
        client, path_entries, path_globs, project_params, emitted_keys
    ):
        yield skills


async def _resync_skills_via_tree(
    client: GitLabClient,
    path_entries: list[GitLabSkillPath],
    path_globs: list[str],
    project_params: dict[str, Any] | None,
    emitted_keys: set[str],
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """One minimized tree-walk set per project, matching all applicable globs."""
    patterns_by_repo, unrestricted_patterns = _partition_skill_patterns(path_entries)

    # Common case: same globs for every project — concurrent tree walks.
    if unrestricted_patterns and not patterns_by_repo:
        async for files_batch in client.search_files_matching_patterns(
            unrestricted_patterns,
            skip_parsing=True,
            params=project_params,
        ):
            skills = _skills_from_files(
                await client._enrich_files_with_repos(files_batch),
                path_globs,
                emitted_keys,
            )
            if skills:
                yield skills
        return

    repos_scope = [] if unrestricted_patterns else list(patterns_by_repo.keys())
    async for projects_batch in _iter_projects(client, repos_scope, project_params):
        for project in projects_batch:
            repo = project["path_with_namespace"]
            patterns = list(
                dict.fromkeys(unrestricted_patterns + patterns_by_repo.get(repo, []))
            )
            if not patterns:
                continue
            async for files_batch in client.search_files_matching_patterns(
                patterns,
                skip_parsing=True,
                repositories=[project],
            ):
                skills = _skills_from_files(
                    await client._enrich_files_with_repos(files_batch),
                    path_globs,
                    emitted_keys,
                )
                if skills:
                    yield skills


def _partition_skill_patterns(
    path_entries: list[GitLabSkillPath],
) -> tuple[dict[str, list[str]], list[str]]:
    patterns_by_repo: dict[str, list[str]] = defaultdict(list)
    unrestricted: list[str] = []
    for entry in path_entries:
        if not entry.repos:
            unrestricted.append(entry.path)
            continue
        for repo in entry.repos:
            patterns_by_repo[repo].append(entry.path)
    return patterns_by_repo, unrestricted


def _skills_from_files(
    enriched: list[dict[str, Any]],
    path_globs: list[str],
    emitted_keys: set[str],
) -> list[dict[str, Any]]:
    skills: list[dict[str, Any]] = []
    for file_entity in enriched:
        skill_item = enrich_file_to_skill(file_entity, path_globs=path_globs)
        if not skill_item:
            continue
        key = (
            f"{(skill_item.get('repo') or {}).get('id')}:"
            f"{skill_item['skill']['skillMdPath']}"
        )
        if key in emitted_keys:
            continue
        emitted_keys.add(key)
        skills.append(skill_item)
    return skills


async def resync_plugins(
    client: GitLabClient,
    selector: GitLabPluginSelector,
    project_params: dict[str, Any] | None,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    providers = selector.providers
    search_paths = plugin_search_paths(providers)

    # A plugin aggregates manifests spread over several paths (e.g. claude's
    # plugin.json and marketplace.json), so manifests are accumulated per
    # project. Projects are processed one page at a time and dropped once
    # yielded, instead of holding every project of the org until the last
    # search path completes.
    async for projects_batch in _iter_projects(client, selector.repos, project_params):
        projects_by_id = {str(project["id"]): project for project in projects_batch}
        accumulated: dict[str, dict[str, Any]] = {}

        async for files_batch in client.search_files_matching_patterns(
            search_paths,
            skip_parsing=False,
            repositories=projects_batch,
        ):
            for file_data in files_batch:
                _accumulate_plugin_file(
                    accumulated, projects_by_id, file_data, providers
                )

        batch: list[dict[str, Any]] = []
        for entry in accumulated.values():
            plugin = normalize_plugin(
                repository=entry["repo"],
                manifests=entry["manifests"],
                providers=providers,
                directory_supports=detect_directory_providers(
                    entry["paths"], providers
                ),
            )
            if not plugin:
                continue
            batch.append(
                {
                    "plugin": plugin,
                    "repo": entry["repo"],
                    "__branch": entry.get("branch")
                    or entry["repo"].get("default_branch")
                    or "main",
                }
            )
        if batch:
            yield batch


async def _iter_projects(
    client: GitLabClient,
    repos: list[str],
    project_params: dict[str, Any] | None,
) -> AsyncIterator[list[dict[str, Any]]]:
    """Yield the projects to scan, one page at a time."""
    if repos:
        projects = [await client.get_project(repo) for repo in repos]
        yield [project for project in projects if project]
        return

    async for projects_batch in client.get_projects(params=project_params):
        yield projects_batch


def _accumulate_plugin_file(
    accumulated: dict[str, dict[str, Any]],
    projects_by_id: dict[str, dict[str, Any]],
    file_data: dict[str, Any],
    providers: list[PluginProvider],
) -> None:
    path = file_data.get("path") or ""
    provider = provider_for_manifest_path(path)
    if provider is None or provider not in providers:
        return

    project_key = str(file_data.get("project_id"))
    project = projects_by_id.get(project_key)
    if project is None:
        return

    entry = accumulated.setdefault(
        project_key,
        {
            "repo": project,
            "manifests": {},
            "paths": set(),
            "branch": file_data.get("ref"),
        },
    )
    entry["paths"].add(path)

    if path not in KNOWN_MANIFEST_PATHS:
        return
    content = file_data.get("content")
    if isinstance(content, dict):
        entry["manifests"][path] = content
    elif isinstance(content, str):
        try:
            entry["manifests"][path] = json.loads(content)
        except json.JSONDecodeError:
            logger.warning(f"Invalid plugin manifest JSON at {path}")
