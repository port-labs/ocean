from collections import defaultdict
from typing import Any, AsyncGenerator, Dict, List, Set, Tuple
import fnmatch
from loguru import logger
from integration import BitbucketServerFolderPattern
from client import BitbucketClient

async def get_repositories_for_pattern(
    pattern: BitbucketServerFolderPattern,
    client: BitbucketClient
) -> List[Tuple[Dict[str, Any], str]]:
    """Get repositories matching the given folder pattern."""
    repos_to_process = []
    project_key = pattern.project_key

    # Handle wildcard project key differently
    if project_key == "*":
        await collect_repos_for_all_projects(client, pattern, repos_to_process)
    else:
        # Use the specific project key
        await collect_repos_for_project(client, project_key, pattern.repos, repos_to_process)

    return repos_to_process


async def collect_repos_for_all_projects(
    client: BitbucketClient,
    pattern: BitbucketServerFolderPattern,
    repos_list: List[Tuple[Dict[str, Any], str]]
) -> None:
    """Collect repositories for all projects that match the filter."""
    # Get all projects first
    async for project_batch in client.get_projects():
        for project in project_batch:
            actual_project_key = project["key"]
            logger.info(f"Processing project: {actual_project_key}")
            # For each project, get its repositories
            await collect_repos_for_project(client, actual_project_key, pattern.repos, repos_list)


async def collect_repos_for_project(
    client: BitbucketClient,
    project_key: str,
    repo_filter: List[str],
    repos_list: List[Tuple[Dict[str, Any], str]]
) -> None:
    """Collect repositories for a specific project that match the filter."""
    async for repo_batch in client.get_repositories_for_project(project_key):
        for repo in repo_batch:
            if not repo_filter or "*" in repo_filter or repo["slug"] in repo_filter:
                repos_list.append((repo, project_key))


async def process_repository_folders(
    client: BitbucketClient,
    repo_info: Tuple[Dict[str, Any], str],
    pattern: BitbucketServerFolderPattern
) -> List[Dict[str, Any]]:
    """Process folders in a repository that match the given pattern."""
    repo, actual_project_key = repo_info  # Unpack the tuple
    repo_slug = repo["slug"]
    matching_folders = []

    # Handle wildcard path
    path_to_use = "" if pattern.path == "*" else pattern.path

    try:
        async for contents in client.get_directory_contents(
            actual_project_key, repo_slug, path_to_use
        ):
            # Process each item in the directory contents
            for item in contents:
                process_directory_item(item, pattern.path, repo, actual_project_key, matching_folders)

        return matching_folders

    except Exception as e:
        logger.error(f"Error getting directory contents for {repo_slug} in project {actual_project_key}: {e}")
        return []


def process_directory_item(
    item: Any,
    pattern_path: str,
    repo: Dict[str, Any],
    project_key: str,
    matching_folders: List[Dict[str, Any]]
) -> None:
    """Process a single item from directory contents."""
    # Check if item is a dictionary with the expected structure
    if isinstance(item, dict) and "type" in item and "path" in item:
        process_dict_item(item, pattern_path, repo, project_key, matching_folders)
    # If it's a string, we need to construct a folder object
    elif isinstance(item, str):
        process_string_item(item, pattern_path, repo, project_key, matching_folders)


def process_dict_item(
    item: Dict[str, Any],
    pattern_path: str,
    repo: Dict[str, Any],
    project_key: str,
    matching_folders: List[Dict[str, Any]]
) -> None:
    """Process an item that is represented as a dictionary."""
    if item["type"] == "DIRECTORY" and fnmatch.fnmatch(item["path"], pattern_path):
        matching_folders.append({
            "folder": item,
            "repo": repo,
            "project": {"key": project_key}
        })


def process_string_item(
    item_path: str,
    pattern_path: str,
    repo: Dict[str, Any],
    project_key: str,
    matching_folders: List[Dict[str, Any]]
) -> None:
    """Process an item that is represented as a string path."""
    # For string items, we assume they are paths
    folder_path = item_path
    # Create a synthetic folder object
    folder_obj = {"path": folder_path, "type": "DIRECTORY"}
    if fnmatch.fnmatch(folder_path, pattern_path):
        matching_folders.append({
            "folder": folder_obj,
            "repo": repo,
            "project": {"key": project_key}
        })


async def process_folder_patterns(
    folder_patterns: list[BitbucketServerFolderPattern],
    client: BitbucketClient
) -> AsyncGenerator[list[dict[str, Any]], None]:
    """Process folder patterns for Bitbucket Server."""
    for pattern in folder_patterns:
        project_key = pattern.project_key
        if not project_key:
            logger.warning("Missing project key in folder pattern, skipping")
            continue

        # Get repositories matching the pattern
        repos_to_process = await get_repositories_for_pattern(pattern, client)

        # Process each repository
        for repo_info in repos_to_process:
            matching_folders = await process_repository_folders(client, repo_info, pattern)

            # If we found matching folders, yield them
            if matching_folders:
                yield matching_folders
