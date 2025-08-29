from collections import defaultdict
from typing import Any, AsyncGenerator, Dict, List, Set, Tuple
import fnmatch
from loguru import logger
from integration import BitbucketServerFolderPattern
from client import BitbucketClient

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

        # Get repositories in the project
        repos_to_process = []

        # Handle wildcard project key differently
        if project_key == "*":
            # Get all projects first
            async for project_batch in client.get_projects():
                for project in project_batch:
                    actual_project_key = project["key"]
                    logger.info(f"Processing project: {actual_project_key}")
                    # For each project, get its repositories
                    async for repo_batch in client.get_repositories_for_project(actual_project_key):
                        for repo in repo_batch:
                            if not pattern.repos or "*" in pattern.repos or repo["slug"] in pattern.repos:
                                repos_to_process.append((repo, actual_project_key))
        else:
            # Use the specific project key
            async for repo_batch in client.get_repositories_for_project(project_key):
                for repo in repo_batch:
                    if not pattern.repos or "*" in pattern.repos or repo["slug"] in pattern.repos:
                        repos_to_process.append((repo, project_key))

        # Process each repository
        for repo_info in repos_to_process:
            repo, actual_project_key = repo_info  # Unpack the tuple
            repo_slug = repo["slug"]

            # Handle wildcard path
            path_to_use = "" if pattern.path == "*" else pattern.path

            try:
                matching_folders = []  # Initialize outside the async for loop
                async for contents in client.get_directory_contents(
                    actual_project_key, repo_slug, path_to_use
                ):
                    # The API returns a list of items, each item can be a string or a dictionary
                    # We need to handle both cases
                    for item in contents:
                        # Check if item is a dictionary with the expected structure
                        if isinstance(item, dict) and "type" in item and "path" in item:
                            if item["type"] == "DIRECTORY" and fnmatch.fnmatch(item["path"], pattern.path):
                                matching_folders.append({"folder": item, "repo": repo, "project": {"key": actual_project_key}})
                        # If it's a string, we need to construct a folder object
                        elif isinstance(item, str):
                            # For string items, we assume they are paths
                            folder_path = item
                            # Create a synthetic folder object
                            folder_obj = {"path": folder_path, "type": "DIRECTORY"}
                            if fnmatch.fnmatch(folder_path, pattern.path):
                                matching_folders.append({"folder": folder_obj, "repo": repo, "project": {"key": actual_project_key}})

                # If we found matching folders, yield them
                if matching_folders:
                    yield matching_folders

            except Exception as e:
                logger.error(f"Error getting directory contents for {repo_slug} in project {actual_project_key}: {e}")
                continue
