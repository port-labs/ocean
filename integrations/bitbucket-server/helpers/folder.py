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
        async for repo_batch in client.get_repositories_for_project(project_key):
            for repo in repo_batch:
                if not pattern.repos or repo["slug"] in pattern.repos:
                    repos_to_process.append(repo)

        # Process each repository
        for repo in repos_to_process:
            repo_slug = repo["slug"]
            async for contents in client.get_directory_contents(
                project_key, repo_slug, pattern.path
            ):
                # Filter directories based on pattern
                matching_folders = [
                    {"folder": item, "repo": repo, "project": {"key": project_key}}
                    for item in contents
                    if item["type"] == "DIRECTORY" and fnmatch.fnmatch(item["path"], pattern.path)
                ]

                if matching_folders:
                    yield matching_folders
