from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from typing import Any, AsyncIterator

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from gitlab.clients.gitlab_client import GitLabClient
from gitlab.helpers.skill_folder import (
    attach_skill_folder_files,
    find_owning_skill_md_paths,
)
from gitlab.helpers.skill_plugin import (
    PLUGIN_MANIFEST_PATHS,
    PluginProvider,
    detect_directory_providers,
    enrich_file_to_skill,
    matches_skill_path,
    normalize_plugin,
    path_touches_plugin,
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
        client,
        path_entries,
        path_globs,
        project_params,
        emitted_keys,
        selector.include_skill_folder,
    ):
        yield skills


async def resync_skills_incremental(
    client: GitLabClient,
    selector: GitLabSkillSelector,
    project_params: dict[str, Any] | None,
    since: datetime,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Rebuild only the skills whose SKILL.md or bundle files changed since ``since``.

    A project whose compare fails falls back to the full per-project search.
    """
    path_entries = selector.paths
    path_globs = [entry.path for entry in path_entries]
    patterns_by_repo, unrestricted_patterns = _partition_skill_patterns(path_entries)
    repos_scope = [] if unrestricted_patterns else list(patterns_by_repo.keys())
    emitted_keys: set[str] = set()

    async for projects_batch in _iter_projects(client, repos_scope, project_params):
        for project in projects_batch:
            repo = project["path_with_namespace"]
            patterns = list(
                dict.fromkeys(unrestricted_patterns + patterns_by_repo.get(repo, []))
            )
            ref = client._project_tree_ref(project)
            if not patterns or not ref:
                continue

            changed = await client.get_changed_paths_since(project, since, ref)
            if changed is None:
                async for files_batch in client.search_files_matching_patterns(
                    patterns, skip_parsing=True, repositories=[project]
                ):
                    skills = await _build_skills(
                        client,
                        files_batch,
                        path_globs,
                        emitted_keys,
                        selector.include_skill_folder,
                    )
                    if skills:
                        yield skills
                continue

            skill_md_paths = await _changed_skill_md_paths(
                client,
                project,
                ref,
                changed,
                patterns,
                selector.include_skill_folder,
            )
            if not skill_md_paths:
                continue
            files_batch = await client._process_file_batch(
                [
                    {"path": path, "ref": ref, "project_id": project["id"]}
                    for path in sorted(skill_md_paths)
                ],
                repo,
                skip_parsing=True,
            )
            skills = await _build_skills(
                client,
                files_batch,
                path_globs,
                emitted_keys,
                selector.include_skill_folder,
            )
            if skills:
                yield skills


async def _changed_skill_md_paths(
    client: GitLabClient,
    project: dict[str, Any],
    ref: str,
    changed: list[str],
    patterns: list[str],
    include_skill_folder: bool,
) -> set[str]:
    """SKILL.md paths to rebuild: edited skills, plus owners of changed bundle files."""
    direct = {path for path in changed if matches_skill_path(path, patterns)}
    if not include_skill_folder:
        return direct
    owners = await find_owning_skill_md_paths(
        client, project, ref, set(changed), patterns
    )
    return direct | owners


async def _resync_skills_via_tree(
    client: GitLabClient,
    path_entries: list[GitLabSkillPath],
    path_globs: list[str],
    project_params: dict[str, Any] | None,
    emitted_keys: set[str],
    include_skill_folder: bool,
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
            skills = await _build_skills(
                client, files_batch, path_globs, emitted_keys, include_skill_folder
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
                skills = await _build_skills(
                    client, files_batch, path_globs, emitted_keys, include_skill_folder
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


async def _build_skills(
    client: GitLabClient,
    files_batch: list[dict[str, Any]],
    path_globs: list[str],
    emitted_keys: set[str],
    include_skill_folder: bool,
) -> list[dict[str, Any]]:
    skills = _skills_from_files(
        await client._enrich_files_with_repos(files_batch), path_globs, emitted_keys
    )
    if not include_skill_folder:
        return [skill_item for skill_item, _ in skills]
    built = await attach_skill_folder_files(client, skills)
    return [skill_item for skill_item in built if skill_item is not None]


def _skills_from_files(
    enriched: list[dict[str, Any]],
    path_globs: list[str],
    emitted_keys: set[str],
) -> list[tuple[dict[str, Any], str]]:
    """Deduplicated skill raw items, each with its raw SKILL.md content."""
    skills: list[tuple[dict[str, Any], str]] = []
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
        skills.append((skill_item, file_entity["file"]["content"]))
    return skills


async def resync_plugins(
    client: GitLabClient,
    selector: GitLabPluginSelector,
    project_params: dict[str, Any] | None,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    # Projects are processed one page at a time and dropped once yielded, instead
    # of holding every project of the org until the last search path completes.
    async for projects_batch in _iter_projects(client, selector.repos, project_params):
        batch = await _plugins_for_projects(client, projects_batch, selector.providers)
        if batch:
            yield batch


async def resync_plugins_incremental(
    client: GitLabClient,
    selector: GitLabPluginSelector,
    project_params: dict[str, Any] | None,
    since: datetime,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Rebuild only the plugins of projects whose changes touch a plugin manifest or directory."""
    providers = selector.providers
    async for projects_batch in _iter_projects(client, selector.repos, project_params):
        touched: list[dict[str, Any]] = []
        for project in projects_batch:
            if await _plugin_changed(client, project, since, providers):
                touched.append(project)
        if not touched:
            continue
        batch = await _plugins_for_projects(client, touched, providers)
        if batch:
            yield batch


async def _plugin_changed(
    client: GitLabClient,
    project: dict[str, Any],
    since: datetime,
    providers: list[PluginProvider],
) -> bool:
    """True when the project's plugin may have changed since ``since``.

    A failed or partial compare counts as changed, so the project is rebuilt in full.
    """
    ref = client._project_tree_ref(project)
    if not ref:
        return False
    changed = await client.get_changed_paths_since(project, since, ref)
    if changed is None:
        return True
    return any(path_touches_plugin(path, providers) for path in changed)


async def _plugins_for_projects(
    client: GitLabClient,
    projects: list[dict[str, Any]],
    providers: list[PluginProvider],
) -> list[dict[str, Any]]:
    """Build one plugin per project from every manifest and directory marker it has."""
    projects_by_id = {str(project["id"]): project for project in projects}
    accumulated: dict[str, dict[str, Any]] = {}

    # A plugin aggregates manifests spread over several paths (e.g. claude's
    # plugin.json and marketplace.json), so manifests are accumulated per project.
    async for files_batch in client.search_files_matching_patterns(
        plugin_search_paths(providers),
        skip_parsing=False,
        repositories=projects,
    ):
        for file_data in files_batch:
            _accumulate_plugin_file(accumulated, projects_by_id, file_data, providers)

    batch: list[dict[str, Any]] = []
    for entry in accumulated.values():
        plugin = normalize_plugin(
            repository=entry["repo"],
            manifests=entry["manifests"],
            providers=providers,
            directory_supports=detect_directory_providers(entry["paths"], providers),
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
    return batch


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
