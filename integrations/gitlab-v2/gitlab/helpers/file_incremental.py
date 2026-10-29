"""Incremental file sync.

``repositoryTree`` lists commits since the cursor, then one straight compare,
and downloads files that were added or edited. ``projectSearch`` and
``groupSearch`` call the same ``search_files`` path as the full resync.
Deletions are left for full-resync reconciliation. A tree walk is used only
when the compare cannot be trusted, the window starts at the root commit, or
an included file changed on its own.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from functools import partial
from typing import Any, AsyncIterator

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.async_iterators import (
    semaphore_async_iterator,
    stream_async_iterators_tasks,
)
from port_ocean.utils.time import convert_str_to_utc_datetime
from wcmatch import glob

from gitlab.clients.gitlab_client import GitLabClient
from gitlab.clients.utils import build_group_params, build_project_params
from gitlab.helpers.incremental import build_file_project_params
from gitlab.helpers.utils import build_search_query, file_match_pattern
from integration import GitLabFilesSelector


def path_matches_file_pattern(file_path: str, search_path: str) -> bool:
    return glob.globmatch(
        file_path,
        file_match_pattern(search_path),
        flags=glob.GLOBSTAR | glob.DOTGLOB,
    )


def project_updated_before_cursor(project: dict[str, Any], cursor: datetime) -> bool:
    """True when the project row has not changed since ``cursor``.

    A missing ``updated_at`` does not skip the project; the commit list decides.
    """
    raw = project.get("updated_at")
    if not isinstance(raw, str) or not raw:
        return False
    updated = convert_str_to_utc_datetime(raw)
    if cursor.tzinfo is None:
        cursor = cursor.replace(tzinfo=timezone.utc)
    return updated < cursor.astimezone(timezone.utc)


def oldest_commit_parent(commits: list[dict[str, Any]]) -> str | None:
    """First parent of the oldest commit in a newest-first list.

    ``None`` means that commit has no parent (the root of the branch).
    """
    if not commits:
        return None
    parents = commits[-1].get("parent_ids") or []
    if not parents or not isinstance(parents[0], str) or not parents[0]:
        return None
    return parents[0]


def compare_is_incomplete(compare: dict[str, Any] | None) -> bool:
    """True when the compare file list cannot be trusted.

    ``compare_timeout`` means GitLab hit a size or time limit and ``diffs`` may
    be missing files. ``too_large`` and ``collapsed`` only omit patch text.
    """
    if not compare or compare.get("compare_timeout"):
        return True
    return compare.get("diffs") is None


def _changed_paths(diffs: list[dict[str, Any]]) -> set[str]:
    """Added or edited paths from a compare. Deleted paths are left out."""
    changed: set[str] = set()
    for diff in diffs:
        if diff.get("deleted_file"):
            continue
        new_path = diff.get("new_path")
        if isinstance(new_path, str) and new_path:
            changed.add(new_path)
    return changed


def _selector_paths(changed: set[str], search_path: str) -> list[str]:
    return sorted(
        path for path in changed if path_matches_file_pattern(path, search_path)
    )


def _included_path_changed(changed: set[str], included_files: list[str]) -> bool:
    if not included_files:
        return False
    included = set(included_files)
    return any(path in included for path in changed)


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

    changed = _changed_paths(compare.get("diffs") or [])
    selector_paths = _selector_paths(changed, search_path)
    if not selector_paths:
        if _included_path_changed(changed, included_files):
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
    max_concurrent: int = 10,
) -> AsyncIterator[list[dict[str, Any]]]:
    """Yield ``{file, repo}`` batches for files added or edited since ``cursor``."""
    if not projects:
        return

    semaphore = asyncio.BoundedSemaphore(max_concurrent)

    async def _one(project: dict[str, Any]) -> AsyncIterator[list[dict[str, Any]]]:
        async for batch in _project_file_changes(
            client,
            project,
            cursor=cursor,
            search_path=search_path,
            skip_parsing=skip_parsing,
            included_files=included_files,
        ):
            yield batch

    tasks = [
        semaphore_async_iterator(semaphore, partial(_one, project))
        for project in projects
    ]
    async for batch in stream_async_iterators_tasks(*tasks):
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
    client: GitLabClient,
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
        projects = await load_named_projects(
            client, repositories, cursor, max_concurrent=max_concurrent
        )
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
    client: GitLabClient,
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
            max_concurrent=max_concurrent,
        ):
            yield batch

    if repositories:
        async for batch in _files(
            await load_named_projects(
                client, repositories, cursor, max_concurrent=max_concurrent
            )
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


async def load_named_projects(
    client: Any,
    repositories: list[str],
    cursor: datetime,
    *,
    max_concurrent: int = 10,
) -> list[dict[str, Any]]:
    """Fetch named repos and drop those whose ``updated_at`` is before ``cursor``."""
    semaphore = asyncio.BoundedSemaphore(max_concurrent)

    async def _load(repo: str) -> dict[str, Any] | None:
        async with semaphore:
            project = await client.get_project(repo)
            if not project or not project.get("default_branch"):
                return None
            if project_updated_before_cursor(project, cursor):
                logger.info(
                    f"Skipping project '{repo}' during file incremental sync: "
                    "updated_at is before the cursor"
                )
                return None
            return project

    loaded = await asyncio.gather(*(_load(repo) for repo in repositories))
    return [project for project in loaded if project is not None]
