from __future__ import annotations

import json
from typing import Any

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from gitlab.clients.gitlab_client import GitLabClient
from gitlab.helpers.skill_plugin import (
    PLUGIN_MANIFEST_PATHS,
    detect_directory_providers,
    enrich_file_to_skill,
    matches_skill_path,
    normalize_plugin,
    plugin_search_paths,
    provider_for_manifest_path,
    skill_search_paths,
)
from integration import GitLabPluginSelector, GitLabSkillSelector


async def resync_skills(
    client: GitLabClient,
    selector: GitLabSkillSelector,
    group_params: dict[str, Any] | None,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    path_entries = selector.paths
    path_globs = [entry.path for entry in path_entries]

    # If any path entry has no repos filter, search all repos and filter per entity.
    # Otherwise union the explicit repo lists for the Advanced Search scope.
    if any(not entry.repos for entry in path_entries):
        repositories: list[str] | None = None
    else:
        repositories = (
            list({repo for entry in path_entries for repo in entry.repos}) or None
        )

    search_paths = skill_search_paths(path_globs)
    seen: set[str] = set()
    unique_paths: list[str] = []
    for path in search_paths:
        if path not in seen:
            seen.add(path)
            unique_paths.append(path)

    emitted_keys: set[str] = set()

    def _path_applies(path: str, repo_path: str) -> bool:
        for entry in path_entries:
            if not matches_skill_path(path, [entry.path]):
                continue
            if entry.repos and repo_path not in entry.repos:
                continue
            return True
        return False

    for search_path in unique_paths:
        async for files_batch in client.search_files(
            "blobs",
            search_path,
            repositories,
            True,  # skip_parsing — SKILL.md is markdown
            group_params,
        ):
            enriched = await client._enrich_files_with_repos(files_batch)
            skills: list[dict[str, Any]] = []
            for entity in enriched:
                path = (entity.get("file") or {}).get("path") or ""
                repo = entity.get("repo") or {}
                repo_path = repo.get("path_with_namespace") or ""
                if not _path_applies(path, repo_path):
                    continue
                skill_item = enrich_file_to_skill(entity, path_globs=path_globs)
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
    group_params: dict[str, Any] | None,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    providers = selector.providers
    repositories = selector.repos or None
    known_manifests = {
        path for paths in PLUGIN_MANIFEST_PATHS.values() for path in paths
    }

    # A plugin can aggregate manifests discovered across several search paths
    # (e.g. claude's plugin.json and marketplace.json), so we keep accumulating
    # per project across search paths. We flush projects touched by each
    # search path as soon as it finishes, instead of buffering the whole org
    # in memory and only yielding after every search path has completed.
    # Re-normalizing and re-yielding a project when it gains another manifest
    # is safe: later batches simply upsert over earlier ones.
    by_project: dict[str, dict[str, Any]] = {}

    for search_path in plugin_search_paths(providers):
        is_directory_search = search_path.endswith("/*")
        touched_project_keys: set[str] = set()

        async for files_batch in client.search_files(
            "blobs",
            search_path,
            repositories,
            False,  # parse JSON when applicable
            group_params,
        ):
            enriched = await client._enrich_files_with_repos(files_batch)
            for entity in enriched:
                file_data = entity.get("file") or {}
                repo = entity.get("repo") or {}
                path = file_data.get("path") or ""
                provider = provider_for_manifest_path(path)
                if provider is None or provider not in providers:
                    continue
                if not is_directory_search and path != search_path:
                    continue

                project_key = str(repo.get("id") or repo.get("path_with_namespace"))
                entry = by_project.setdefault(
                    project_key,
                    {
                        "repo": repo,
                        "manifests": {},
                        "paths": set(),
                        "branch": file_data.get("ref"),
                    },
                )
                entry["paths"].add(path)
                touched_project_keys.add(project_key)

                if path not in known_manifests:
                    continue
                content = file_data.get("content")
                if isinstance(content, dict):
                    entry["manifests"][path] = content
                elif isinstance(content, str):
                    try:
                        entry["manifests"][path] = json.loads(content)
                    except Exception:
                        logger.warning(f"Invalid plugin manifest JSON at {path}")

        batch: list[dict[str, Any]] = []
        for project_key in touched_project_keys:
            entry = by_project[project_key]
            directory_supports = detect_directory_providers(entry["paths"], providers)
            plugin = normalize_plugin(
                repository=entry["repo"],
                manifests=entry["manifests"],
                providers=providers,
                directory_supports=directory_supports,
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
            if len(batch) >= 25:
                yield batch
                batch = []
        if batch:
            yield batch
