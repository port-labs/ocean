from __future__ import annotations

from typing import Any, Protocol, TypeGuard

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


def _is_usable_sha(sha: Any) -> TypeGuard[str]:
    return isinstance(sha, str) and bool(sha) and sha != DELETED_COMMIT_SHA


async def resolve_push_path_changes(
    client: _CompareClient,
    project_path: str | int,
    payload: dict[str, Any],
) -> tuple[set[str], set[str]]:
    """
    Resolve changed/removed paths for a push hook.

    GitLab caps the commits list embedded in a push hook, so the repository
    compare API is the source of truth whenever `before`/`after` can be
    compared. The commits list is only used when compare is impossible
    (branch create/delete) or the compare call fails.
    """
    before = payload.get("before")
    after = payload.get("after")

    if _is_usable_sha(before) and _is_usable_sha(after):
        try:
            compare = await client.compare_repository(project_path, before, after)
            diffs = compare.get("diffs")
            if diffs is not None:
                return paths_from_compare_diffs(diffs)
            # Unreachable refs (force push, rebase) answer 404, which the REST
            # client turns into an empty response rather than an error.
            logger.warning(
                f"Repository compare {before}..{after} returned no diffs for "
                f"{project_path}; falling back to the push payload commits list"
            )
        except Exception as exc:
            logger.warning(
                f"Repository compare {before}..{after} failed for {project_path} "
                f"({exc}); falling back to the push payload commits list"
            )
    return collect_paths_from_commits(payload)
