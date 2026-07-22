from __future__ import annotations

from typing import Any, Protocol

from loguru import logger

from gitlab.webhook.webhook_processors.push_constants import DELETED_COMMIT_SHA


class _CompareClient(Protocol):
    async def compare_repository(
        self,
        project_path: str | int,
        from_sha: str,
        to_sha: str,
    ) -> dict[str, Any]: ...


def collect_paths_from_commits(payload: dict[str, Any]) -> tuple[set[str], set[str]]:
    """Collect added/modified and removed paths from the push payload commits list."""
    changed_files: set[str] = set()
    removed_files: set[str] = set()
    for commit in payload.get("commits") or []:
        changed_files.update(commit.get("added") or [])
        changed_files.update(commit.get("modified") or [])
        removed_files.update(commit.get("removed") or [])
    return changed_files, removed_files


def paths_from_compare_diffs(
    diffs: list[dict[str, Any]],
) -> tuple[set[str], set[str]]:
    """Map GitLab compare `diffs` entries to changed and removed path sets."""
    changed_files: set[str] = set()
    removed_files: set[str] = set()
    for diff in diffs:
        if diff.get("deleted_file"):
            old_path = diff.get("old_path")
            if isinstance(old_path, str) and old_path:
                removed_files.add(old_path)
            continue
        new_path = diff.get("new_path")
        if isinstance(new_path, str) and new_path:
            changed_files.add(new_path)
        if diff.get("renamed_file"):
            old_path = diff.get("old_path")
            if isinstance(old_path, str) and old_path and old_path != new_path:
                removed_files.add(old_path)
    return changed_files, removed_files


def _is_usable_sha(sha: str | None) -> bool:
    return bool(sha) and sha != DELETED_COMMIT_SHA


async def resolve_push_path_changes(
    client: _CompareClient,
    project_path: str | int,
    payload: dict[str, Any],
) -> tuple[set[str], set[str]]:
    """
    Resolve changed/removed paths for a push hook.

    When GitLab truncates the commits list (`total_commits_count` > len(commits)),
    fall back to the repository compare API using `before`/`after`.
    """
    commits = payload.get("commits") or []
    total_commits_count = payload.get("total_commits_count", len(commits))
    changed_files, removed_files = collect_paths_from_commits(payload)

    if total_commits_count <= len(commits):
        return changed_files, removed_files

    before = payload.get("before")
    after = payload.get("after")
    if not isinstance(before, str) or not isinstance(after, str):
        logger.warning(
            "Push payload commits list is truncated but before/after SHAs are "
            f"unusable for compare on project {project_path}; using commits only"
        )
        return changed_files, removed_files
    if not _is_usable_sha(before) or not _is_usable_sha(after):
        logger.warning(
            "Push payload commits list is truncated but before/after SHAs are "
            f"unusable for compare on project {project_path}; using commits only"
        )
        return changed_files, removed_files

    logger.info(
        f"Push commits truncated ({len(commits)}/{total_commits_count}) for "
        f"{project_path}; resolving paths via repository compare"
    )
    compare = await client.compare_repository(project_path, before, after)
    return paths_from_compare_diffs(compare.get("diffs") or [])
