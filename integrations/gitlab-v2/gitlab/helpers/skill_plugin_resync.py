from __future__ import annotations

import json
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
from gitlab.helpers.utils import build_search_query
from integration import GitLabPluginSelector, GitLabSkillSelector

# Skills and plugins live in dot-directories that GitLab's Advanced Search does
# not reliably index, so discovery always walks the repository tree instead.
TREE_SEARCH_STRATEGY = "repositoryTree"

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

    for entry in path_entries:
        async for files_batch in client.search_files(
            "blobs",
            build_search_query(entry.path),
            skip_parsing=True,  # SKILL.md is markdown
            repositories=entry.repos or None,
            params=project_params,
            strategy=TREE_SEARCH_STRATEGY,
        ):
            enriched = await client._enrich_files_with_repos(files_batch)
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
            if skills:
                yield skills


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

        for search_path in search_paths:
            async for files_batch in client.search_files(
                "blobs",
                build_search_query(search_path),
                skip_parsing=False,  # parse JSON when applicable
                repositories=[
                    project["path_with_namespace"] for project in projects_batch
                ],
                strategy=TREE_SEARCH_STRATEGY,
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
