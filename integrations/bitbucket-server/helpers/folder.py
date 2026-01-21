from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple, TYPE_CHECKING

from loguru import logger
from integration import BitbucketServerFolderPattern

if TYPE_CHECKING:
    from client import BitbucketClient


def _normalize_posix(path: str) -> str:
    return Path(path).as_posix()


def _has_glob_chars(pattern: str) -> bool:
    # detect any globbing: *, ?, [], or **
    return any(ch in pattern for ch in ["*", "?", "["])


def _dir_like(path: str) -> str:
    # normalize path for directory-style comparisons (no trailing slash)
    return _normalize_posix(path).rstrip("/")


def _matches_dir_pattern(dir_path: str, pattern_path: str) -> bool:
    """
    Match directory 'dir_path' against user-specified 'pattern_path'.
    - If pattern empty or '*', match anything.
    - Allow nested matching via **.
    - fnmatch is applied on full path (posix).
    """
    dir_path = _dir_like(dir_path)
    pattern_path = _dir_like(pattern_path)

    if not pattern_path or pattern_path == "*":
        return True

    # If user did not include any glob chars, treat as exact directory match
    if not _has_glob_chars(pattern_path):
        return dir_path == pattern_path

    # Ensure ** works naturally for nested directories
    # (if user supplied single '*', it stays single; '**' matches across slashes)
    # We don't force add '/**' here because user might have anchored end.
    return fnmatch.fnmatch(dir_path, pattern_path)


async def get_repositories_for_pattern(
    pattern: BitbucketServerFolderPattern, client: "BitbucketClient"
) -> List[Tuple[Dict[str, Any], str]]:
    """Get repositories (and their project_key) matching the given folder pattern."""
    repos_to_process: List[Tuple[Dict[str, Any], str]] = []
    project_key = pattern.project_key

    if not project_key:
        logger.warning("Missing project key in folder pattern; skipping.")
        return repos_to_process

    if project_key == "*":
        await collect_repos_for_all_projects(client, pattern, repos_to_process)
    else:
        await collect_repos_for_project(
            client, project_key, pattern.repos, repos_to_process
        )

    return repos_to_process


async def collect_repos_for_all_projects(
    client: "BitbucketClient",
    pattern: BitbucketServerFolderPattern,
    repos_list: List[Tuple[Dict[str, Any], str]],
) -> None:
    async for project_batch in client.get_projects():
        for project in project_batch:
            actual_project_key = project["key"]
            logger.info(f"[folders] Scanning project: {actual_project_key}")
            await collect_repos_for_project(
                client, actual_project_key, pattern.repos, repos_list
            )


async def collect_repos_for_project(
    client: "BitbucketClient",
    project_key: str,
    repo_filter: List[str],
    repos_list: List[Tuple[Dict[str, Any], str]],
) -> None:
    async for repo_batch in client.get_repositories_for_project(project_key):
        for repo in repo_batch:
            if not repo_filter or "*" in repo_filter or repo["slug"] in repo_filter:
                repos_list.append((repo, project_key))


async def _list_dirs_recursively(
    client: "BitbucketClient",
    project_key: str,
    repo_slug: str,
    path: str,
    result_list: List[Dict[str, Any]],
) -> None:
    """
    Recursively list all DIRECTORY-like items under 'path' using the /files API.
    Records any item (FILE/DIRECTORY/SYMLINK/SUBMODULE), but only recurses into DIRECTORY.
    """
    try:
        base = "" if path in ("", "*") else path
        async for contents in client.get_directory_contents(
            project_key, repo_slug, base
        ):
            for item in contents:
                await _process_directory_item(
                    client, project_key, repo_slug, item, result_list
                )
    except Exception as e:
        logger.error(
            f"[folders] Error listing '{path}' in {project_key}/{repo_slug}: {e}"
        )


async def _process_directory_item(
    client: "BitbucketClient",
    project_key: str,
    repo_slug: str,
    item: Any,
    result_list: List[Dict[str, Any]],
) -> None:
    # Dict form (Bitbucket sometimes returns dicts with 'path' and 'type')
    if isinstance(item, dict) and "path" in item:
        await _process_typed_item(client, project_key, repo_slug, item, result_list)
        return

    # String form (a path that may end with '/')
    if isinstance(item, str):
        await _process_string_item(client, project_key, repo_slug, item, result_list)
        return

    logger.debug(f"[folders] Unknown directory item shape: {item!r}")


async def _process_typed_item(
    client: "BitbucketClient",
    project_key: str,
    repo_slug: str,
    item: Dict[str, Any],
    result_list: List[Dict[str, Any]],
) -> None:
    # item['type'] may be FILE | DIRECTORY | SYMLINK | SUBMODULE
    item_type = item.get("type", "FILE")
    result_list.append(item)  # record everything; consumers can filter

    if item_type == "DIRECTORY":
        await _list_dirs_recursively(
            client, project_key, repo_slug, item["path"], result_list
        )


async def _process_string_item(
    client: "BitbucketClient",
    project_key: str,
    repo_slug: str,
    item_path: str,
    result_list: List[Dict[str, Any]],
) -> None:
    is_dir = item_path.endswith("/")
    obj = {
        "path": item_path.rstrip("/") if is_dir else item_path,
        "type": "DIRECTORY" if is_dir else "FILE",
    }
    result_list.append(obj)
    if is_dir:
        await _list_dirs_recursively(
            client, project_key, repo_slug, obj["path"], result_list
        )


def _folder_hit(item: Dict[str, Any], pattern_path: str) -> bool:
    """
    True if item is a DIRECTORY and its path matches the pattern.
    """
    if item.get("type") != "DIRECTORY":
        return False
    return _matches_dir_pattern(item.get("path", ""), pattern_path)


async def _fast_check_exact_folder(
    client: "BitbucketClient",
    project_key: str,
    repo_slug: str,
    path: str,
) -> Optional[Dict[str, Any]]:
    """
    For non-glob patterns (exact folder path), query browse?noContent=true once.
    If Bitbucket says this is a DIRECTORY, return a synthetic item.
    """
    try:
        info = await client.get_file_info(project_key, repo_slug, path)
        if not info:
            return None
        # Bitbucket browse returns "type": "DIRECTORY" for directories
        if info.get("type") == "DIRECTORY":
            # Build a minimal directory object compatible with the traversal output
            # 'path' in browse JSON can be an object; normalize to string
            path_obj = info.get("path")
            if isinstance(path_obj, dict):
                path_str = path_obj.get("toString") or ""
            else:
                path_str = str(path_obj or "")
            return {"path": path_str, "type": "DIRECTORY"}
    except Exception as e:
        logger.debug(
            f"[folders] Fast check failed for {project_key}/{repo_slug}:{path} -> {e}"
        )
    return None


async def process_repository_folders(
    client: "BitbucketClient",
    repo_info: Tuple[Dict[str, Any], str],
    pattern: BitbucketServerFolderPattern,
) -> List[Dict[str, Any]]:
    """
    Process folders in a repository that match the given pattern.

    Strategy:
      - If pattern.path is empty or '*' or contains globbing, do a recursive walk and fnmatch.
      - If pattern.path is an exact path (no glob chars), do a single 'browse?noContent=true' fast check.
    """
    repo, project_key = repo_info
    repo_slug = repo["slug"]
    pattern_path = _dir_like(pattern.path)

    try:
        # Fast path: exact folder check (no glob chars and not empty/'*')
        if pattern_path and pattern_path != "*" and not _has_glob_chars(pattern_path):
            hit = await _fast_check_exact_folder(
                client, project_key, repo_slug, pattern_path
            )
            if hit:
                return [{"folder": hit, "repo": repo, "project": {"key": project_key}}]
            return []

        # Glob / recursive path:
        items: List[Dict[str, Any]] = []
        await _list_dirs_recursively(client, project_key, repo_slug, "", items)

        matches: List[Dict[str, Any]] = []
        for item in items:
            if _folder_hit(item, pattern_path):
                matches.append(
                    {"folder": item, "repo": repo, "project": {"key": project_key}}
                )

        return matches

    except Exception as e:
        logger.error(f"[folders] Error in repo {project_key}/{repo_slug}: {e}")
        return []


async def process_folder_patterns(
    folder_patterns: list[BitbucketServerFolderPattern], client: "BitbucketClient"
) -> AsyncGenerator[list[dict[str, Any]], None]:
    """
    Process a list of folder patterns. Yields lists of matches per repository.
    """
    for pattern in folder_patterns:
        if not pattern.project_key:
            logger.warning("Missing project key in folder pattern, skipping")
            continue

        repos_to_process = await get_repositories_for_pattern(pattern, client)

        for repo_info in repos_to_process:
            matches = await process_repository_folders(client, repo_info, pattern)
            if matches:
                yield matches
