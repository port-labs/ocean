"""Incremental file sync.

``repositoryTree`` lists commits since the cursor, then one straight compare,
and downloads files that were added or edited. ``projectSearch`` and
``groupSearch`` call the same ``search_files`` path as the full resync.
Deletions are left for full-resync reconciliation. A tree walk is used only
when the compare cannot be trusted, the window starts at the root commit, or
an included file changed on its own.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, AsyncIterator

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from wcmatch import glob

from gitlab.clients.utils import build_group_params, build_project_params
from gitlab.helpers.incremental import (
    build_file_project_params,
    changed_paths_from_diffs,
    compare_is_incomplete,
    included_path_changed,
    load_named_projects,
    oldest_commit_parent,
)
from gitlab.helpers.utils import build_search_query, file_match_pattern
from integration import GitLabFilesSelector


def path_matches_file_pattern(file_path: str, search_path: str) -> bool:
    return glob.globmatch(
        file_path,
        file_match_pattern(search_path),
        flags=glob.GLOBSTAR | glob.DOTGLOB,
    )


def _selector_paths(changed: set[str], search_path: str) -> list[str]:
    return sorted(
        path for path in changed if path_matches_file_pattern(path, search_path)
    )


async def fetch_included_files_content(
    client: Any,
    project: dict[str, Any],
    file_paths: list[str],
) -> dict[str, Any]:
    """Fetch included files for a project. Returns dict of file_path -> content."""
    project_path = project.get("path_with_namespace", str(project.get("id", "")))
    ref = project.get("default_branch", "main")
    included: dict[str, Any] = {}
    for file_path in file_paths:
        try:
            content = await client.get_file_content(project_path, file_path, ref)
            included[file_path] = content
        except Exception as exc:
            logger.debug(
                f"Could not fetch file '{file_path}' "
                f"(project={project_path}, branch={ref}): {exc}"
            )
            included[file_path] = None
    return included


async def _enrich_processed_files(
    client: Any,
    processed: list[dict[str, Any]],
    project: dict[str, Any],
    included_files: list[str],
    included_cache: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    entities = [{"file": item, "repo": project} for item in processed if item]
    if not entities or not included_files:
        return entities
    key = str(project.get("id", project.get("path_with_namespace", "")))
    if key not in included_cache:
        included_cache[key] = await fetch_included_files_content(
            client, project, included_files
        )
    for entity in entities:
        entity["__includedFiles"] = included_cache[key]
    return entities


async def _tree_fallback(
    client: Any,
    project: dict[str, Any],
    *,
    search_path: str,
    skip_parsing: bool,
    included_files: list[str],
    included_cache: dict[str, dict[str, Any]],
) -> AsyncIterator[list[dict[str, Any]]]:
    async for processed in client.search_files_matching_patterns(
        [search_path],
        skip_parsing=skip_parsing,
        repositories=[project],
    ):
        enriched = await _enrich_processed_files(
            client, processed, project, included_files, included_cache
        )
        if enriched:
            yield enriched


async def _project_file_changes(
    client: Any,
    project: dict[str, Any],
    *,
    cursor: datetime,
    search_path: str,
    skip_parsing: bool,
    included_files: list[str],
) -> AsyncIterator[list[dict[str, Any]]]:
    ref = project.get("default_branch")
    if not ref:
        return
    project_path = project.get("path_with_namespace") or str(project.get("id"))
    commits: list[dict[str, Any]] = []
    async for page in client.get_repository_commits(project_path, ref, cursor):
        commits.extend(page)
    if not commits:
        logger.info(
            f"Skipping files for project '{project_path}' on branch '{ref}': "
            f"no commits since {cursor.isoformat()}"
        )
        return

    included_cache: dict[str, dict[str, Any]] = {}

    async def _fallback() -> AsyncIterator[list[dict[str, Any]]]:
        logger.info(
            f"Falling back to repository tree search for project '{project_path}' "
            f"on branch '{ref}'"
        )
        async for batch in _tree_fallback(
            client,
            project,
            search_path=search_path,
            skip_parsing=skip_parsing,
            included_files=included_files,
            included_cache=included_cache,
        ):
            yield batch

    parent = oldest_commit_parent(commits)
    if parent is None:
        async for batch in _fallback():
            yield batch
        return

    compare = await client.compare_repository(project_path, parent, ref, straight=True)
    if compare_is_incomplete(compare):
        async for batch in _fallback():
            yield batch
        return

    changed = changed_paths_from_diffs(compare.get("diffs") or [])
    selector_paths = _selector_paths(changed, search_path)
    if not selector_paths:
        if included_path_changed(changed, included_files):
            async for batch in _fallback():
                yield batch
        return

    stubs = [
        {"project_id": str(project["id"]), "path": path, "ref": ref}
        for path in selector_paths
    ]
    processed = await client._process_file_batch(stubs, project_path, skip_parsing)
    enriched = await _enrich_processed_files(
        client, processed, project, included_files, included_cache
    )
    if enriched:
        yield enriched


async def iter_incremental_files(
    client: Any,
    projects: list[dict[str, Any]],
    *,
    cursor: datetime,
    search_path: str,
    skip_parsing: bool,
    included_files: list[str],
) -> AsyncIterator[list[dict[str, Any]]]:
    """Yield ``{file, repo}`` batches for files added or edited since ``cursor``."""
    for project in projects:
        async for batch in _project_file_changes(
            client,
            project,
            cursor=cursor,
            search_path=search_path,
            skip_parsing=skip_parsing,
            included_files=included_files,
        ):
            yield batch


async def enrich_files_with_included(
    client: Any,
    files_batch: list[dict[str, Any]],
    included_files: list[str],
    included_cache: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attach the project and any ``includedFiles`` to a search result batch."""
    enriched_batch = await client._enrich_files_with_repos(files_batch)
    if not included_files:
        return enriched_batch
    for file_entity in enriched_batch:
        repo = file_entity.get("repo", {})
        repo_key = str(repo.get("id", repo.get("path_with_namespace", "")))
        if repo_key not in included_cache:
            included_cache[repo_key] = await fetch_included_files_content(
                client, repo, included_files
            )
        file_entity["__includedFiles"] = included_cache[repo_key]
    return enriched_batch


async def _resync_files_via_search(
    client: Any,
    selector: GitLabFilesSelector,
    cursor: datetime,
    *,
    max_concurrent: int,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Run ``projectSearch`` or ``groupSearch`` through the full-resync search."""
    strategy = selector.files.search_strategy
    search_path = selector.files.path
    included_files = list(selector.included_files or [])
    repositories = selector.files.repos or None
    if repositories:
        projects = await load_named_projects(client, repositories, cursor)
        repositories = [project["path_with_namespace"] for project in projects]
        if not repositories:
            return
        params: dict[str, Any] | None = None
    elif strategy == "projectSearch":
        params = build_file_project_params(
            build_project_params(
                include_only_active_projects=selector.include_only_active_groups
            ),
            cursor,
        )
    else:
        params = build_group_params(selector.include_only_active_groups)

    included_cache: dict[str, dict[str, Any]] = {}
    async for files_batch in client.search_files(
        "blobs",
        build_search_query(search_path),
        skip_parsing=selector.files.skip_parsing,
        repositories=repositories,
        params=params,
        strategy=strategy,
        max_concurrent=max_concurrent,
    ):
        enriched_batch = await enrich_files_with_included(
            client, files_batch, included_files, included_cache
        )
        if enriched_batch:
            yield enriched_batch


async def resync_files_incremental(
    client: Any,
    selector: GitLabFilesSelector,
    cursor: datetime,
    *,
    max_concurrent: int = 10,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Upsert files added or edited since ``cursor``. Deletions stay on full resync."""
    if selector.files.search_strategy != "repositoryTree":
        async for batch in _resync_files_via_search(
            client, selector, cursor, max_concurrent=max_concurrent
        ):
            yield batch
        return

    included_files = list(selector.included_files or [])
    search_path = selector.files.path
    skip_parsing = selector.files.skip_parsing
    repositories = selector.files.repos or None

    async def _files(
        projects: list[dict[str, Any]],
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for batch in iter_incremental_files(
            client,
            projects,
            cursor=cursor,
            search_path=search_path,
            skip_parsing=skip_parsing,
            included_files=included_files,
        ):
            yield batch

    if repositories:
        async for batch in _files(
            await load_named_projects(client, repositories, cursor)
        ):
            yield batch
        return

    params = build_file_project_params(
        build_project_params(
            include_only_active_projects=selector.include_only_active_groups
        ),
        cursor,
    )
    async for projects_batch in client.get_projects(
        params=params,
        max_concurrent=max_concurrent,
        include_languages=False,
    ):
        searchable, skipped = client._partition_projects_with_tree_ref(projects_batch)
        client._log_skipped_projects_without_default_branch(skipped)
        async for batch in _files(searchable):
            yield batch
