# helpers/file.py
from __future__ import annotations

import fnmatch
import mimetypes
from pathlib import Path
from typing import Dict, List, Any, AsyncGenerator, Optional, TYPE_CHECKING

from loguru import logger
from integration import BitbucketServerFilePattern

if TYPE_CHECKING:
    from client import BitbucketClient


def _normalize_posix(path: str) -> str:
    return Path(path).as_posix()


def _matches_any(patterns: List[str], value: str) -> bool:
    return any(fnmatch.fnmatch(value, p) for p in patterns)


def matches_file_pattern(file_path: str, pattern_path: str, filenames: List[str]) -> bool:
    """
    Check if a file path matches the provided directory/path constraint and filename patterns.
    - If pattern_path is empty or '*', match by filename only.
    - Otherwise, allow nested directories via **.
    """
    file_path = _normalize_posix(file_path)
    name = Path(file_path).name

    if not pattern_path or pattern_path == "*":
        return _matches_any(filenames, name)

    dir_glob = f"{pattern_path.rstrip('/')}/**"
    return fnmatch.fnmatch(file_path, dir_glob) and _matches_any(filenames, name)


async def get_repositories_for_pattern(
    client: "BitbucketClient", file_pattern: BitbucketServerFilePattern
) -> List[Dict[str, Any]]:
    """
    Get repositories matching the given file pattern.
    Supports wildcard project_key="*".
    """
    repos_to_process: List[Dict[str, Any]] = []

    if not file_pattern.project_key:
        logger.warning("No project key provided; will not fetch repositories.")
        return repos_to_process

    if file_pattern.project_key == "*":
        async for project_batch in client.get_projects():
            for project in project_batch:
                project_key = project["key"]
                logger.info(f"Processing project: {project_key}")
                await collect_repos_for_project(
                    client, project_key, file_pattern.repos, repos_to_process
                )
    else:
        await collect_repos_for_project(
            client, file_pattern.project_key, file_pattern.repos, repos_to_process
        )

    return repos_to_process


async def collect_repos_for_project(
    client: "BitbucketClient",
    project_key: str,
    repo_filter: List[str],
    repos_list: List[Dict[str, Any]],
) -> None:
    """Collect repositories for a specific project that match the optional filter."""
    async for repo_batch in client.get_repositories_for_project(project_key):
        for repo in repo_batch:
            if not repo_filter or repo["slug"] in repo_filter:
                repos_list.append(repo)


def _create_file_metadata_from_browse(browse_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a normalized metadata object from Bitbucket 'browse' JSON (with noContent=true).
    Common fields: path, size, type (FILE/DIRECTORY/SYMLINK/SUBMODULE), mimeType.
    """
    path_obj = browse_json.get("path")
    if isinstance(path_obj, dict):
        path_str = path_obj.get("toString") or ""
    else:
        path_str = str(path_obj or "")

    meta = {
        "path": path_str,
        "size": browse_json.get("size"),
        "type": browse_json.get("type"),        # FILE / DIRECTORY / SYMLINK / SUBMODULE
        "mimeType": browse_json.get("mimeType"),
        "lastModified": None,                   # could be populated via commits call
        "sha": None,                            # could be populated via commits call
    }
    return meta


def _finalize_metadata_fallbacks(meta: Dict[str, Any], content_type_header: Optional[str]) -> Dict[str, Any]:
    """
    Prefer Bitbucket-provided mimeType, otherwise use the HTTP header; if still missing, fall back to mimetypes.
    Default 'type' to FILE if not present.
    """
    if not meta.get("mimeType"):
        if content_type_header:
            meta["mimeType"] = content_type_header.split(";")[0].strip()
        else:
            guess, _ = mimetypes.guess_type(meta.get("path", ""))
            meta["mimeType"] = guess or "application/octet-stream"

    if not meta.get("type"):
        meta["type"] = "FILE"

    return meta


async def process_matching_file(
    client: "BitbucketClient",
    project_key: str,
    repo_slug: str,
    file_path: str,
    repo: Dict[str, Any],
    *,
    at: Optional[str] = None,
    size_limit_bytes: int = 2_000_000,
    skip_parsing: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Process a matching file and return its content and metadata.

    Strategy:
      1) Fetch metadata only (noContent=true) via browse.
      2) If not skip_parsing and under size cap, fetch raw content (binary safe).
      3) Merge/normalize metadata and return result.
    """
    try:
        # 1) Lightweight metadata call
        info = await client.get_file_info(project_key, repo_slug, file_path, at=at)
        if not info:
            logger.warning(f"No metadata returned for {project_key}/{repo_slug}:{file_path}")
            return None

        file_obj = _create_file_metadata_from_browse(info)

        # 2) Conditional content fetch
        content: Optional[bytes] = None
        content_type_header: Optional[str] = None
        if not skip_parsing:
            file_size = int(file_obj.get("size") or 0)
            if file_size == 0:
                # Zero-byte files are safe to fetch, but raw still returns cleanly
                content, content_type_header = await client.get_file_raw(project_key, repo_slug, file_path, at=at)
            elif file_size <= size_limit_bytes:
                content, content_type_header = await client.get_file_raw(project_key, repo_slug, file_path, at=at)
            else:
                logger.info(
                    f"Skipping content download for large file ({file_size} bytes): {file_path}"
                )

        file_obj = _finalize_metadata_fallbacks(file_obj, content_type_header)

        result = {
            "content": content,  # bytes or None
            "repo": repo,
            "project": {"key": project_key},
            "file": file_obj,
            "path": file_path,
            "filename": Path(file_path).name,
            "truncated": (content is None) and (file_obj.get("size") or 0) > size_limit_bytes and not skip_parsing,
        }
        return result

    except Exception as e:
        logger.error(f"Failed to retrieve file content for {file_path} from {repo_slug}: {e}")
        return None


async def list_files_recursively(
    client: "BitbucketClient",
    project_key: str,
    repo_slug: str,
    path: str,
    result_list: List[Dict[str, Any]],
) -> None:
    """Recursively list all items under the given path using /files API."""
    try:
        # Treat '*' as repo root
        path_to_use = "" if path in ("", "*") else path

        async for contents in client.get_directory_contents(project_key, repo_slug, path_to_use):
            for item in contents:
                await process_directory_item(client, project_key, repo_slug, item, result_list)
    except Exception as e:
        logger.error(f"Error listing directory '{path}' in {repo_slug}: {e}")


async def process_directory_item(
    client: "BitbucketClient",
    project_key: str,
    repo_slug: str,
    item: Any,
    result_list: List[Dict[str, Any]],
) -> None:
    """
    Handle heterogeneous item formats from /files:
    - Dict with 'path' and 'type' (FILE/DIRECTORY/SYMLINK/SUBMODULE)
    - String path (infer FILE/DIRECTORY by trailing slash)
    """
    if isinstance(item, dict) and "path" in item:
        await process_typed_item(client, project_key, repo_slug, item, result_list)
        return

    if isinstance(item, str):
        await process_string_item(client, project_key, repo_slug, item, result_list)
        return

    logger.debug(f"Unknown item shape from directory listing: {item!r}")


async def process_typed_item(
    client: "BitbucketClient",
    project_key: str,
    repo_slug: str,
    item: Dict[str, Any],
    result_list: List[Dict[str, Any]],
) -> None:
    """Process an item with explicit type information."""
    item_path = item["path"]
    item_type = item.get("type", "FILE")  # FILE | DIRECTORY | SYMLINK | SUBMODULE

    # Always record the item for consumers
    result_list.append(item)

    if item_type == "DIRECTORY":
        await list_files_recursively(client, project_key, repo_slug, item_path, result_list)


async def process_string_item(
    client: "BitbucketClient",
    project_key: str,
    repo_slug: str,
    item_path: str,
    result_list: List[Dict[str, Any]],
) -> None:
    """Process a string path (create synthetic item with type)."""
    is_dir = item_path.endswith("/")
    file_obj = {
        "path": item_path.rstrip("/") if is_dir else item_path,
        "type": "DIRECTORY" if is_dir else "FILE",
    }
    result_list.append(file_obj)
    if is_dir:
        await list_files_recursively(client, project_key, repo_slug, file_obj["path"], result_list)


async def process_repository_files(
    client: "BitbucketClient",
    repo: Dict[str, Any],
    file_pattern: BitbucketServerFilePattern,
) -> AsyncGenerator[List[Dict[str, Any]], None]:
    """
    Process files in a repository that match the pattern.
    Honors `skip_parsing` to avoid fetching file bodies.
    """
    repo_slug = repo["slug"]
    project_key = repo["project"]["key"]

    try:
        # Process items as a stream instead of collecting them all in memory first
        async for item in list_files_recursively_stream(client, project_key, repo_slug, ""):
            # We only consider FILE items as candidates to match the filename patterns
            if item.get("type") != "FILE":
                continue

            file_path = item.get("path", "")
            if matches_file_pattern(file_path, file_pattern.path, file_pattern.filenames):
                result = await process_matching_file(
                    client,
                    project_key,
                    repo_slug,
                    file_path,
                    repo,
                    at=None,  # Optional: thread a ref through BitbucketServerFilePattern if you need it
                    size_limit_bytes=2_000_000,
                    skip_parsing=file_pattern.skip_parsing,
                )
                if result:
                    yield [result]

    except Exception as e:
        logger.error(f"Failed to list files in repository {repo_slug}: {e}")


async def list_files_recursively_stream(
    client: "BitbucketClient",
    project_key: str,
    repo_slug: str,
    path: str,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Recursively list all items under the given path using /files API as a stream."""
    try:
        path_to_use = "" if path in ("", "*") else path

        async for contents in client.get_directory_contents(project_key, repo_slug, path_to_use):
            for item in contents:
                # Yield the item first
                if isinstance(item, dict) and "path" in item:
                    yield item
                    if item.get("type") == "DIRECTORY":
                        async for sub_item in list_files_recursively_stream(client, project_key, repo_slug, item["path"]):
                            yield sub_item
                elif isinstance(item, str):
                    is_dir = item.endswith("/")
                    file_obj = {
                        "path": item.rstrip("/") if is_dir else item,
                        "type": "DIRECTORY" if is_dir else "FILE",
                    }
                    yield file_obj
                    if is_dir:
                        async for sub_item in list_files_recursively_stream(client, project_key, repo_slug, file_obj["path"]):
                            yield sub_item
                else:
                    logger.debug(f"Unknown item shape from directory listing: {item!r}")

    except Exception as e:
        logger.error(f"Error listing directory '{path}' in {repo_slug}: {e}")


async def process_file_patterns(
    file_pattern: BitbucketServerFilePattern,
    client: "BitbucketClient",
) -> AsyncGenerator[List[Dict[str, Any]], None]:
    """
    Top-level entry to process a single BitbucketServerFilePattern across matching repos.
    """
    logger.info(
        f"Searching for files in project {file_pattern.project_key} with pattern: {file_pattern.path}"
    )

    if not file_pattern.project_key:
        logger.warning("No project key provided, skipping file search")
        return
    if not file_pattern.filenames:
        logger.info("No filenames provided, skipping file search")
        return

    repos_to_process = await get_repositories_for_pattern(client, file_pattern)

    for repo in repos_to_process:
        async for result in process_repository_files(client, repo, file_pattern):
            yield result
