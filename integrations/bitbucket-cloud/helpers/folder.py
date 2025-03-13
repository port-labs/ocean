from collections import defaultdict
from typing import Any, AsyncGenerator, Dict, List, Set

from loguru import logger
import fnmatch
from client import BitbucketClient
from integration import FolderPattern


async def extract_repo_names_from_patterns(
    folder_patterns: List[FolderPattern],
) -> Set[str]:
    """Extract and validate repository names from folder patterns."""
    if not folder_patterns:
        logger.info("No folder patterns found in config, skipping folder sync")
        return set()

    repo_names = {
        repo_name for pattern in folder_patterns for repo_name in pattern.repos
    }
    if not repo_names:
        logger.info("No repository names found in patterns, skipping folder sync")
        return set()

    return repo_names


async def create_pattern_mapping(
    folder_patterns: List[FolderPattern],
) -> Dict[str, List[str]]:
    """Create a mapping of repository names to their folder patterns."""
    pattern_by_repo = defaultdict(list)
    for pattern in folder_patterns:
        p = pattern.path
        for repo in pattern.repos:
            pattern_by_repo[repo].append(p)
    return dict(pattern_by_repo)


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
    pattern_by_repo: dict[str, list[str]],
    folder_patterns: list[FolderPattern],
    client: BitbucketClient,
) -> AsyncGenerator[list[dict[str, Any]], None]:
    repo_name = repo["name"]
    patterns = pattern_by_repo[repo_name]
    repo_slug = repo.get("slug", repo_name.lower())
    default_branch = repo.get("mainbranch", {}).get("name", "main")
    max_pattern_depth = max(
        (folder_pattern.path.count("/") + 1 for folder_pattern in folder_patterns),
        default=1,
    )
    async for contents in client.get_directory_contents(
        repo_slug, default_branch, "", max_depth=max_pattern_depth
    ):
        if matching_folders := await find_matching_folders(contents, patterns, repo):
            yield matching_folders
