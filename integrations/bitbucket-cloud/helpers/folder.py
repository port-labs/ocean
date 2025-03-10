from typing import Any, Dict, List, Set

from loguru import logger
import fnmatch

from integration import FolderPattern


def extract_repo_names_from_patterns(
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


def create_pattern_mapping(
    folder_patterns: List[FolderPattern],
) -> Dict[str, List[str]]:
    """Create a mapping of repository names to their folder patterns."""
    pattern_by_repo: Dict[str, List[str]] = {}
    for pattern in folder_patterns:
        for repo_name in pattern.repos:
            if repo_name not in pattern_by_repo:
                pattern_by_repo[repo_name] = []
            pattern_by_repo[repo_name].append(pattern.path)
    return pattern_by_repo


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
