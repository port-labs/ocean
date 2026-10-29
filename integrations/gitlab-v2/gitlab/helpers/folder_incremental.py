"""Incremental folder sync.

Lists commits on each repository's target branch since the cursor, then runs one
straight compare to determine which ancestor directories changed. Only matching
folders whose contents changed are emitted from the repository tree. Deletions
are left for full-resync reconciliation. A full folder tree walk for a project
is used only when the compare cannot be trusted, the window starts at the root
commit, or an included file changed on its own.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import PurePosixPath
from typing import Any, AsyncIterator, Iterable, Sequence

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from wcmatch import glob

from gitlab.clients.gitlab_client import GitLabClient, _is_wildcard_path
from gitlab.clients.utils import build_project_params
from gitlab.enrichments.included_files import (
    FolderIncludedFilesStrategy,
    IncludedFilesEnricher,
)
from gitlab.helpers.incremental import (
    build_file_project_params,
    changed_paths_from_diffs,
    compare_is_incomplete,
    included_path_changed,
    load_named_projects,
    oldest_commit_parent,
)
from integration import FolderPattern, GitlabFolderSelector, RepositoryBranchMapping


def ancestor_directories(paths: Iterable[str]) -> set[str]:
    """Return every parent directory path for the given file paths."""
    ancestors: set[str] = set()
    for path in paths:
        if not path:
            continue
        for parent in PurePosixPath(path).parents:
            parent_str = str(parent)
            if parent_str and parent_str != ".":
                ancestors.add(parent_str)
    return ancestors


def path_matches_folder_pattern(folder_path: str, pattern_path: str) -> bool:
    """True when ``folder_path`` is a folder matched by ``pattern_path``."""
    if not folder_path:
        return False
    if _is_wildcard_path(pattern_path):
        return glob.globmatch(
            folder_path,
            pattern_path,
            flags=glob.GLOBSTAR | glob.DOTGLOB,
        )
    prefix = pattern_path.strip("/")
    if not prefix:
        return "/" not in folder_path
    return folder_path == prefix or (
        folder_path.startswith(f"{prefix}/")
        and "/" not in folder_path[len(prefix) + 1 :]
    )


def _matching_changed_folders(changed_files: set[str], pattern_path: str) -> set[str]:
    return {
        folder
        for folder in ancestor_directories(changed_files)
        if path_matches_folder_pattern(folder, pattern_path)
    }


async def enrich_folders_with_included(
    client: GitLabClient,
    folders_batch: list[dict[str, Any]],
    folder_selectors: Sequence[FolderPattern],
    included_files: Sequence[str],
) -> list[dict[str, Any]]:
    """Attach ``__includedFiles`` to a folder batch when ``includedFiles`` is set."""
    if not folders_batch or not included_files:
        return folders_batch
    enricher = IncludedFilesEnricher(
        client=client,
        strategy=FolderIncludedFilesStrategy(
            folder_selectors=folder_selectors,
            global_included_files=included_files,
        ),
    )
    return await enricher.enrich_batch(folders_batch)


async def _iter_matching_tree_folders(
    client: GitLabClient,
    project: dict[str, Any],
    *,
    path: str,
    branch: str,
    allowed_paths: set[str] | None = None,
) -> AsyncIterator[list[dict[str, Any]]]:
    is_wildcard = _is_wildcard_path(path)
    async for items_batch in client.get_repository_tree(project, path, branch):
        folders_batch = [
            {"folder": item, "repo": project, "__branch": branch}
            for item in items_batch
            if item.get("type") == "tree"
            and (
                not is_wildcard
                or glob.globmatch(
                    item["path"], path, flags=glob.GLOBSTAR | glob.DOTGLOB
                )
            )
            and (allowed_paths is None or item["path"] in allowed_paths)
        ]
        if folders_batch:
            yield folders_batch


async def _project_folder_changes(
    client: GitLabClient,
    project: dict[str, Any],
    *,
    cursor: datetime,
    path: str,
    branch: str | None = None,
    folder_selectors: Sequence[FolderPattern] = (),
    included_files: Sequence[str] = (),
) -> AsyncIterator[list[dict[str, Any]]]:
    effective_branch = branch or project.get("default_branch")
    if not effective_branch:
        return
    project_path = project.get("path_with_namespace") or str(project.get("id"))
    commits: list[dict[str, Any]] = []
    async for page in client.get_repository_commits(
        project_path, effective_branch, cursor
    ):
        commits.extend(page)
    if not commits:
        logger.info(
            f"Skipping folders for project '{project_path}' on branch "
            f"'{effective_branch}': no commits since {cursor.isoformat()}"
        )
        return

    async def _emit(
        allowed_paths: set[str] | None,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        async for folders_batch in _iter_matching_tree_folders(
            client,
            project,
            path=path,
            branch=effective_branch,
            allowed_paths=allowed_paths,
        ):
            enriched = await enrich_folders_with_included(
                client, folders_batch, folder_selectors, included_files
            )
            if enriched:
                yield enriched

    parent = oldest_commit_parent(commits)
    if parent is None:
        logger.info(
            f"Falling back to repository tree for folders in project '{project_path}' "
            f"on branch '{effective_branch}'"
        )
        async for batch in _emit(None):
            yield batch
        return

    compare = await client.compare_repository(
        project_path, parent, effective_branch, straight=True
    )
    if compare_is_incomplete(compare):
        logger.info(
            f"Falling back to repository tree for folders in project '{project_path}' "
            f"on branch '{effective_branch}'"
        )
        async for batch in _emit(None):
            yield batch
        return

    changed = changed_paths_from_diffs(compare.get("diffs") or [])
    if included_path_changed(changed, included_files):
        logger.info(
            f"Falling back to repository tree for folders in project '{project_path}' "
            f"on branch '{effective_branch}': included file changed"
        )
        async for batch in _emit(None):
            yield batch
        return

    matched_folders = _matching_changed_folders(changed, path)
    if not matched_folders:
        return

    async for batch in _emit(matched_folders):
        yield batch


async def iter_incremental_folders(
    client: GitLabClient,
    projects: list[dict[str, Any]],
    *,
    cursor: datetime,
    path: str,
    branch: str | None = None,
    folder_selectors: Sequence[FolderPattern] = (),
    included_files: Sequence[str] = (),
) -> AsyncIterator[list[dict[str, Any]]]:
    """Yield ``{folder, repo, __branch}`` batches for folders changed since ``cursor``."""
    for project in projects:
        async for batch in _project_folder_changes(
            client,
            project,
            cursor=cursor,
            path=path,
            branch=branch,
            folder_selectors=folder_selectors,
            included_files=included_files,
        ):
            yield batch


async def _resync_named_repo_folders(
    client: GitLabClient,
    repos: Sequence[RepositoryBranchMapping],
    *,
    cursor: datetime,
    path: str,
    folder_selectors: Sequence[FolderPattern],
    included_files: Sequence[str],
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    unique_names = list(dict.fromkeys(repo.name for repo in repos))
    loaded_projects = await load_named_projects(client, unique_names, cursor)
    project_by_name = {
        project["path_with_namespace"]: project for project in loaded_projects
    }

    for repo_mapping in repos:
        project = project_by_name.get(repo_mapping.name)
        if not project:
            continue
        async for batch in _project_folder_changes(
            client,
            project,
            cursor=cursor,
            path=path,
            branch=repo_mapping.branch,
            folder_selectors=folder_selectors,
            included_files=included_files,
        ):
            yield batch


async def resync_folders_incremental(
    client: GitLabClient,
    selector: GitlabFolderSelector,
    cursor: datetime,
    *,
    max_concurrent: int = 10,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Upsert folders with changes since ``cursor``. Deletions stay on full resync."""
    included_files = list(selector.included_files or [])
    projects_params: dict[str, Any] | None = None

    for folder_selector in selector.folders:
        path = folder_selector.path
        repos = folder_selector.repos

        if repos:
            async for batch in _resync_named_repo_folders(
                client,
                repos,
                cursor=cursor,
                path=path,
                folder_selectors=selector.folders,
                included_files=included_files,
            ):
                yield batch
            continue

        if projects_params is None:
            projects_params = build_file_project_params(
                build_project_params(
                    include_only_active_projects=selector.include_only_active_projects
                ),
                cursor,
            )

        logger.info(
            f"No repositories specified for path {path}; "
            "incrementally syncing folders from updated projects"
        )
        async for projects_batch in client.get_projects(
            params=projects_params,
            max_concurrent=max_concurrent,
            include_languages=False,
        ):
            searchable, skipped = client._partition_projects_with_tree_ref(
                projects_batch
            )
            client._log_skipped_projects_without_default_branch(skipped)
            async for batch in iter_incremental_folders(
                client,
                searchable,
                cursor=cursor,
                path=path,
                folder_selectors=selector.folders,
                included_files=included_files,
            ):
                yield batch
