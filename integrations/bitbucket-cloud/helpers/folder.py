import asyncio
from collections import defaultdict
from typing import Any, AsyncGenerator, Dict, List, Set, Tuple

from loguru import logger
import fnmatch
from client import BitbucketClient
from integration import FolderPattern


async def extract_repo_names_from_patterns(
    folder_patterns: List[FolderPattern],
) -> Set[str]:
    """Extract repository names from folder patterns."""
    if not folder_patterns:
        logger.info("No folder patterns found in config, skipping folder sync")
        return set()

    repo_names = {repo.name for pattern in folder_patterns for repo in pattern.repos}
    if not repo_names:
        logger.info("No repository names found in patterns, skipping folder sync")
        return set()

    return repo_names


async def create_pattern_mapping(
    folder_patterns: List[FolderPattern],
) -> Dict[str, Dict[str, List[str]]]:
    """
    Create a mapping of repository names to branch names to folder patterns.
    """
    pattern_by_repo_branch: Dict[str, Dict[str, List[str]]] = defaultdict(
        lambda: defaultdict(list)
    )

    for pattern in folder_patterns:
        p = pattern.path
        for repo in pattern.repos:
            pattern_by_repo_branch[repo.name][repo.branch].append(p)

    # Convert defaultdicts to regular dicts
    return {repo: dict(branches) for repo, branches in pattern_by_repo_branch.items()}


async def find_matching_folders(
    contents: List[Dict[str, Any]], patterns: List[str], repo: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Find folders that match the given patterns."""
    matching_folders = []
    for pattern_str in patterns:
        is_wildcard_pattern = any(c in pattern_str for c in "*?[]")
        matching = [
            {"folder": folder, "repo": repo, "pattern": pattern_str}
            for folder in contents
            if folder["type"] == "commit_directory"
            and (
                (
                    is_wildcard_pattern
                    and folder["path"].count("/") == pattern_str.count("/")
                )
                or (not is_wildcard_pattern and folder["path"] == pattern_str)
            )
            and fnmatch.fnmatch(folder["path"], pattern_str)
        ]
        matching_folders.extend(matching)
    return matching_folders


async def find_common_base_path(paths: List[str]) -> Tuple[str, int]:
    """
    Find the common base path and required depth for a list of glob patterns.
    """
    if not paths:
        return "", 1

    async def get_parts_before_wildcard(path: str) -> List[str]:
        parts = path.split("/")
        result = []
        for part in parts:
            if any(c in part for c in "*?[]"):
                break
            result.append(part)
        return result

    all_path_parts = await asyncio.gather(
        *[get_parts_before_wildcard(path) for path in paths]
    )

    common_parts = []
    if not all_path_parts or not all_path_parts[0]:
        return "", 1
    for i in range(min(len(path_parts) for path_parts in all_path_parts)):
        current_part = all_path_parts[0][i]
        if all(path_parts[i] == current_part for path_parts in all_path_parts):
            common_parts.append(current_part)
        else:
            break

    base_path = "/".join(common_parts)

    # Calculate relative paths and required depth
    relative_paths = [
        p[len(base_path) :].lstrip("/") if base_path and p.startswith(base_path) else p
        for p in paths
    ]

    max_pattern_depth = max(
        (path.count("/") + 1 for path in relative_paths),
        default=1,
    )
    return base_path, max_pattern_depth


async def process_folder_patterns(
    folder_patterns: list[FolderPattern], client: BitbucketClient
) -> AsyncGenerator[list[dict[str, Any]], None]:
    repo_names = await extract_repo_names_from_patterns(folder_patterns)
    if not repo_names:
        return

    pattern_by_repo = await create_pattern_mapping(folder_patterns)
    async for repos_batch in client.get_repositories(
        params={"q": f"name IN ({','.join(f'"{name}"' for name in repo_names)})"}
    ):
        for repo in repos_batch:
            async for matching_folders in process_repo_folders(
                repo, pattern_by_repo, folder_patterns, client
            ):
                yield matching_folders


async def process_repo_folders(
    repo: dict[str, Any],
    pattern_by_repo: dict[str, dict[str, list[str]]],
    folder_patterns: list[FolderPattern],
    client: BitbucketClient,
) -> AsyncGenerator[list[dict[str, Any]], None]:
    repo_name = repo["name"]
    if repo_name not in pattern_by_repo:
        return

    repo_branches = pattern_by_repo[repo_name]
    for branch, paths in repo_branches.items():
        repo_slug = repo.get("slug", repo_name.lower())
        effective_branch = branch or repo["mainbranch"]["name"]
        base_path, max_pattern_depth = await find_common_base_path(paths)
        logger.debug(
            f"Fetching {repo_name}/{effective_branch} from '{base_path}' with depth {max_pattern_depth}"
        )

        async for contents in client.get_directory_contents(
            repo_slug, effective_branch, base_path, max_depth=max_pattern_depth
        ):
            if matching_folders := await find_matching_folders(contents, paths, repo):
                yield matching_folders
